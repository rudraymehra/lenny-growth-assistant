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


def fallback_citations_by_guest(
    text: str, retrieved: list[RetrievedChunk], limit: int = 4
) -> list[Citation]:
    """Deterministic backstop for small local models that answer from the
    excerpts but forget the [n] markers: attach a citation for each retrieved
    chunk whose guest is explicitly named in the answer (one per guest,
    first-retrieved chunk wins). Still database-truth — a guest that wasn't
    retrieved can never be cited."""
    citations: list[Citation] = []
    cited_guests: set[str] = set()
    lowered = text.lower()
    for i, chunk in enumerate(retrieved, start=1):
        guest = chunk.guest.strip()
        if len(guest) < 4 or guest.lower() in cited_guests:
            continue
        if guest.lower() in lowered:
            cited_guests.add(guest.lower())
            citations.append(citation_for(i, chunk))
            if len(citations) >= limit:
                break
    return citations


def extract_citations(text: str, retrieved: list[RetrievedChunk]) -> list[Citation]:
    """Map [n] markers in model output to citations. n is 1-based into the
    retrieved-chunk list, in retrieval order. Deduplicated, ordered by first
    appearance; unmatched markers are dropped and logged."""
    citations: list[Citation] = []
    seen_markers: set[int] = set()
    seen_chunks: set[int] = set()  # same chunk can get two indices across searches
    for m in _MARKER.finditer(text):
        n = int(m.group(1))
        if n in seen_markers:
            continue
        seen_markers.add(n)
        if 1 <= n <= len(retrieved):
            chunk = retrieved[n - 1]
            if chunk.chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk.chunk_id)
            citations.append(citation_for(n, chunk))
        else:
            log.warning(EVT_CITATION_UNMATCHED, marker=n, retrieved_count=len(retrieved))
    return citations
