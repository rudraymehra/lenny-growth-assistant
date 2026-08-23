# Demo video script (2–3 minutes, camera on)

Record with the stack already running (`make demo` done, KB ingested, Ollama
up, **no** `ANTHROPIC_API_KEY` in `.env` so the local path is provably live —
or keep the key and show both). Have http://localhost:3000 open, plus a
terminal. Upload to YouTube (unlisted is fine), camera enabled throughout.

## 0:00–0:20 — The problem (talking head)

> "Hi, I'm Rudray. A product team wants Lenny's Podcast — 300+ episodes of the
> best product and growth practitioners — as an internal assistant. The catch:
> answers they can *verify*, content they can *reuse*, and it has to run on
> their infrastructure — including fully local. This is the Lenny Growth
> Assistant."

## 0:20–1:05 — Grounded chat on a LOCAL model (screen share)

1. Point at the header badge: **"Local · llama3.2:3b"** and the sidebar KB
   stats (303 episodes).
2. Terminal, one line: `ollama ps` → the model is running locally. Say:
   > "No cloud key configured — everything you'll see is a 3-billion-parameter
   > model on this 8-gig laptop, via Ollama."
3. Click the example prompt "What do guests say about finding product-market
   fit?" Narrate the activity line:
   > "It retrieves first — hybrid vector + full-text search over Postgres —
   > then the model answers only from those excerpts."
4. When the answer lands, click a citation chip → popover → **"Watch this
   moment"** → YouTube opens at the timestamp:
   > "Citations are enforced by the backend, not volunteered by the model — it
   > can only cite chunks retrieval actually returned. Click, and you're at
   > the exact second in the episode."

## 1:05–1:45 — The Ship 30 skill + artifact viewer

5. Send: **"Write a Ship 30 essay about improving activation."**
   While it generates:
   > "The Ship 30 writing system — one-sentence hook, 1-3-1 rhythm, subheads,
   > a TL;DR takeaway — is encoded as a real skill file. The Claude engine
   > loads it as an Agent SDK skill; the local engine compiles the same file
   > into its prompt. One source of truth, two model classes."
6. The essay opens in the artifact viewer. Scroll it; flip to **Source** tab:
   > "Artifacts render beside the chat. Generated HTML is treated as untrusted
   > — server-side allowlist sanitization, then a fully sandboxed iframe with
   > a no-network CSP. The Source tab shows exactly what the sanitizer saw."

## 1:45–2:20 — The trade-off (talking head or screen)

7. > "One technical trade-off worth explaining: the two providers get
   > *different control flow*. Claude runs a real agentic loop — Agent SDK,
   > custom MCP tools, it decides when to search. The local 3B model doesn't
   > get tools at all: it gets a deterministic pipeline — always retrieve,
   > then generate, citations and artifacts enforced by the backend. Small
   > models are unreliable tool-callers, so the big model gets agency and the
   > small one gets rails — same interface, same product, and the provider is
   > pinned per session so you always know which model said what, and what it
   > cost."

## 2:20–2:45 — Ops close

8. Terminal: `make test` (62 green), then `make eval` scrolling the hit@5
   table:
   > "Retrieval quality is measured, not assumed — a golden set gates at 80%
   > hit-at-5. One command boots the whole stack; structured JSON logs trace
   > every request id from browser to database. Handoff docs — PRD,
   > architecture, design, test plan — are in the repo. Thanks!"

## Recording checklist

- [ ] Camera on, mic OK, 1080p+ screen capture
- [ ] KB ingested (sidebar shows 303 episodes) BEFORE recording
- [ ] Model pre-warmed: send one throwaway message first (`ollama ps` shows it
      loaded) so the demo isn't waiting on model load
- [ ] Close other apps (8 GB machine — keep tokens/sec up)
- [ ] `.env` has no real key visible on screen at any point
- [ ] Under 3:00 total
