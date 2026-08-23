# design.md — UI/UX

## Principles

1. **Trust is the product.** Every design choice makes verifiability visible:
   citation chips under grounded answers, an amber notice on ungrounded ones,
   the provider badge always in view, dollar cost on every cloud message.
   The user should never wonder "which model said this, and can I check it?"
2. **States are legible.** Waiting on a local model can take tens of seconds —
   the UI narrates what's happening ("search_transcripts: 8 excerpts
   retrieved") instead of showing a bare spinner, and every failure mode has a
   designed state with a next step, not a dead end.
3. **Artifacts live beside the conversation,** not inside it. The chat stays
   scannable; documents get a dedicated pane with room to render properly.
4. **Calm surface.** One accent color (indigo), one font (system stack),
   generous whitespace. The content — answers, quotes, essays — is the visual
   hierarchy; chrome stays quiet.

## Information architecture

```
Header........... identity + active session's provider/model badge + provider readiness
Sidebar (264px).. new chat (default / ☁ Claude / 💻 Local), session list
                  (title, provider glyph, model, message count), KB stats footer
Chat pane........ message thread, streaming draft, activity notes, failure banners
Composer......... textarea (Enter=send, Shift+Enter=newline), Stop while
                  streaming, example prompts as affordance
Artifact panel... 46% width on demand: Preview | Source tabs, close button
```

## Key interaction states

| State | Treatment |
|---|---|
| First run / empty session | welcome card + four one-click example prompts covering all three capabilities (Q&A, essay, artifact) |
| Streaming, pre-token | bouncing dots + latest tool activity line ("search_transcripts: …") |
| Streaming, tokens | assistant bubble grows in place; markdown renders live |
| Grounded answer | "Sources" row of citation chips: `[n] guest · timestamp`; click → popover with episode title, quote, ▶ YouTube deep link (opens at the cited second) |
| Ungrounded answer | amber "No transcript sources were cited" notice inside the bubble |
| Artifact created | tappable artifact card in the message + the viewer auto-opens |
| Stream failure | red banner naming the error code in plain words, the fix, and — when recoverable — a one-click "start a new chat on the local model" |
| No provider at all | full-pane setup card with copy-pasteable commands for both fixes |
| Cost/latency | 11px footer per assistant message: model · seconds · tokens · $ (or "$0.00 (local)") |

## Responsive behavior

- ≥1024px: sidebar + chat + (optional) artifact panel side by side.
- <1024px: artifact panel overlays the chat full-width with a shadow (chat
  state preserved beneath; ✕ returns).
- <768px: sidebar hidden (the demo targets desktop; sessions remain reachable
  by URL-free single-column flow — documented limitation rather than a
  half-built drawer).

## Accessibility

- Full keyboard path: Tab reaches sessions, example prompts, chips, tabs,
  composer; Enter sends; popovers are buttons with `aria-expanded`.
- Roles/labels: `role="alert"` on failure banners, `role="dialog"` on citation
  popovers, `role="tablist"` in the viewer, `aria-label` on icon-only buttons,
  iframe `title` describes the artifact.
- Color is never the only signal (provider badge pairs glyph + text; notices
  pair color + copy). Indigo-on-white and slate text meet WCAG AA contrast.
- Streaming updates append to the DOM (screen readers see stable content, not
  churn); the activity line is text, not animation alone.

## Design decisions worth defending

- **Chips, not footnotes.** Citations are the product's proof; burying them in
  a footnote list undersells the core value. Chips keep them one glance away
  without breaking reading flow.
- **Provider pinned per session, chooser only at creation.** Mid-session model
  switching invites "which model wrote message 7?" ambiguity — resolution at
  creation keeps every message attributable.
- **Essays go to the artifact pane** (not the chat) because 1,250 words in a
  bubble destroys the conversation's scannability; the chat gets a 2-sentence
  summary, the pane gets typography-friendly rendering.
- **Example prompts over onboarding copy.** Four buttons teach the entire
  capability surface faster than a paragraph nobody reads.
