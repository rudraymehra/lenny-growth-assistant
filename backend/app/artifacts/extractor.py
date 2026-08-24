"""Streaming-safe extraction of four-backtick ````artifact:*```` fenced blocks.

The local engine asks the model to put generated documents inside a
FOUR-backtick fence:

    ````artifact:markdown title="My Title"
    ...content, which may itself contain ```code``` blocks...
    ````

Four backticks (not three) are used deliberately so a document that contains
ordinary three-backtick code blocks — checklists, templates, essays with
examples — cannot accidentally close the artifact fence early.

This filter consumes stream deltas and (a) suppresses fence content from the
visible chat text, (b) captures each block as an ExtractedArtifact. Because a
fence marker can be split across two stream chunks, the filter holds back a
small tail of un-emitted text until it can rule out a fence start.
"""

import re
from dataclasses import dataclass

_OPEN = re.compile(r"````artifact:(markdown|html)(?:[ \t]+title=\"([^\"\n]{0,150})\")?[ \t]*\n")
_CLOSE = re.compile(r"\n````[ \t]*(?:\n|$)")
# Longest prefix we might need to hold back to detect a split fence marker.
_HOLDBACK = 200


@dataclass
class ExtractedArtifact:
    kind: str  # "markdown" | "html"
    title: str
    content: str


class ArtifactStreamFilter:
    def __init__(self) -> None:
        self._buf = ""
        self._in_fence = False
        self._current: ExtractedArtifact | None = None
        self.artifacts: list[ExtractedArtifact] = []

    def feed(self, delta: str) -> str:
        """Consume a stream delta, return text safe to show in chat now."""
        self._buf += delta
        return self._drain(final=False)

    def flush(self) -> str:
        """Call once at end-of-stream; closes an unterminated fence."""
        out = self._drain(final=True)
        if self._in_fence and self._current is not None:
            # Model stopped mid-fence (e.g. token limit): keep what we have.
            self._current.content = self._buf.strip()
            self.artifacts.append(self._current)
            self._buf = ""
            self._in_fence = False
        remainder = "" if self._in_fence else self._buf
        self._buf = ""
        return out + remainder

    def _drain(self, final: bool) -> str:
        emitted = ""
        while True:
            if not self._in_fence:
                m = _OPEN.search(self._buf)
                if m:
                    emitted += self._buf[: m.start()]
                    self._current = ExtractedArtifact(
                        kind=m.group(1), title=m.group(2) or "", content=""
                    )
                    self._buf = self._buf[m.end():]
                    self._in_fence = True
                    continue
                # No fence: emit all but a holdback tail (a fence might be
                # arriving split across deltas), or everything when final.
                if final:
                    return emitted
                safe_len = max(0, len(self._buf) - _HOLDBACK)
                emitted += self._buf[:safe_len]
                self._buf = self._buf[safe_len:]
                return emitted
            else:
                m = _CLOSE.search(self._buf)
                if m and self._current is not None:
                    self._current.content = self._buf[: m.start()].strip()
                    self.artifacts.append(self._current)
                    self._buf = self._buf[m.end():]
                    self._in_fence = False
                    self._current = None
                    continue
                return emitted
