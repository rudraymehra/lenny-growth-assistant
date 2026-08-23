"""Citation enforcement: markers map to retrieved chunks only; fabricated
markers are dropped; deep links carry the timestamp."""

from app.models.domain import RetrievedChunk
from app.rag.citations import extract_citations, youtube_deep_link


def _chunk(i: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=i, episode_slug=f"ep-{i}", episode_title=f"Episode {i}",
        guest=f"Guest {i}", youtube_url="https://www.youtube.com/watch?v=abc",
        speaker="Guest", start_ts=100 * i, end_ts=100 * i + 60,
        content="Some transcript content about growth loops and retention curves.",
        score=1.0,
    )


def test_markers_map_in_first_appearance_order_and_dedupe():
    retrieved = [_chunk(1), _chunk(2), _chunk(3)]
    citations = extract_citations("Claim [2]. Another [1]. Repeat [2].", retrieved)
    assert [c.index for c in citations] == [2, 1]
    assert citations[0].episode_slug == "ep-2"


def test_fabricated_marker_is_dropped():
    citations = extract_citations("Real [1], fabricated [7].", [_chunk(1)])
    assert len(citations) == 1
    assert citations[0].index == 1


def test_same_chunk_under_two_markers_is_deduplicated():
    # cross-search duplicates: chunk retrieved twice gets indices 1 and 3
    shared = _chunk(9)
    citations = extract_citations("a [1] b [2] c [3]", [shared, _chunk(2), shared])
    assert [c.index for c in citations] == [1, 2]


def test_no_retrieval_means_no_citations():
    assert extract_citations("Confident nonsense [1] [2].", []) == []


def test_deep_link_math():
    assert youtube_deep_link("https://www.youtube.com/watch?v=abc", 90) == \
        "https://www.youtube.com/watch?v=abc&t=90"
    assert youtube_deep_link("https://youtu.be/abc", 5) == "https://youtu.be/abc?t=5"
    assert youtube_deep_link(None, 5) is None


def test_quote_is_truncated():
    citations = extract_citations("x [1]", [_chunk(1)])
    assert len(citations[0].quote) <= 221
    assert citations[0].quote.endswith("…")
