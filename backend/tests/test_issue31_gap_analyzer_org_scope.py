"""Issue #31 — GapAnalyzer must scope its internal queries to the active org.

Before the fix, GapAnalyzer.analyze() ran unscoped queries against RawEntity /
AuthorityRecord, so gap statistics aggregated across all tenants. These tests
pin the per-org boundary using the enrichment-coverage gap (which reports
total_count = entities visible to the caller's org).
"""
from __future__ import annotations

from uuid import uuid4

from backend import models
from backend.analyzers.gap_detector import GapAnalyzer


def _org(db) -> int:
    suffix = uuid4().hex[:8]
    owner = models.User(
        username=f"owner_{suffix}",
        password_hash="test-password-hash",
        role="admin",
        is_active=True,
    )
    db.add(owner)
    db.flush()
    org = models.Organization(
        name=f"Org {suffix}",
        slug=f"org-{suffix}",
        owner_id=owner.id,
        plan="pro",
        is_active=True,
    )
    db.add(org)
    db.flush()
    return org.id


def _entity(db, *, org_id, enriched: bool):
    db.add(
        models.RawEntity(
            org_id=org_id,
            primary_label=f"E-{uuid4().hex[:6]}",
            domain="default",
            entity_type="paper",
            source="test",
            validation_status="confirmed",
            enrichment_status="completed" if enriched else "pending",
            attributes_json="{}",
        )
    )


def _enrichment_gap(gaps):
    return next((g for g in gaps if g.category == "enrichment"), None)


def test_gap_analyzer_counts_only_active_org(db_session):
    org_a = _org(db_session)
    org_b = _org(db_session)

    # Org A: 3 entities (1 pending). Org B: 5 entities (all pending).
    _entity(db_session, org_id=org_a, enriched=True)
    _entity(db_session, org_id=org_a, enriched=True)
    _entity(db_session, org_id=org_a, enriched=False)
    for _ in range(5):
        _entity(db_session, org_id=org_b, enriched=False)
    db_session.commit()

    gaps_a = GapAnalyzer().analyze("default", db_session, org_id=org_a)
    gap_a = _enrichment_gap(gaps_a)
    assert gap_a is not None
    # Only org A's 3 entities are visible — org B's 5 must not leak in.
    assert gap_a.total_count == 3
    assert gap_a.affected_count == 1

    gaps_b = GapAnalyzer().analyze("default", db_session, org_id=org_b)
    gap_b = _enrichment_gap(gaps_b)
    assert gap_b is not None
    assert gap_b.total_count == 5
    assert gap_b.affected_count == 5


def test_gap_analyzer_global_scope_sees_all(db_session):
    """org_id=None (super_admin global) keeps the original cross-org behavior."""
    org_a = _org(db_session)
    org_b = _org(db_session)
    _entity(db_session, org_id=org_a, enriched=False)
    _entity(db_session, org_id=org_b, enriched=False)
    db_session.commit()

    gaps = GapAnalyzer().analyze("default", db_session, org_id=None)
    gap = _enrichment_gap(gaps)
    assert gap is not None
    assert gap.total_count >= 2  # both orgs visible under global scope
