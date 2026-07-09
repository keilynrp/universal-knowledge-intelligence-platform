"""Tests for blocking + Union-Find clustering (Phase 2, Task 6).

Blocking generates candidate pairs only within shared blocks (fingerprint /
phonetic / token-prefix), compares intra-block pairs with token_sort_ratio, and
unions matches into transitive components. Results must be order-independent.
"""
from backend.clustering.blocking import cluster_values


def _norm(groups):
    return sorted(sorted(g) for g in groups)


def test_blocking_is_order_independent():
    vals = ["Univ of Texas", "University of Texas", "U. of Texas", "MIT"]
    a = cluster_values(vals, threshold=80)
    b = cluster_values(list(reversed(vals)), threshold=80)
    assert _norm(a) == _norm(b)


def test_blocking_transitive():
    groups = cluster_values(["John Smith", "J. Smith", "Smith, John"], threshold=70)
    assert any(len(g) == 3 for g in groups)


def test_singletons_are_their_own_components():
    groups = cluster_values(["Apple", "Microsoft", "Google"], threshold=90)
    assert _norm(groups) == [["Apple"], ["Google"], ["Microsoft"]]


def test_empty_input_returns_empty():
    assert cluster_values([], threshold=80) == []


def test_build_groups_uses_blocking_when_flag_on(db_session, monkeypatch):
    """Integration: _build_disambig_groups honors UKIP_USE_BLOCKING."""
    from backend import models
    from backend.routers.deps import _build_disambig_groups

    for label in ["Acme Corporation", "Acme corporation", "ACME Corporation ", "Distinct Co"]:
        db_session.add(models.RawEntity(primary_label=label))
    db_session.commit()

    monkeypatch.setenv("UKIP_USE_BLOCKING", "1")
    groups = _build_disambig_groups("primary_label", 80, db_session, algorithm="token_sort")
    assert any(g["algorithm_used"] == "token_sort+blocking" for g in groups)
    # The three Acme variants collapse into one group.
    assert any(g["count"] >= 3 for g in groups)


def test_legacy_token_sort_does_not_truncate_large_group(db_session, monkeypatch):
    """Legacy greedy token_sort path must not cap a group at the old limit of 50."""
    from backend import models
    from backend.routers.deps import _build_disambig_groups

    # 60 distinct variants that all share 3 of 4 tokens → token_sort_ratio well
    # above the threshold, so they belong to a single group.
    for i in range(60):
        db_session.add(models.RawEntity(primary_label=f"Acme Corporation Branch {i:03d}"))
    db_session.commit()

    monkeypatch.setenv("UKIP_USE_BLOCKING", "0")
    groups = _build_disambig_groups("primary_label", 60, db_session, algorithm="token_sort")
    assert any(g["algorithm_used"] == "token_sort" for g in groups)
    # Old code capped extract() at limit=50; the fix returns all 60 variants.
    assert max(g["count"] for g in groups) > 50
