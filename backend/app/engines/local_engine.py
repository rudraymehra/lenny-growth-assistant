"""LocalRagEngine — the local (Ollama) provider.

Deliberately NOT an agentic tool-calling loop: 3–4B local models handle
free-form tool use poorly, so this engine runs a deterministic pipeline —
classify intent → retrieve (always) → build a compact grounded prompt →
stream from Ollama /api/chat → enforce citations and extract artifacts in the
backend. Same EngineEvent contract as the cloud engine; the trade-off is
documented in architecture.md#engine-asymmetry.
"""

import json
import time
from typing import AsyncIterator

import asyncpg
import httpx

from app.artifacts.extractor import ArtifactStreamFilter
from app.artifacts.store import save_artifact
from app.config import Settings
from app.db.repos import ArtifactRepo
from app.engines.intents import Intent, classify
from app.logging import EVT_ENGINE_ERROR, EVT_MODEL_CALL, EVT_MODEL_TIMEOUT, get_logger
from app.models.domain import (
    ArtifactEvent, Citation, CitationEvent, DoneEvent, EngineEvent, EngineHealth,
    ErrorEvent, Message, RetrievedChunk, Session, TokenEvent, ToolUseEvent, Usage,
)
from app.rag.citations import extract_citations
from app.rag.embedder import embed_query_async
from app.rag.search import hybrid_search
from app.skills.loader import ship30_prompt

log = get_logger(__name__)

_CHUNK_CHAR_LIMIT = 1600   # keep the prompt within a small model's context
_CHAT_CHUNKS = 6           # chat uses fewer excerpts than essays: prefill on a
_ESSAY_CHUNKS = 8          # small local model is the dominant latency cost
_HISTORY_MESSAGES = 6
_HISTORY_CHAR_LIMIT = 1200

_GROUNDING_SYSTEM = """You are the Lenny Growth Assistant, an internal tool for a product & growth team. You answer questions using ONLY the numbered transcript excerpts from Lenny's Podcast provided in each request.

Rules:
- Every sentence that uses an excerpt MUST end with its citation marker: [1], [2], etc., matching the excerpt numbers. Example of correct style: "Brian Chesky argues founders must stay in the details, comparing it to how a board oversees a CEO [2]. He explicitly separates that from telling people what to do [2]."
- Name the guest when you use their story or advice.
- If the excerpts do not contain enough information to answer, say exactly that in one short paragraph — do not invent facts, do not use outside knowledge, and do not add citation markers you cannot support.
- Answer in clean markdown. Be direct and practical."""

_ARTIFACT_INSTRUCTION = """When the user asks for a document (HTML page or markdown document), output it inside a fenced block:

```artifact:{kind} title="A short descriptive title"
...the complete document...
```

For HTML: produce one complete, self-contained document with inline <style>. No JavaScript, no external resources except https images. Before the fenced block, write one short sentence saying what you created. Do not repeat the document content outside the block."""


def _render_excerpts(chunks: list[RetrievedChunk]) -> str:
    lines = []
    for i, c in enumerate(chunks, start=1):
        lines.append(
            f"[{i}] {c.guest} — \"{c.episode_title}\" (t={c.start_ts}s)\n"
            f"{c.content[:_CHUNK_CHAR_LIMIT]}"
        )
    return "\n\n".join(lines)


