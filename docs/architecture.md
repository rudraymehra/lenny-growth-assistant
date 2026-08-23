# Architecture

The Lenny Growth Assistant is three containers plus a native model runtime:

```
┌──────────────────────────── Docker Compose ────────────────────────────┐
│                                                                        │
│  frontend (nginx :3000)                                                │
│    • serves the built React SPA                                        │
│    • proxies /api → backend:8000 (proxy_buffering off for SSE)         │
│                    │                                                   │
│  backend (FastAPI :8000)                                               │
│    api/        HTTP contract, SSE encoding, errors, health             │
│    engines/    AgentEngine seam: ClaudeAgentEngine | LocalRagEngine    │
│    rag/        chunker, fastembed embeddings, hybrid search, citations │
│    artifacts/  fence extraction, nh3 sanitizer, store                  │
│    ingest/     idempotent transcript ingestion CLI                     │
│         │                          │                                   │
│  postgres (pgvector :5433→5432)    │ host.docker.internal:11434        │
│    sessions, messages, artifacts,  │                                   │
│    episodes, chunks(vector+tsv),   │                                   │
│    ingest_runs                     │                                   │
└────────────────────────────────────┼───────────────────────────────────┘
                                     │
                       Ollama (native on the host — Metal GPU)
                       Anthropic API (api.anthropic.com, if key set)
```

Ollama deliberately runs natively rather than in Compose on macOS: containers
get no GPU access on Docker Desktop, and an 8 GB host cannot afford a model
inside the Docker VM's memory budget. A `--profile ollama-docker` service
exists for Linux reviewers who prefer everything containerized.

## Database schema

Six tables in one Postgres (see `backend/app/db/schema.sql` for the DDL —
it is short and readable by design):

| Table | Purpose | Notable columns |
|---|---|---|
| `sessions` | one chat session | `provider` (CHECK anthropic\|local, stamped at creation), `model`, `sdk_session_id` (Agent SDK resume handle), `user_metadata jsonb` |
| `messages` | conversation turns | `citations jsonb`, `artifact_id`, `usage jsonb` (tokens, cost, latency) |
| `episodes` | one podcast episode | `slug`, front-matter metadata, `content_hash` (idempotent ingest) |
| `chunks` | retrieval unit | `embedding vector(384)` + HNSW index, `tsv tsvector` (generated) + GIN index, `start_ts`/`end_ts` seconds, `speaker` |
| `artifacts` | generated documents | **both** `content` (raw) and `sanitized_content` — what the sanitizer removed is auditable |
| `ingest_runs` | ingestion audit trail | status, counts, error — surfaced in `/config` and the UI |

**Why no migration framework:** the schema is applied on startup from one
idempotent `schema.sql`. For a green-field system at this scale, Alembic adds
a moving part without adding safety; the moment this system needs its second
schema change in production, introduce it.

**Why pgvector instead of a vector DB:** ~10k chunks. One database means one
backup story, one health check, one connection pool, and transactional
consistency between conversations and the knowledge base. A dedicated vector
store earns its keep at millions of vectors, not thousands.

## Ingestion flow

`python -m app.ingest.cli` (idempotent; `--refresh` forces):

1. `scripts/fetch_transcripts.sh` shallow-clones
   [ChatPRD/lennys-podcast-transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts)
   (303 episodes, pinned to a known commit) into `./data`, volume-mounted read-only.
2. Each `episodes/*/transcript.md` is sha256-hashed; unchanged files are skipped.
3. `rag/chunker.py` parses YAML front matter, then splits the body on
   `Speaker Name (HH:MM:SS):` headers (carrying the speaker across name-less
   continuation blocks, stripping `[inaudible …]`), and merges segments into
   ~800-token chunks **breaking only on speaker-turn boundaries**. Each chunk
   keeps its first segment's timestamp.
4. `fastembed` (BAAI/bge-small-en-v1.5, 384-d ONNX, pre-baked into the image)
   embeds chunks in batches; episode + chunks are written in one transaction.
5. An `ingest_runs` row records counts/status/error for every run.

Traceability: every chunk knows its episode, speaker, and timestamp; every
citation renders as guest + episode + `youtube_url&t={seconds}` deep link.

## Retrieval

`rag/search.py` runs two legs and fuses them with Reciprocal Rank Fusion
(k=60, 30 candidates per leg):

