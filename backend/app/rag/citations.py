"""Citation enforcement: the model only ever writes inline [n] markers; this
module maps those markers back to the chunks that were actually retrieved and
builds Citation objects (with YouTube deep links) from database truth. A
marker with no matching retrieved chunk is dropped and logged — the model
cannot fabricate a source."""

import re

from app.logging import EVT_CITATION_UNMATCHED, get_logger
from app.models.domain import Citation, RetrievedChunk

log = get_logger(__name__)

_MARKER = re.compile(r"\[(\d{1,2})\]")
_QUOTE_CHARS = 220


def youtube_deep_link(url: str | None, ts_seconds: int) -> str | None:
    if not url:
        return None
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}t={ts_seconds}"


def citation_for(index: int, chunk: RetrievedChunk) -> Citation:
    return Citation(
        index=index,
        episode_slug=chunk.episode_slug,
        episode_title=chunk.episode_title,
        guest=chunk.guest,
        ts_seconds=chunk.start_ts,
        youtube_url=youtube_deep_link(chunk.youtube_url, chunk.start_ts),
        quote=chunk.content[:_QUOTE_CHARS].rsplit(" ", 1)[0] + "…",
    )


def extract_citations(text: str, retrieved: list[RetrievedChunk]) -> list[Citation]:
    """Map [n] markers in model output to citations. n is 1-based into the
    retrieved-chunk list, in retrieval order. Deduplicated, ordered by first
    appearance; unmatched markers are dropped and logged."""
    citations: list[Citation] = []
    seen: set[int] = set()
    for m in _MARKER.finditer(text):
        n = int(m.group(1))
        if n in seen:
            continue
        seen.add(n)
        if 1 <= n <= len(retrieved):
            citations.append(citation_for(n, retrieved[n - 1]))
        else:
            log.warning(EVT_CITATION_UNMATCHED, marker=n, retrieved_count=len(retrieved))
    return citations
