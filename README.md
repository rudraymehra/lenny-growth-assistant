# The Lenny Growth Assistant

A full-stack, AI-powered conversational assistant that answers product & growth
questions **strictly from Lenny's Podcast transcripts** — with verifiable
citations that deep-link to the exact YouTube moment — and turns those grounded
answers into Ship 30 for 30-style essays and rendered Markdown/HTML artifacts.

Built as a forward-deployment engagement: cloud (Anthropic Claude via the
Claude Agent SDK) and local (Ollama) model providers behind one interface,
switchable by configuration; PostgreSQL persistence; one-command Docker
Compose startup; structured logs; automated tests plus a golden retrieval eval.

| Doc | Contents |
|---|---|
| [docs/PRD.md](docs/PRD.md) | user & problem, success metrics, assumptions, scope, flows, acceptance criteria, risks |
| [docs/architecture.md](docs/architecture.md) | schema, API, engine seam & routing, ingestion/retrieval, model toggle, security, observability, topology |
| [docs/design.md](docs/design.md) | UI/UX principles, IA, interaction states, responsive, accessibility |
| [docs/manual-ui-test-plan.md](docs/manual-ui-test-plan.md) | 16-step human test pass |
| [docs/demo-script.md](docs/demo-script.md) | the 2–3 minute demo walkthrough |
| [agent-transcripts/](agent-transcripts/) | coding-agent session logs, including failed attempts and fixes |

## Architecture at a glance

```
Browser ── nginx (SPA + /api proxy, :3000)
              │ SSE over POST
          FastAPI backend (:8000)
              ├─ EngineRouter ─ provider resolved once per session
              │    ├─ ClaudeAgentEngine … Claude Agent SDK: agentic loop,
              │    │    MCP tools (search_transcripts/get_episode/save_artifact),
              │    │    ship-30-essay SKILL.md, session resume, cost capture
              │    └─ LocalRagEngine …… deterministic pipeline on Ollama:
              │         intent → retrieve → grounded prompt → stream → extract
              ├─ RAG: chunker → fastembed (in-process) → pgvector + tsvector + RRF
              ├─ Citations: [n] markers mapped to retrieved chunks (enforced)
              └─ Artifacts: nh3 sanitizer → sandboxed iframe viewer
          PostgreSQL (pgvector): sessions, messages, artifacts,
                                 episodes, chunks, ingest_runs
          Ollama (native, host) + Anthropic API (optional)
```

