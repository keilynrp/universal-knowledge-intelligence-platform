"""Tests for the coauthorship overlap adapter (Phase 2, Task 7)."""
from backend.authority.coauthorship_signal import (
    compute_candidate_overlap,
    jaccard_overlap,
)


def test_jaccard_basic():
    assert jaccard_overlap(["a", "b", "c"], ["b", "c", "d"]) == 0.5  # 2 / 4


def test_jaccard_identical():
    assert jaccard_overlap(["x", "y"], ["y", "x"]) == 1.0


def test_jaccard_disjoint():
    assert jaccard_overlap(["a"], ["b"]) == 0.0


def test_jaccard_empty_is_zero():
    assert jaccard_overlap([], ["a"]) == 0.0
    assert jaccard_overlap([], []) == 0.0


def test_jaccard_is_normalization_insensitive():
    # Case/whitespace differences should not break the overlap.
    assert jaccard_overlap(["John  Smith"], ["john smith"]) == 1.0


def test_candidate_overlap_none_when_no_query_coauthors():
    assert compute_candidate_overlap(None, ["Alice"]) is None
    assert compute_candidate_overlap([], ["Alice"]) is None


def test_candidate_overlap_none_when_candidate_has_no_coauthors():
    assert compute_candidate_overlap(["Alice"], []) is None


def test_candidate_overlap_value():
    # {alice,bob} ∩ {bob,carol} = {bob}; union = 3 → 1/3
    assert compute_candidate_overlap(["Alice", "Bob"], ["Bob", "Carol"]) == 1 / 3