- **Vector leg:** pgvector cosine over bge-small embeddings — semantic match.
- **Full-text leg:** Postgres `tsvector`/`ts_rank` — exact terms, names,
  acronyms that small embedding models blur.

Hybrid + RRF is the boring, robust choice: no score normalization headaches,
and each leg covers the other's known failure mode. Quality is measured, not
assumed: `make eval` runs a 15-question golden set asserting hit@5 ≥ 80%
(`backend/tests/evals/`).

## Agent routing and the engine seam

`engines/base.py` defines the contract both providers implement:

```python
class AgentEngine(Protocol):
    def stream_reply(session, history, user_content) -> AsyncIterator[EngineEvent]: ...
    async def check() -> EngineHealth
```

`EngineEvent` is a discriminated union — `token | tool_use | citation |
artifact | done | error` — which is also, verbatim, the SSE wire protocol.
The API layer is engine-agnostic: persist user message → relay events →
persist assistant message on `done`.

### ClaudeAgentEngine (cloud)

A real agentic loop on the Claude Agent SDK:

- **Custom in-process MCP tools** (`search_transcripts`, `get_episode`,
  `save_artifact`) defined with `@tool` + `create_sdk_mcp_server`. The model
  decides when and how often to search.
- **Skills:** `workspace/.claude/skills/ship-30-essay/SKILL.md` is discovered
  via `setting_sources=["project"]` with `cwd=workspace/`.
- **Sessions:** first reply captures `ResultMessage.session_id` into
  `sessions.sdk_session_id`; later turns pass `resume=` so the SDK keeps its
  own transcript. Postgres remains the authoritative history.
- **Cost:** `ResultMessage.total_cost_usd` flows into `messages.usage` and the
  UI footer of every assistant message.
- Concurrency is capped (`MAX_CONCURRENT_AGENT_SESSIONS`, default 2) because
  each SDK run is a subprocess costing ~1 GiB RAM.

### LocalRagEngine (Ollama)

Deliberately **not** agentic — a deterministic pipeline:

```
classify intent (chat|essay|artifact_html|artifact_markdown, keyword rules)
→ retrieve (always, before the model)
→ compact grounded prompt (numbered excerpts + windowed history
   + the same SKILL.md body for essays)
→ stream Ollama /api/chat (think:false, num_ctx 8k/16k)
→ extract ```artifact:*``` fences from the stream, sanitize, persist
```

### The engine asymmetry, on purpose

A 3–4B quantized model handles free-form tool calling poorly: it forgets to
search, mangles JSON arguments, and loops. Giving each model class the control
flow it can actually execute is the design: the big model gets agency, the
small model gets rails. Both meet the identical EngineEvent contract, so the
product behaves the same — grounded answers, citations, essays, artifacts —
on both providers.

### Citations are enforced, not requested

Both engines number retrieved excerpts `[1]..[n]` in the prompt and require
inline markers. The backend then maps markers to the *actually retrieved*
chunks (`rag/citations.py`) and builds citation objects from database truth.
A marker with no matching chunk is dropped and logged (`citation.unmatched`).
The model can never fabricate a source — at worst it can under-cite, which the
UI surfaces as a "no sources cited" notice.

## Model toggle & fallback behavior

Provider resolution happens **once, at session creation**
(`engines/router.py` + `Settings.resolve_provider`), is stamped on the session
row, and is always visible in the UI badge:

| `DEFAULT_PROVIDER` / request | key set? | Ollama up? | result |
|---|---|---|---|
| auto | yes | – | anthropic |
| auto | no | yes | local |
| auto | no | no | **503 provider_unavailable** + setup card |
| anthropic (explicit) | no | – | 503 (no silent downgrade) |
| local (explicit) | – | no | 503 (no silent upgrade) |

There is **no silent mid-conversation fallback**. If a session's provider
fails mid-reply, the stream carries a typed `error` event and the UI offers
"start a new chat on the local model". Silently swapping models would corrupt
the two properties this product sells: grounding and cost transparency.

Switching providers requires zero code changes: `.env` (`DEFAULT_PROVIDER`,
`ANTHROPIC_MODEL`, `OLLAMA_MODEL`) or the per-session UI buttons.

### <a name="local-model-choice"></a>Local model choice (measured, not guessed)