Why two *different* engine shapes — agency for the big model, rails for the
small one — is the central design decision; see
[architecture.md](docs/architecture.md#the-engine-asymmetry-on-purpose).

## Prerequisites

- **Docker Desktop** (Compose v2)
- **Ollama** for the local model (mandatory for the offline demo):
  `brew install ollama && brew services start ollama`
- Optional: an **Anthropic API key** for the cloud provider
- ~4 GB disk (transcripts + models + images); works on an 8 GB machine

## Quickstart — one command

```bash
git clone https://github.com/rudraymehra/lenny-growth-assistant.git
cd lenny-growth-assistant
make demo
```

`make demo` fetches the transcript dataset (shallow clone, pinned commit),
verifies Ollama + pulls `llama3.2:3b` if needed, builds and starts the stack,
waits for readiness, ingests the knowledge base (~10 min first run on a
laptop; instant when re-run), and opens http://localhost:3000.

To enable the cloud provider:

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY=sk-ant-…
docker compose up -d
```

## Environment variables

Everything has a safe default; an empty `.env` (or none) runs fully local.
See [.env.example](.env.example) for the annotated list. The load-bearing ones:

| Var | Default | Meaning |
|---|---|---|
| `DEFAULT_PROVIDER` | `auto` | `auto` → Anthropic if key set, else local. Resolved **once per session**, stamped, shown in the UI. |
| `ANTHROPIC_API_KEY` | *(empty)* | empty = cloud disabled; app still fully works |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` | cloud model |
| `OLLAMA_MODEL` | `llama3.2:3b` | local model (tested on 8 GB) |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | native host Ollama |
| `MODEL_TIMEOUT_S` | `120` | per-reply budget (SDK path gets 3×) |
| `EXPERIMENTAL_SDK_VIA_OLLAMA` | `false` | run the Agent SDK against Ollama's Anthropic-compatible endpoint ([why it's off](docs/architecture.md#experimental-sdk-via-ollama)) |

**Fallback behaviour (documented, deliberate):** no key → `auto` sessions run
local · Ollama down + no key → structured 503 + in-app setup card · provider
fails mid-reply → typed error event with a "retry on local" affordance —
**never** a silent model swap, never a hung spinner.

## Everyday commands

```bash
make demo            # one-command startup (idempotent)
make ingest          # re-ingest transcripts (hash-skips unchanged episodes)
make ingest-refresh  # force full re-chunk + re-embed
make test            # 60 unit + integration tests (no model required)
make eval            # golden-set retrieval eval: hit@5 ≥ 80% against real KB
make logs            # follow structured JSON backend logs
make clean           # stop and delete volumes (destroys the database)
```

## API

`/api/v1` — OpenAPI at http://localhost:8000/docs

| Endpoint | Purpose |
|---|---|
| `POST /sessions` | create session (provider resolution happens here; 503 if none usable) |
| `GET /sessions` · `GET /sessions/{id}/messages` | history |
| `POST /sessions/{id}/messages` | **SSE stream**: `token`, `tool_use`, `citation`, `artifact`, then `done{usage,cost}` or `error{code}` |
| `GET /artifacts/{id}[?raw=true]` | sanitized artifact (raw shows what the sanitizer removed) |
| `GET /config` | non-secret runtime config + knowledge-base stats |
| `GET /health` · `GET /health/ready` | liveness · dependency readiness (never spends API credit) |

Errors are always `{"error": {"code", "message", "request_id"}}`; the
request id is also in the `x-request-id` header and every log line.

## Testing

```bash
make test   # chunker, RRF fusion, citation enforcement, sanitizer XSS corpus,
            # artifact stream extraction, intent routing, provider-resolution
            # matrix, SSE relay guarantees, API contract + persistence (FakeEngine)
make eval   # 15-question golden set, prints a hit@5 table, asserts ≥ 80%
```

Integration tests run against a dedicated `lenny_test` database with a
scripted engine — no model needed. Three real transcripts are vendored as
fixtures so tests never touch the network. The human pass lives in
[docs/manual-ui-test-plan.md](docs/manual-ui-test-plan.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| Setup card: "No model provider is available" | `brew services start ollama && ollama pull llama3.2:3b`, or set `ANTHROPIC_API_KEY` in `.env`; then retry |
| `/health/ready` shows `ollama.ok: false` | same as above; from containers Ollama is reached at `host.docker.internal:11434` |
| Local replies are slow | first reply loads the model (~10 s); don't run `make ingest` concurrently on an 8 GB machine; try a smaller model |
| Empty/odd answers with citations missing | check KB stats in the sidebar; re-run `make ingest`; inspect `retrieval.query` log events (`make logs`) |
| Anthropic errors mid-reply | check key/credits; the error frame names the cause; start a local session to keep working |
| Port clash (3000/8000/5433) | edit the `ports:` mappings in `docker-compose.yml` |

## Extending

- **New knowledge source:** implement a parser to `EpisodeMeta` + segments in
  `rag/chunker.py`, reuse everything downstream.
- **New skill:** drop a `SKILL.md` under `backend/workspace/.claude/skills/`
  (cloud engine discovers it; wire it into `skills/loader.py` + an intent for
  the local path).
- **New provider:** implement the two-method `AgentEngine` protocol
  (`engines/base.py`) and register it in `engines/router.py`. Nothing else changes.

## Security notes

Generated HTML is treated as untrusted: nh3 allowlist sanitization server-side
(raw + sanitized both stored for audit), rendered only inside
`<iframe sandbox="">` with a `default-src 'none'` CSP client-side. Chat
markdown never renders raw HTML. No secrets in the repo; keys live in `.env`
(gitignored). Details: [architecture.md](docs/architecture.md#artifact-security).

## Data source & attribution

Transcripts: [ChatPRD/lennys-podcast-transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts)
(303 episodes of [Lenny's Podcast](https://www.lennyspodcast.com/)). All
content belongs to Lenny Rachitsky and the respective guests; used here for
personal/educational evaluation only and not redistributed (the dataset is
fetched at setup time, never committed).
