# Agent transcripts

This project was built with Claude Code (Claude Fable 5) directing the full
engagement: research → PRD → architecture → implementation → debugging → docs.
This folder contains the exported session logs (secrets redacted). The point
of keeping them is not that the process was smooth — it's the record of what
broke and how it was verified and fixed.

## How the agent was used

1. **Research phase (parallel subagents):** one agent located and
   format-analyzed the transcript dataset (ChatPRD repo, front-matter + speaker
   blocks); one researched the Claude Agent SDK's session/MCP/skills surface;
   one researched Oogway Labs and the Ship 30 for 30 writing system; the main
   agent verified the Ollama ⇄ Anthropic-compatibility question directly.
2. **Design phase:** a dedicated planning agent pressure-tested the proposed
   architecture and returned corrections that were adopted (fetch-based SSE
   consumption, provider resolution at session creation only, pipeline-enforced
   citations, pre-baked embedding model, testcontainers dropped for a compose
   test DB).
3. **Implementation:** the main agent wrote the code, with tests run inside
   the real containers at every milestone.

## Failed attempts and corrections (the honest list)

| # | Failure | How it surfaced | Fix |
|---|---|---|---|
| 1 | **Chunker regex fused blocks**: `\s*` between speaker name and timestamp matched newlines, so a paragraph line + the *next* block's `(HH:MM:SS):` parsed as one bogus header — first segments silently vanished | unit test `test_segments_carry_forward_speaker...` failed with a paragraph string where a speaker name should be | whitespace restricted to same-line `[ \t]*`; regression comment in `chunker.py` |
| 2 | **Sanitizer panic**: ammonia (nh3) aborts if a tag (`<style>`) is both allowed and in its default content-strip set | `pyo3_runtime.PanicException` in the XSS-corpus test | explicit `clean_content_tags={"script"}` |
| 3 | **asyncpg × pytest-asyncio loop mismatch**: session-scoped pool on per-test event loops → "another operation is in progress" | 8 integration tests failing | function-scoped pool fixture |
| 4 | **The big one — SSE heartbeat killed the engine**: `asyncio.wait_for(gen.__anext__(), 15)` *cancels the generator* on timeout; any model call slower than one heartbeat (i.e., every local-model call) died silently and the stream ended with an empty `done` | end-to-end curl showed `tool_use` events, one heartbeat, then an empty terminal frame; backend logs showed retrieval succeed and no model.call | rewrote `sse.py`: background task pumps engine events into a queue; heartbeat timeout applies to `queue.get()` only. Regression test pins it (`test_slow_event_survives_heartbeats`) |
| 5 | **qwen3:4b unusable on the target hardware**: measured ~4.5 tok/s with reasoning preambles leaking into content despite `think:false`; server logs showed 1,267 generated tokens for a "say hello" prompt | direct Ollama probing + `print_timing` server logs | default switched to `llama3.2:3b`; `think` sent only to models that accept it; local prompt slimmed (6 chunks × 1,600 chars for chat); decision documented in architecture.md#local-model-choice |
| 6 | **Ollama error lines swallowed**: `/api/chat` can return HTTP 200 whose stream carries `{"error": ...}`; the parser ignored unknown lines → silent empty replies | discovered while diagnosing #4 | error lines now raise and surface as typed `ollama_unreachable` error frames |
| 7 | **First model pull silently failed** (network); a later health probe caught the missing model | `/health/ready` reported `ollama reachable but model not pulled` — the check exists precisely for this | re-pull; `scripts/demo.sh` verifies the model on every start |
| 8 | **8 GB memory pressure**: running ingestion (ONNX embedding) concurrently with model load thrashed the machine; Postgres briefly entered crash recovery | ingest CLI died with `CannotConnectNowError`; `memory_pressure` at 16% free | ingest is hash-idempotent so re-running resumed cleanly; README warns against concurrent ingest + inference on small machines; memory budget table in architecture.md |

| 9 | **Citation markers flaky at temperature 0.7**: on the flagship demo prompt the 3B model produced a well-grounded answer but skipped every [n] marker → zero chips + a misleading "no sources" notice | user's first real browser session | chat temperature lowered to 0.3 (markers now emitted reliably: 6/6/6 across repeat runs, latency 44s → 11s warm) + a deterministic backstop that cites retrieved chunks whose guest is explicitly named in the answer — still database-truth, never fabricable |

## Adversarial review round (pre-submission test fleet)

Before submitting, a fleet of subagents audited the repo, adversarially
reviewed the backend, and ran live API/UI tests. What they found and how it was
fixed (all verified live afterward):

| # | Severity | Finding | Fix + verification |
|---|---|---|---|
| 10 | CRITICAL | `scripts/demo.sh` still defaulted to the old `qwen3:4b` when no `.env` existed → a fresh evaluator's `make demo` pulls the wrong model and every local chat fails | one-line default → `llama3.2:3b`, kept in sync with config.py |
| 11 | CRITICAL | Assistant reply **lost on client disconnect / Stop**, and even on a clean stream (persistence ran *after* the `done` frame was yielded) | persist when `DoneEvent` is received, *before* forwarding it, under `asyncio.shield`; `finally` saves partial content on early disconnect. Reproduced live: stream-one-token-then-disconnect now persists the full 448-char reply |
| 12 | MAJOR | Cross-turn citation misattribution on the resumed cloud engine: turn-2 markers could collide with turn-1's numbers and mislink to the wrong episode | per-session monotonic `marker_base`; a recalled stale marker now falls out of range and is safely dropped, never mislinked (unit-tested) |
| 13 | MAJOR | Artifact extractor closed at the first inner ```` ``` ```` — any essay/checklist containing a code block corrupted the artifact and leaked into chat | switched the artifact fence to four backticks (can't collide with inner 3-backtick code); prompts updated; nested-code test added |
| 14 | MAJOR | CSS exfiltration: nh3 doesn't parse CSS, so `url()`/`@import` in a `<style>` survived — contradicting the docs' "blocked" claim | second sanitizer pass strips `url()`/`@import`/`expression()`/`image-set()`; CSP `img-src` tightened to `https:`; docs corrected; XSS-corpus test extended |
| 15 | MAJOR | Persistence failure after `done` could emit a *second* terminal frame; concurrent messages to one session interleaved and forked the SDK transcript | single-terminal-frame guard in `sse.py`; per-session `asyncio.Lock` → 409 on concurrent send. Both verified live (200 + 409, never two streams) |
| 16 | MINOR | A running-but-erroring Ollama (missing model / OOM) reported the misleading "start Ollama" message | `HTTPStatusError` now mapped to a distinct `ollama_error` with the right fix |

Clean bills of health from the fleet: **no secrets anywhere in git history**, all
parameterized SQL (no injection), all deliverables present, all API contract /
error-envelope / SSE-ordering / persistence / grounded-refusal tests passing,
retrieval eval 87% hit@5. Test count after this round: **73**.

## Files

- `session-*.jsonl` — raw Claude Code session logs (tool calls, outputs,
  reasoning summaries), redacted of any tokens/keys.
