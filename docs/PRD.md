# PRD — The Lenny Growth Assistant

## 1. Forward Deployment Brief

### User and problem

**Primary user:** product managers and growth leads on a product & growth
team who already trust Lenny's Podcast as a knowledge source.

**Job to be done:** "When I face a product/growth decision (pick an activation
metric, structure a growth team, position against a competitor), get me what
the best practitioners actually said about it — fast, verifiable, and in a
form I can reuse."

**Pain removed:** today that job means remembering *which* of 300+ episodes
covered the topic, scrubbing through hours of video, and manually reworking
notes into shareable content. Generic chatbots answer instantly but
unverifiably — for internal decision-making, an answer you can't trace to a
source is a liability, not an asset. The assistant removes both pains at once:
grounded answers with jump-to-the-moment YouTube citations, plus one-step
conversion into essays and shareable artifacts.

### Success metrics

Product (primary):
- **Groundedness:** ≥ 90% of substantive answers carry ≥ 1 verifiable citation;
  0 fabricated citations (enforced by construction — the backend only builds
  citations from actually-retrieved chunks).
- **Retrieval quality:** golden-set hit@5 ≥ 80% (measured, `make eval`;
  currently passing).

Operational (secondary):
- Local-model answer latency ≤ 60 s p90 on an 8 GB laptop; cloud ≤ 15 s p90.
- Cost visibility: 100% of cloud messages display their dollar cost in the UI.

### Assumptions (client brief was incomplete)

1. **Internal tool, trusted users** → no auth/user accounts in v1; the
   `sessions.user_metadata` JSONB column is the hook for identity later.
2. **The ChatPRD transcript archive** (303 episodes) is the intended corpus —
   it's the largest free, complete, consistently-formatted set. Educational
   use only; not for commercial redistribution.
3. **Freshness cadence is low** (a new episode a week) → re-running the
   idempotent ingest CLI is sufficient; no scheduler/webhook in v1.
4. **"Local demo" means genuinely local** → embeddings also run in-process
   (fastembed ONNX), so retrieval works with zero cloud dependencies.
5. **English-only**, matching the corpus.
6. Evaluators run macOS or Linux with Docker; macOS runs Ollama natively
   (GPU), Linux can use the provided compose profile.

### Scope choices

**In:** grounded chat with citations & refusal behaviour; multi-session
persistence; cloud + local providers behind one interface, switchable without
code changes; Ship 30 essay skill (real SKILL.md, both engines); markdown +
sandboxed HTML artifacts with an in-app viewer; one-command startup;
structured logs; automated tests + retrieval eval; full handoff docs.

**Out (deliberately), and why:**
- Auth/multi-tenancy — internal tool; JSONB hook preserved.
- Conversation branching/regeneration, message editing — polish, not proof.
- Automatic transcript refresh scheduling — `make ingest` is one command.
- Essay-quality LLM-judge evals — retrieval eval gives the highest
  signal-per-hour; judge evals are the documented next step.
- Streaming token-by-token from the Agent SDK (it yields whole blocks) —
  the UI's activity indicators cover perceived latency.
- Voice, mobile apps, export-to-Notion, etc.

### Risks and trade-offs

| Risk | Mitigation |
|---|---|
| **Hallucination** | retrieval-first prompts; backend-enforced citations (fabricated markers are dropped + logged); explicit refusal instruction; zero-citation answers visibly flagged in UI |
| **Local model quality** (3–4B) | deterministic pipeline instead of agentic tool use; retrieval before generation; compact prompts; documented as the central engine asymmetry |
| **Latency on 8 GB hardware** | native Ollama (Metal), small model, `think:false`, capped context, activity indicators during generation |
| **Cost runaway (cloud)** | per-message cost in UI from `ResultMessage.total_cost_usd`; `max_turns=10`; concurrency semaphore; readiness checks never call paid APIs |
| **Unsafe artifact rendering** | two independent layers: nh3 allowlist server-side + `sandbox=""` iframe with `default-src 'none'` CSP client-side; raw vs sanitized stored for audit |
| **Data leakage** | transcripts are public content; no secrets in repo (.env only); logs contain queries but no keys |
| **Corpus availability** | ingest pinned to a known-good commit; 3 episodes vendored as test fixtures so tests never need the network |

## 2. Core flows

1. **Grounded Q&A:** new chat → ask → assistant searches transcripts → streamed
   answer with `[n]` citation chips → chip opens quote + YouTube deep link at
   the exact timestamp. Follow-ups keep session context.
2. **Honest refusal:** ask something the corpus can't support ("what's Lenny's
   view on quantum computing?") → one-paragraph refusal, no citations, amber
   "no sources cited" notice.
3. **Ship 30 essay:** "Write a Ship 30 essay on activation" → essay skill
   produces ~1,250 words (hook / 1-3-1 rhythm / subheads / TL;DR + takeaway),
   claims cited, delivered as a markdown artifact in the viewer.
4. **Artifact:** "Turn that into an HTML one-pager" → complete styled HTML
   document rendered in the sandboxed viewer beside the chat; Source tab shows
   raw vs sanitized.
5. **Provider switch:** sidebar "☁ Claude / 💻 Local" buttons pin a new session
   to a provider; the header badge always shows the active session's
   provider + model; `.env` flips the default with no code change.

## 3. Acceptance criteria

- [ ] `make demo` from a clean clone reaches a working UI with only Docker +
      Ollama installed (cloud key optional).
- [ ] Answers to corpus-covered questions include ≥ 1 citation whose YouTube
      link lands at the cited moment.
- [ ] Questions outside the corpus produce an explicit refusal with zero
      citations, visibly flagged.
- [ ] Sessions persist across `docker compose restart`; each session's
      provider/model is stamped and displayed.
- [ ] With no `ANTHROPIC_API_KEY`, all functionality works on Ollama; with no
      Ollama and no key, the UI shows setup guidance and the API returns
      structured 503s.
- [ ] Essay requests yield 1,150–1,350 words with hook, ≥ 4 subheads, bullets,
      bold emphasis, TL;DR + single takeaway, and inline citations.
- [ ] Hostile HTML in artifacts is neutralized server-side AND the viewer
      renders artifacts in a script-less sandboxed iframe.
- [ ] `make test` (56 tests) and `make eval` (hit@5 ≥ 80%) pass.
- [ ] Every failure in the resilience map (architecture.md) produces its
      documented behaviour — never a hung spinner.

## 4. Implementation plan (as executed)

M0 scaffold → M1 ingestion/retrieval → M2 cloud engine + persistence + SSE →
M3 chat UI → M4 local engine + router + provider UX → M5 essay skill +
artifacts + sanitizer + viewer → M6 hardening (error taxonomy, timeouts,
readiness) → M7 tests + golden eval → M8 docs → M9 repo/demo. Each milestone
was independently verifiable; the walking skeleton existed at M3.