class LocalRagEngine:
    name = "local"

    def __init__(self, settings: Settings, pool: asyncpg.Pool):
        self._settings = settings
        self._pool = pool
        self._artifact_repo = ArtifactRepo(pool)

    async def check(self) -> EngineHealth:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._settings.ollama_base_url}/api/tags")
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]
                if any(m.startswith(self._settings.ollama_model) for m in models):
                    return EngineHealth(ok=True, detail=f"model {self._settings.ollama_model} available")
                return EngineHealth(
                    ok=False,
                    detail=f"Ollama reachable but model {self._settings.ollama_model} not pulled "
                           f"(run: ollama pull {self._settings.ollama_model})",
                )
        except Exception as exc:  # noqa: BLE001
            return EngineHealth(ok=False, detail=f"Ollama unreachable: {exc}")

    async def stream_reply(
        self, session: Session, history: list[Message], user_content: str
    ) -> AsyncIterator[EngineEvent]:
        started = time.perf_counter()
        try:
            intent = classify(user_content)

            # 1. Retrieval — always grounded, retrieval happens before the model.
            yield ToolUseEvent(tool="search_transcripts", summary=f'"{user_content[:80]}"')
            embedding = await embed_query_async(user_content, self._settings.embedding_model)
            top_k = min(
                self._settings.retrieval_top_k,
                _ESSAY_CHUNKS if intent == "essay" else _CHAT_CHUNKS,
            )
            chunks = await hybrid_search(self._pool, embedding, user_content, top_k)
            yield ToolUseEvent(
                tool="search_transcripts",
                summary=f"{len(chunks)} transcript excerpts retrieved",
            )

            # 2. Prompt assembly by intent.
            messages = self._build_messages(intent, history, user_content, chunks)

            # 3. Stream from Ollama, filtering artifact fences out of chat text.
            artifact_filter = ArtifactStreamFilter()
            full_text = ""
            usage = Usage(provider=self.name, model=self._settings.ollama_model)
            async for delta, final_stats in self._ollama_stream(messages, intent):
                if final_stats is not None:
                    usage.input_tokens = final_stats.get("prompt_eval_count", 0)
                    usage.output_tokens = final_stats.get("eval_count", 0)
                if delta:
                    full_text += delta
                    visible = artifact_filter.feed(delta)
                    if visible:
                        yield TokenEvent(text=visible)
            tail = artifact_filter.flush()
            if tail:
                yield TokenEvent(text=tail)

            # 4. Citations from database truth (only markers the model used
            #    AND retrieval actually returned survive).
            for citation in extract_citations(full_text, chunks):
                yield CitationEvent(citation=citation)

            # 5. Artifacts extracted from fences, sanitized, persisted.
            for extracted in artifact_filter.artifacts:
                artifact = await save_artifact(
                    self._artifact_repo, session.id,
                    extracted.kind, extracted.title, extracted.content,
                )
                yield ArtifactEvent(artifact_id=artifact.id, kind=artifact.kind, title=artifact.title)

            usage.latency_ms = int((time.perf_counter() - started) * 1000)
            log.info(EVT_MODEL_CALL, provider=self.name, model=usage.model,
                     latency_ms=usage.latency_ms, ok=True, intent=intent)
            yield DoneEvent(usage=usage)

        except httpx.TimeoutException:
            log.error(EVT_MODEL_TIMEOUT, provider=self.name,
                      model=self._settings.ollama_model, timeout_s=self._settings.model_timeout_s)
            yield ErrorEvent(
                code="model_timeout",
                message=f"The local model did not respond within {int(self._settings.model_timeout_s)}s. "
                        "It may be loading — try again, or use a smaller model.",
                recoverable=True,
            )
        except (httpx.ConnectError, httpx.HTTPStatusError) as exc:
            log.error(EVT_ENGINE_ERROR, provider=self.name, code="ollama_unreachable", detail=str(exc))
            yield ErrorEvent(
                code="ollama_unreachable",
                message="Could not reach Ollama. Start it with: brew services start ollama "
                        f"(and pull the model: ollama pull {self._settings.ollama_model}).",
                recoverable=True,
            )
        except Exception as exc:  # noqa: BLE001 — engine contract: always terminate the stream
            log.error(EVT_ENGINE_ERROR, provider=self.name, code="internal_error", detail=str(exc))
            yield ErrorEvent(code="internal_error", message="Unexpected engine failure.", recoverable=False)

    # ── internals ────────────────────────────────────────────────────────────

    def _build_messages(
        self, intent: Intent, history: list[Message],
        user_content: str, chunks: list[RetrievedChunk],
    ) -> list[dict]:
        system = _GROUNDING_SYSTEM
        if intent == "essay":
            system += "\n\n# Essay task\n" + ship30_prompt() + \
                      "\n\n" + _ARTIFACT_INSTRUCTION.replace("{kind}", "markdown")
        elif intent == "artifact_html":
            system += "\n\n" + _ARTIFACT_INSTRUCTION.replace("{kind}", "html")
        elif intent == "artifact_markdown":
            system += "\n\n" + _ARTIFACT_INSTRUCTION.replace("{kind}", "markdown")

        messages: list[dict] = [{"role": "system", "content": system}]
        for m in history[-_HISTORY_MESSAGES:]:
            messages.append({"role": m.role, "content": m.content[:_HISTORY_CHAR_LIMIT]})

        excerpts = _render_excerpts(chunks) if chunks else "(no relevant excerpts found)"
        # Small models weight the end of the prompt heavily — restate the
        # citation contract right next to the request.
        reminder = (
            "(Cite excerpts inline with [n] markers after each claim; "
            "if the excerpts don't cover it, say so.)"
        )
        messages.append({
            "role": "user",
            "content": f"Transcript excerpts:\n\n{excerpts}\n\n---\nRequest: {user_content}\n{reminder}",
        })
        return messages

    async def _ollama_stream(self, messages: list[dict], intent: Intent):
        """Yield (delta_text, final_stats_or_None) pairs from /api/chat."""
        payload = {
            "model": self._settings.ollama_model,
            "messages": messages,
            "stream": True,
            "options": {
                # Essays need headroom: skill + excerpts + ~1,700 output tokens.
                "num_ctx": 16384 if intent != "chat" else 8192,
                "temperature": 0.7,
            },
        }
        # Ollama rejects `think` on models without a thinking mode, so send it
        # only where it applies (suppresses reasoning tokens on those models).
        if any(f in self._settings.ollama_model for f in ("qwen3", "deepseek-r1", "gpt-oss")):
            payload["think"] = False
        timeout = httpx.Timeout(self._settings.model_timeout_s, connect=5.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", f"{self._settings.ollama_base_url}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        # Ollama reports some failures as 200 + error lines.
                        raise httpx.HTTPStatusError(
                            f"Ollama error: {data['error']}",
                            request=resp.request, response=resp,
                        )
                    if data.get("done"):
                        yield "", data
                    else:
                        yield data.get("message", {}).get("content", ""), None