`llama3.2:3b` is the default because it was the model that survived contact
with the demo hardware. `qwen3:4b` was tried first and measured at ~4.5 tok/s
on the 8 GB M2 under real conditions, with reasoning preambles leaking into
answers even with `think: false` — a 2-minute reply is a broken product.
llama3.2:3b (2 GB, no thinking mode) answers interactively. The `think`
parameter is now sent only to model families that support it (Ollama rejects
it otherwise). Machines with ≥16 GB should raise `OLLAMA_MODEL` to an 8B-class
model for noticeably better essay quality — a one-line `.env` change.

### <a name="experimental-sdk-via-ollama"></a>Experimental: Agent SDK over Ollama

Ollama ≥ 0.14 exposes an Anthropic-compatible `/v1/messages`, and the Agent
SDK honours `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`. Setting
`EXPERIMENTAL_SDK_VIA_OLLAMA=true` routes the *agentic* engine at the local
model. It works, and it is not the default for two measured reasons: the SDK
re-sends its large system prompt every turn with no prompt caching (30–90 s
per reply on an 8 GB machine), and small models' tool-call reliability is too
low for an agentic loop (see the asymmetry note above). The deterministic
LocalRagEngine is the supported local path.

## Artifact security

Two independent layers; either alone should hold.

1. **Server (`artifacts/sanitizer.py`)** — nh3 (ammonia) allowlist.
   *Permitted:* structure (headings/p/lists/tables/blockquote/details),
   inline semantics, `class`/`style` attributes, one `<style>` block,
   https/http/mailto URLs, https images.
   *Blocked:* `<script>` and all `on*` handlers (execution), `<iframe>/<object>/<embed>`
   (nested contexts), `<form>/<input>` (credential capture), `javascript:`/`data:`
   URLs, `<link>`/`<base>` (external fetch / URL hijack). Raw + sanitized are
   both stored, so `GET /artifacts/{id}?raw=true` shows exactly what was removed.
2. **Client (`SandboxFrame.tsx`)** — `<iframe sandbox="" srcdoc>`: empty
   sandbox = no scripts, opaque origin (no cookies/storage/parent DOM), no
   forms/popups/navigation — plus an injected CSP of
   `default-src 'none'; style-src 'unsafe-inline'; img-src https: data:`.
   A sanitizer bypass still lands in an inert, origin-less document.

Chat markdown is a third, narrower surface: react-markdown never renders raw
HTML, so model output in chat is inert text.

## Observability

`structlog` JSON to stdout with a stable event taxonomy
(`backend/app/logging.py`): `http.request`, `retrieval.query` (hit_count,
latency), `model.call` / `model.timeout`, `citation.unmatched`,
`artifact.sanitized` (removed_bytes), `ingest.run`, `engine.error`,
`db.error`. Every line carries the `request_id` bound by middleware and echoed
in error envelopes and the `x-request-id` response header — one id correlates
a user report to logs to the failing subsystem. Per-message token/cost/latency
is persisted in `messages.usage` and shown in the UI.

## Resilience map

| Failure | Behaviour |
|---|---|
| No `ANTHROPIC_API_KEY` | auto-sessions resolve to local; cloud buttons disabled with tooltip |
| Ollama down + no key | `POST /sessions` → 503 with fix instructions; UI shows setup card |
| Ollama dies mid-reply | typed `ollama_unreachable` error frame; user message persisted; no half-written assistant row |
| Model timeout | `model_timeout` error frame after `MODEL_TIMEOUT_S` (SDK path gets 3×: agentic loops legitimately run longer) |
| Empty retrieval | prompt instructs a grounded refusal; UI renders a zero-citation notice |
| DB down | `/health/ready` → 503; requests fail with structured `db_unavailable`-class errors |
| Engine crash mid-stream | `api/sse.py` guarantees a terminal frame — the UI never hangs on a spinner |

## Memory budget (8 GB MacBook Air M2 — the demo machine)

| Component | Resident |
|---|---|
| Ollama + qwen3:4b (Q4, native, Metal) | ~2.6 GB |
| Docker VM (postgres ~300 MB, backend ~800 MB incl. ONNX, nginx ~10 MB) | ~2.5 GB cap |
| One Agent SDK subprocess (cloud sessions only, max 2) | ~1 GB each |
| Headroom for macOS + browser | remainder |

## Deployment topology

Local-first by requirement: `make demo` = fetch data → verify Ollama → compose
up → readiness gate → ingest → open browser. The same compose file runs on a
single cloud VM (EC2/Lightsail) unchanged — put a TLS proxy in front and use
the `ollama-docker` profile or a GPU instance for the local provider.
