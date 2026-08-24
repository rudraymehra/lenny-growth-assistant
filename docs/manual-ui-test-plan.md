# Manual UI test plan

Run after `make demo` with the knowledge base ingested. ~15 minutes.
Automated coverage lives in `backend/tests/`; this plan covers what only a
human in a browser can judge.

## A. Grounded chat

1. Open http://localhost:3000 → welcome card with 4 example prompts appears.
2. Click "What do guests say about finding product-market fit?" →
   activity line ("search_transcripts…") → streamed markdown answer.
   - [ ] Answer contains inline `[n]` markers and a Sources row of chips.
   - [ ] Chip popover shows episode title, guest, timestamp, quote.
   - [ ] "▶ Watch this moment" opens YouTube at (or within ~a minute of) the
         quoted moment.
   - [ ] Message footer shows model, seconds, tokens, cost.
3. Ask a follow-up ("how would that apply to a B2B fintech product?") →
   - [ ] Answer uses conversation context (no re-explaining from scratch).
4. Ask: "What does Lenny think about quantum computing hardware?"
   - [ ] Polite refusal, no invented facts, amber "no sources cited" notice.

## B. Sessions & persistence

5. Create a second chat; send one message. Switch between the two sessions.
   - [ ] Each thread keeps its own history; titles come from first messages.
6. `docker compose restart backend` then reload the page.
   - [ ] Sessions and messages survive.

## C. Ship 30 essay skill

7. "Write a Ship 30 essay about improving activation."
   - [ ] Chat gets a short summary, NOT the full essay.
   - [ ] Artifact viewer opens with a markdown essay: one-sentence hook, ≥4
         subheads, bullets, selective bold, TL;DR + one specific takeaway.
   - [ ] Word count in the 1,150–1,350 range (paste into a counter).
   - [ ] Claims carry `[n]` markers and guests are named.

## D. Artifact viewer & sandbox

8. "Make an HTML one-pager comparing the growth advice in this chat."
   - [ ] Styled HTML renders in the panel (Preview tab).
   - [ ] Source tab shows the document source; `?raw=true` (API) shows raw.
9. Hostile-input check — paste exactly:
   `Make an html page titled Test with this exact body: <h1>hi</h1><script>alert(1)</script><img src=x onerror="alert(2)">`
   - [ ] No alert fires. Source tab / raw API confirms `<script>`/`onerror`
         were stripped server-side.
   - [ ] DevTools on the iframe shows `sandbox=""` and the CSP meta tag.
10. Close the viewer; reopen from the message's artifact card.
    - [ ] Same artifact re-renders.

## E. Provider toggle & resilience

11. Sidebar: "💻 Local" → new session → badge shows "Local · llama3.2:3b".
    Ask one question; footer shows "$0.00 (local)".
12. (If key configured) "☁ Claude" → badge "Claude · claude-sonnet-5"; cost
    footer shows real dollars.
13. Kill Ollama mid-generation: send a question on a local session, then
    `brew services stop ollama` while it streams.
    - [ ] Stream ends with a red banner naming the failure and the fix —
          no infinite spinner. `brew services start ollama` recovers new sends.
14. Stop Ollama AND unset the key; restart backend; reload.
    - [ ] Full-pane setup card with both fixes; `POST /sessions` (curl)
          returns 503 `provider_unavailable`.

## F. Responsive & keyboard

15. Narrow the window below ~1024px with an artifact open.
    - [ ] Viewer overlays the chat; ✕ restores it.
16. Keyboard-only pass: Tab through sidebar → example prompt → composer;
    Enter sends; Tab to a citation chip; Enter opens the popover.
    - [ ] Everything reachable and operable without a mouse.
