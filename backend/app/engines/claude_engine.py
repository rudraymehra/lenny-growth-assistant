"""ClaudeAgentEngine — the cloud (Anthropic) provider.

A genuine agentic loop via the Claude Agent SDK: the model decides when to
search the knowledge base, which episodes to read, and when to save an
artifact, using in-process MCP tools defined below. The Ship 30 essay skill is
discovered from workspace/.claude/skills (filesystem skills, Agent SDK
convention). Multi-turn context is kept by resuming the SDK session recorded
on our session row — the SDK transcript lives in the container, while the
authoritative conversation history lives in Postgres.

Citation enforcement matches the local engine: search results are numbered
globally per request ([1], [2], …); after the reply completes, only markers
that map to actually-retrieved chunks become citations.
"""

import asyncio
import time
from typing import Any, AsyncIterator
from uuid import UUID

import asyncpg

from app.artifacts.store import save_artifact as persist_artifact
from app.config import Settings
from app.db.repos import ArtifactRepo, SessionRepo
from app.logging import EVT_ENGINE_ERROR, EVT_MODEL_CALL, EVT_MODEL_TIMEOUT, get_logger
from app.models.domain import (
    ArtifactEvent, CitationEvent, DoneEvent, EngineEvent, EngineHealth, ErrorEvent,
    Message, RetrievedChunk, Session, TokenEvent, ToolUseEvent, Usage,
)
from app.rag.citations import extract_citations
from app.rag.embedder import embed_query_async
from app.rag.search import hybrid_search
from app.skills.loader import WORKSPACE_DIR

log = get_logger(__name__)

_SYSTEM_PROMPT = """You are the Lenny Growth Assistant, an internal tool for a product & growth team, answering strictly from Lenny's Podcast transcripts.

Rules:
- For any product/growth question, FIRST call search_transcripts (multiple angles if needed) and answer only from what it returns.
- Mark every grounded claim with the excerpt's inline citation marker [n]. Never invent markers or cite excerpts you did not receive.
- Name the guest when using their story or advice.
- If searches return nothing relevant, say the transcripts don't cover it — plainly, in one short paragraph. No outside knowledge.
- When the user asks for a document, web page, or essay, produce it with the save_artifact tool (complete, self-contained content; for HTML: inline CSS only, no JavaScript, no external resources except https images). In chat, reply with a 1–2 sentence summary — never paste the full document.
- Keep chat answers concise, in clean markdown."""


class _RequestContext:
    """Per-request accumulation shared with the MCP tool closures."""

    def __init__(self) -> None:
        self.retrieved: list[RetrievedChunk] = []
        self.artifacts: list[Any] = []  # domain Artifact rows created via save_artifact


