"""Intent routing for the local engine.

A 3–4B model can't be trusted with free-form tool calling, so the local
pipeline decides deterministically what the user wants and shapes the prompt
accordingly. Cheap keyword heuristics, fully unit-tested — and when they miss,
the fallback is plain grounded chat, which is always a safe answer.
(The cloud engine doesn't use this: Claude routes via skills/tools natively.)
"""

import re
from typing import Literal

Intent = Literal["chat", "essay", "artifact_html", "artifact_markdown"]

_ESSAY = re.compile(r"\b(essay|ship\s*30|article|blog\s*post|long[- ]form)\b", re.I)
_HTML = re.compile(r"\b(html|landing\s*page|web\s*page|webpage|one[- ]pager)\b", re.I)
_MARKDOWN_DOC = re.compile(
    r"\b(checklist|template|cheat\s*sheet|study\s*guide|summary\s+doc(ument)?|"
    r"markdown\s+(doc|document|file)|write[- ]?up)\b",
    re.I,
)


def classify(user_content: str) -> Intent:
    if _ESSAY.search(user_content):
        return "essay"
    if _HTML.search(user_content):
        return "artifact_html"
    if _MARKDOWN_DOC.search(user_content):
        return "artifact_markdown"
    return "chat"
