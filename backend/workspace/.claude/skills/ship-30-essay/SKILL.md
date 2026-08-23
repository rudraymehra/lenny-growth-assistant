---
name: ship-30-essay
description: Write a ~1,250-word Ship 30 for 30-style essay on a product/growth topic, grounded in Lenny's Podcast transcripts. Use when the user asks for an essay, article, long-form post, or "Ship 30" content.
---

# Ship 30 for 30 Essay Skill

Write a ~1,250-word essay (1,150–1,350 acceptable) following the Ship 30 for 30
digital-writing system (Dickie Bush & Nicolas Cole). Every claim about product
or growth must be grounded in retrieved Lenny's Podcast transcript chunks and
carry an inline citation marker [n] referencing those chunks.

## Before writing

1. Retrieve transcript material on the topic (search 2–3 angles: the concept,
   named guests who discuss it, concrete tactics).
2. Pick ONE idea for the essay and ONE of the 4 A's as its direction:
   Actionable (here's how) / Analytical (here are the numbers) /
   Aspirational (yes, you can) / Anthropological (here's why people behave this way).
3. Collect 2–3 specific guest stories or quotes — the "Golden Intersection":
   readers come for actionable advice but stay for personal stories.

## Headline

- Encode as many as fit naturally: WHO it's for, WHAT it delivers, a NUMBER,
  the outcome/PROMISE. Clear beats clever, always.
- Use a curiosity gap: reveal the beginning and the end of the story, not the middle.
- Proven shapes: "N Things/Lessons/Mistakes…", "How [specific person] did X",
  "The [adjective] Guide to X for [audience]".

## Opening

- The hook is EXACTLY ONE sentence, standing alone as its own paragraph.
  Choose one pattern: strong declarative statement / thought-provoking question /
  controversial opinion / moment-in-time / vulnerable admission / surprising stat.
- Then a short intro: state the outcome, admit the humble beginning, promise
  what the middle will show.

## Body

- 4–6 bolded or `##` subheads, one every ~150–250 words. Under each subhead,
  anything listable becomes a bulleted list; bold the key phrases (selective —
  if everything is bold, nothing is).
- Paragraph rhythm: the 1/3/1 rule — a 1-sentence opener, a 3-sentence block
  that builds the point, a 1-sentence punch. Vary with 1/4/1 or 1/5/1; never
  write uniform walls of text.
- Rate of Revelation: every sentence must add something new. If a sentence
  repeats an earlier idea, cut it.
- Ground every substantive claim in the transcripts with [n] markers, and name
  the guest when using their story ("As Brian Chesky puts it [2]…").

## Editing rules

- Cut "that", "very", "I think/I believe", and -ly adverbs (use stronger verbs).
- Put the most important word at the end of the sentence.
- Short words, short sentences, concrete nouns.

## Ending

- A "TL;DR" or "The takeaway" section: 3–5 bullet recap of the core points.
- Close with ONE specific, immediately-usable action for the reader.
- The final line is a single sentence that mirrors the hook.

## Output

Emit the finished essay as a markdown artifact titled with the essay headline
(via the save_artifact tool when available, otherwise inside an
```artifact:markdown``` fenced block). In the chat reply itself, give a 1–2
sentence summary of the essay and its sources — never paste the full essay
into the chat.
