"""RRF fusion against hand-computed scores."""

from app.rag.search import rrf_fuse


def test_item_in_both_rankings_beats_single_leg():
    # id 2: 1/(60+2) + 1/(60+1) ; id 1: 1/(60+1) ; id 3: 1/(60+2)
    fused = rrf_fuse([[1, 2], [2, 3]])
    assert fused[0] == 2
    assert fused[1] == 1  # rank 1 in one leg beats rank 2 in one leg
    assert fused[2] == 3


def test_hand_computed_scores():
    fused = rrf_fuse([[10, 20, 30], [30, 10]], k=60)
    # 10: 1/61 + 1/62 = 0.032523...; 30: 1/63 + 1/61 = 0.032266...; 20: 1/62
    assert fused == [10, 30, 20]


def test_deterministic_tie_break_by_id():
    assert rrf_fuse([[5], [7]]) == [5, 7]
    assert rrf_fuse([[7], [5]]) == [5, 7]


def test_empty_rankings():
    assert rrf_fuse([[], []]) == []
