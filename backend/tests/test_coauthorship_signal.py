"""Tests for the coauthorship scoring signal (Phase 2, Task 7)."""
from backend.authority.scoring import compute_score


def _score(**kw):
    base = dict(
        value="J Smith",
        authority_source="openalex",
        authority_id="A1",
        canonical_label="John Smith",
        description="MIT",
    )
    base.update(kw)
    return compute_score(**base)[0]


def test_coauthorship_boosts_score_for_shared_collaborators():
    high = _score(coauthors_overlap=0.8)
    low = _score(coauthors_overlap=0.0)
    assert high > low


def test_absent_overlap_matches_legacy_behavior():
    # When overlap is not supplied, the coauthorship weight is 0 and the score
    # equals the legacy score (no coauthorship contribution).
    legacy = _score()
    none_overlap = _score(coauthors_overlap=None)
    assert legacy == none_overlap


def test_overlap_recorded_in_breakdown():
    _total, breakdown, _evidence, _status = compute_score(
        value="J Smith",
        authority_source="openalex",
        authority_id="A1",
        canonical_label="John Smith",
        description="MIT",
        coauthors_overlap=0.5,
    )
    assert breakdown["coauthorship"] == 0.5
