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


def test_marker_base_offsets_numbering():
    # cloud resumed turn 2: markers are numbered above earlier turns'
    retrieved = [_chunk(10), _chunk(11)]  # this turn's chunks, markers [5],[6]
    citations = extract_citations("Claim [5] and [6].", retrieved, marker_base=4)
    assert [c.episode_slug for c in citations] == ["ep-10", "ep-11"]
    assert [c.index for c in citations] == [5, 6]


def test_stale_marker_from_prior_turn_is_dropped_not_mislinked():
    # model recalls [1] from turn 1's transcript; this turn only has markers 5,6
    retrieved = [_chunk(10), _chunk(11)]
    citations = extract_citations("Recalled [1]. Fresh [5].", retrieved, marker_base=4)
    assert [c.index for c in citations] == [5]  # [1] dropped, never mislinked


def test_fallback_by_guest_names():
    from app.rag.citations import fallback_citations_by_guest

    retrieved = [_chunk(1), _chunk(2), _chunk(3)]  # guests "Guest 1..3"
    text = "Guest 2 says PMF is a spectrum. Guest 2 repeats. Guest 3 disagrees."
    citations = fallback_citations_by_guest(text, retrieved)
    # one per named guest, in retrieval order, unnamed guest 1 excluded
    assert [c.episode_slug for c in citations] == ["ep-2", "ep-3"]


def test_fallback_never_cites_unretrieved_guests():
    from app.rag.citations import fallback_citations_by_guest

    assert fallback_citations_by_guest("Brian Chesky said things.", [_chunk(1)]) == []


def test_quote_is_truncated():
    citations = extract_citations("x [1]", [_chunk(1)])
    assert len(citations[0].quote) <= 221
    assert citations[0].quote.endswith("…")