class ClaudeAgentEngine:
    name = "anthropic"

    def __init__(self, settings: Settings, pool: asyncpg.Pool):
        self._settings = settings
        self._pool = pool
        self._artifact_repo = ArtifactRepo(pool)
        self._session_repo = SessionRepo(pool)
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_agent_sessions)

    async def check(self) -> EngineHealth:
        # Key presence only — a readiness probe must never spend API credit.
        if self._settings.anthropic_configured:
            return EngineHealth(ok=True, detail="API key configured")
        return EngineHealth(ok=False, detail="ANTHROPIC_API_KEY not set")

    async def stream_reply(
        self, session: Session, history: list[Message], user_content: str
    ) -> AsyncIterator[EngineEvent]:
        from claude_agent_sdk import (
            AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient,
            ResultMessage, TextBlock, ToolUseBlock,
        )

        started = time.perf_counter()
        ctx = _RequestContext()
        full_text = ""
        usage = Usage(provider=self.name, model=self._settings.anthropic_model)

        try:
            options = self._build_options(ctx, session.id, session.sdk_session_id)
            async with self._semaphore:
                async with asyncio.timeout(self._settings.model_timeout_s * 3):
                    async with ClaudeSDKClient(options=options) as client:
                        await client.query(user_content)
                        async for msg in client.receive_response():
                            if isinstance(msg, AssistantMessage):
                                for block in msg.content:
                                    if isinstance(block, TextBlock):
                                        full_text += block.text
                                        yield TokenEvent(text=block.text)
                                    elif isinstance(block, ToolUseBlock):
                                        yield ToolUseEvent(
                                            tool=block.name.removeprefix("mcp__kb__"),
                                            summary=_tool_summary(block.name, block.input),
                                        )
                            elif isinstance(msg, ResultMessage):
                                usage.cost_usd = msg.total_cost_usd or 0.0
                                raw_usage = getattr(msg, "usage", None) or {}
                                usage.input_tokens = int(raw_usage.get("input_tokens", 0))
                                usage.output_tokens = int(raw_usage.get("output_tokens", 0))
                                if msg.session_id and msg.session_id != session.sdk_session_id:
                                    await self._session_repo.set_sdk_session_id(
                                        session.id, msg.session_id
                                    )

            # Essays/documents carry their [n] markers inside the artifact, so
            # scan artifact bodies too — chips then link the essay's sources.
            citation_text = full_text + "\n" + "\n".join(a.content for a in ctx.artifacts)
            for citation in extract_citations(citation_text, ctx.retrieved):
                yield CitationEvent(citation=citation)
            for artifact in ctx.artifacts:
                yield ArtifactEvent(
                    artifact_id=artifact.id, kind=artifact.kind, title=artifact.title
                )

            usage.latency_ms = int((time.perf_counter() - started) * 1000)
            log.info(EVT_MODEL_CALL, provider=self.name, model=usage.model,
                     latency_ms=usage.latency_ms, cost_usd=usage.cost_usd, ok=True)
            yield DoneEvent(usage=usage)

        except TimeoutError:
            log.error(EVT_MODEL_TIMEOUT, provider=self.name, model=usage.model,
                      timeout_s=self._settings.model_timeout_s * 3)
            yield ErrorEvent(
                code="model_timeout",
                message="The cloud model run exceeded its time budget. Try again.",
                recoverable=True,
            )
        except Exception as exc:  # noqa: BLE001 — engine contract: always terminate the stream
            detail = str(exc)
            code = "anthropic_auth_failed" if "authentication" in detail.lower() or "401" in detail \
                else "provider_unavailable"
            log.error(EVT_ENGINE_ERROR, provider=self.name, code=code, detail=detail[:500])
            yield ErrorEvent(
                code=code,
                message="The Anthropic provider failed. Check ANTHROPIC_API_KEY, or start a "
                        "session on the local model.",
                recoverable=True,
            )

    # ── internals ────────────────────────────────────────────────────────────

    def _build_options(self, ctx: _RequestContext, session_id: UUID, sdk_session_id: str | None):
        from claude_agent_sdk import ClaudeAgentOptions

        env = {"ANTHROPIC_API_KEY": self._settings.anthropic_api_key}
        if self._settings.experimental_sdk_via_ollama:
            # Ollama >= 0.14 exposes an Anthropic-compatible /v1/messages.
            # Verified working, but slow + weak tool use on small models — see
            # architecture.md#experimental-sdk-via-ollama.
            env = {
                "ANTHROPIC_BASE_URL": self._settings.ollama_base_url,
                "ANTHROPIC_AUTH_TOKEN": "ollama",
            }

        return ClaudeAgentOptions(
            model=self._settings.ollama_model if self._settings.experimental_sdk_via_ollama
                  else self._settings.anthropic_model,
            system_prompt=_SYSTEM_PROMPT,
            cwd=str(WORKSPACE_DIR),
            setting_sources=["project"],  # discover workspace/.claude/skills/*
            mcp_servers={"kb": self._make_mcp_server(ctx, session_id)},
            allowed_tools=[
                "mcp__kb__search_transcripts",
                "mcp__kb__get_episode",
                "mcp__kb__save_artifact",
                "Skill",
            ],
            # "default" + the allowed_tools pre-approval covers everything the
            # agent needs. (bypassPermissions is refused when the container
            # runs as root — found in testing.)
            permission_mode="default",
            max_turns=10,
            env=env,
            resume=sdk_session_id,
        )

    def _make_mcp_server(self, ctx: _RequestContext, session_id: UUID):
        """In-process MCP tools closing over per-request context, so citation
        numbering is global across all searches within one reply."""
        from claude_agent_sdk import create_sdk_mcp_server, tool

        @tool(
            "search_transcripts",
            "Search Lenny's Podcast transcripts. Returns numbered excerpts; cite them as [n].",
            {"query": str},
        )
        async def search_transcripts(args: dict) -> dict:
            query = str(args["query"])
            embedding = await embed_query_async(query, self._settings.embedding_model)
            chunks = await hybrid_search(
                self._pool, embedding, query, self._settings.retrieval_top_k
            )
            if not chunks:
                return {"content": [{"type": "text",
                                     "text": "No relevant transcript excerpts found."}]}
            start_index = len(ctx.retrieved)
            ctx.retrieved.extend(chunks)
            rendered = "\n\n".join(
                f"[{start_index + i}] {c.guest} — \"{c.episode_title}\" (t={c.start_ts}s)\n"
                f"{c.content[:2000]}"
                for i, c in enumerate(chunks, start=1)
            )
            return {"content": [{"type": "text", "text": rendered}]}

        @tool(
            "get_episode",
            "Get metadata and opening excerpts for one episode by slug.",
            {"slug": str},
        )
        async def get_episode(args: dict) -> dict:
            row = await self._pool.fetchrow(
                "SELECT id, slug, guest, title, description, youtube_url, publish_date "
                "FROM episodes WHERE slug = $1", str(args["slug"]),
            )
            if not row:
                return {"content": [{"type": "text", "text": "Episode not found."}]}
            head = await self._pool.fetch(
                "SELECT content FROM chunks WHERE episode_id = $1 ORDER BY chunk_index LIMIT 2",
                row["id"],
            )
            text = (
                f"{row['title']} — {row['guest']} ({row['publish_date']})\n"
                f"{row['youtube_url']}\n\n{row['description'] or ''}\n\n"
                + "\n\n".join(r["content"][:1500] for r in head)
            )
            return {"content": [{"type": "text", "text": text}]}

        @tool(
            "save_artifact",
            "Save a finished document for the in-app artifact viewer. "
            "kind: 'markdown' or 'html'. content: the complete document. "
            "Call EXACTLY ONCE per reply, with the final version only.",
            {"kind": str, "title": str, "content": str},
        )
        async def save_artifact(args: dict) -> dict:
            kind = str(args["kind"]).lower()
            if kind not in ("markdown", "html"):
                return {"content": [{"type": "text",
                                     "text": "Invalid kind: use 'markdown' or 'html'."}],
                        "is_error": True}
            artifact = await persist_artifact(
                self._artifact_repo, session_id, kind,
                str(args.get("title", "")), str(args["content"]),
            )
            ctx.artifacts.append(artifact)
            return {"content": [{"type": "text",
                                 "text": f"Artifact saved (id={artifact.id}). It is now visible "
                                         "to the user — summarize it in one sentence."}]}

        return create_sdk_mcp_server(name="kb", version="1.0.0",
                                     tools=[search_transcripts, get_episode, save_artifact])


def _tool_summary(name: str, tool_input: dict | None) -> str:
    tool_input = tool_input or {}
    if name.endswith("search_transcripts"):
        return f'"{str(tool_input.get("query", ""))[:80]}"'
    if name.endswith("get_episode"):
        return str(tool_input.get("slug", ""))
    if name.endswith("save_artifact"):
        return f'{tool_input.get("kind", "?")}: {str(tool_input.get("title", ""))[:60]}'
    return name
