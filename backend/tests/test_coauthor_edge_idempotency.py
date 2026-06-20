"""Regression tests: re-enriching a completed work must not crash on the
``uq_entity_relationships_pair_global`` unique index.

Root cause (prod): the legacy CO_AUTHOR writer stored one self-edge row per
author pair, all keyed (id, id, CO_AUTHOR) with the pair only in ``notes``. The
unique index ignores ``notes``, so multi-pair works collided — on first write
(rows collide with each other) and on re-enrichment (collide with the existing
row), raising IntegrityError and rolling the whole enrichment back.

Fix: store ALL pairs for a work in a SINGLE (id, id, CO_AUTHOR) row (newline-
joined ``notes``), upserted idempotently. These tests recreate the prod indexes
so the regression is actually exercised, and drop them afterward (the test
engine is a shared StaticPool in-memory DB).
"""
import json

import pytest
from sqlalchemy import text

from backend import models
from backend.analyzers.coauthorship import extract_coauthor_edges, coauthorship_network


@pytest.fixture
def prod_unique_indexes(db_session):
    """Mirror eng1prereq00001's partial unique indexes, then drop them so the
    shared in-memory engine is left clean for other tests."""
    db_session.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relationships_pair_global "
        "ON entity_relationships (source_id, target_id, relation_type) WHERE org_id IS NULL"
    ))
    db_session.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relationships_pair "
        "ON entity_relationships (org_id, source_id, target_id, relation_type) WHERE org_id IS NOT NULL"
    ))
    db_session.commit()
    try:
        yield
    finally:
        db_session.rollback()
        db_session.execute(text("DROP INDEX IF EXISTS uq_entity_relationships_pair_global"))
        db_session.execute(text("DROP INDEX IF EXISTS uq_entity_relationships_pair"))
        db_session.commit()


def _work(db_session, domain="science", org_id=None):
    e = models.RawEntity(primary_label="Multi-author paper", domain=domain,
                         enrichment_status="completed", org_id=org_id)
    db_session.add(e)
    db_session.commit()
    return e


def test_multi_author_writes_single_row(db_session, prod_unique_indexes):
    """3 authors → 3 pairs → ONE consolidated row (no collision under the index)."""
    e = _work(db_session)
    count = extract_coauthor_edges(e.id, ["Alice", "Bob", "Carol"], db_session, org_id=None)
    db_session.commit()

    assert count == 3
    rows = (db_session.query(models.EntityRelationship)
            .filter_by(relation_type="CO_AUTHOR", source_id=e.id).all())
    assert len(rows) == 1
    notes = rows[0].notes
    assert "Alice||Bob" in notes
    assert "Alice||Carol" in notes
    assert "Bob||Carol" in notes


def test_reenrichment_is_idempotent(db_session, prod_unique_indexes):
    """Re-running on the same work must NOT raise and must NOT duplicate rows.

    This is the exact prod failure (UniqueViolation on the second write)."""
    e = _work(db_session)
    extract_coauthor_edges(e.id, ["Alice", "Bob", "Carol"], db_session, org_id=None)
    db_session.commit()
    # Second pass — previously raised IntegrityError here.
    extract_coauthor_edges(e.id, ["Alice", "Bob", "Carol"], db_session, org_id=None)
    db_session.commit()

    rows = (db_session.query(models.EntityRelationship)
            .filter_by(relation_type="CO_AUTHOR", source_id=e.id).all())
    assert len(rows) == 1


def test_reenrichment_refreshes_pairs(db_session, prod_unique_indexes):
    """A changed author list replaces the stored pairs (no stale accumulation)."""
    e = _work(db_session)
    extract_coauthor_edges(e.id, ["Alice", "Bob"], db_session, org_id=None)
    db_session.commit()
    extract_coauthor_edges(e.id, ["Alice", "Bob", "Carol"], db_session, org_id=None)
    db_session.commit()

    rows = (db_session.query(models.EntityRelationship)
            .filter_by(relation_type="CO_AUTHOR", source_id=e.id).all())
    assert len(rows) == 1
    assert "Bob||Carol" in rows[0].notes


def test_org_scoped_work_writes_single_row(db_session, prod_unique_indexes):
    """The org-scoped index (org_id IS NOT NULL) path must also stay collision-free."""
    e = _work(db_session, org_id=7)
    extract_coauthor_edges(e.id, ["Alice", "Bob", "Carol"], db_session, org_id=7)
    db_session.commit()
    extract_coauthor_edges(e.id, ["Alice", "Bob", "Carol"], db_session, org_id=7)
    db_session.commit()

    rows = (db_session.query(models.EntityRelationship)
            .filter_by(relation_type="CO_AUTHOR", source_id=e.id).all())
    assert len(rows) == 1


def test_network_reads_all_pairs_from_consolidated_row(db_session):
    """The analyzer must reconstruct every pair from the single multi-pair row."""
    e = _work(db_session, domain="__coauth_consolidated__")
    extract_coauthor_edges(e.id, ["Alice", "Bob", "Carol"], db_session, org_id=None)
    db_session.commit()

    result = coauthorship_network("__coauth_consolidated__")
    names = {n["id"] for n in result["nodes"]}
    assert names == {"Alice", "Bob", "Carol"}
    assert len(result["edges"]) == 3


def test_enrich_single_record_twice_succeeds(db_session, monkeypatch, prod_unique_indexes):
    """End-to-end: enriching the same work twice must both complete (prod crashed
    on the second run inside the co-author commit)."""
    from backend import enrichment_worker
    from backend.enrichment_worker import EnrichmentStatus
    from backend.schemas_enrichment import EnrichedRecord

    entity = models.RawEntity(primary_label="Tara Oceans", domain="science",
                              enrichment_status="pending", org_id=None)
    db_session.add(entity)
    db_session.commit()

    enriched = EnrichedRecord(title="Tara Oceans", citation_count=3,
                              authors=["Alice", "Bob", "Carol"])
    monkeypatch.setattr(enrichment_worker, "_ACTIVE_CASCADE", ["openalex"])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "search_by_title",
                        lambda query, limit=1: [enriched])

    enrichment_worker.enrich_single_record(db_session, entity)
    db_session.refresh(entity)
    assert entity.enrichment_status == EnrichmentStatus.completed

    # Re-run — must not raise and must stay completed.
    entity.enrichment_status = "pending"
    db_session.commit()
    enrichment_worker.enrich_single_record(db_session, entity)
    db_session.refresh(entity)
    assert entity.enrichment_status == EnrichmentStatus.completed

    rows = (db_session.query(models.EntityRelationship)
            .filter_by(relation_type="CO_AUTHOR", source_id=entity.id).all())
    assert len(rows) == 1
