"""Auto-enqueue of authority resolution on ingest (front B) + entity_type filter.

Verifies:
  * ``_distinct_values`` / ``execute_batch_resolution`` can restrict the value
    pool to a single ``entity_type`` (author→person, affiliation→institution).
  * ``enqueue_entity_authority_jobs`` is opt-in, de-duplicated, and stamps the
    right ``entity_type_filter`` into the job params.
"""
from __future__ import annotations

import json

from backend import models
from backend.authority import auto_enqueue
from backend.authority.batch_resolution import _distinct_values, execute_batch_resolution


def _entity(db, *, label, entity_type, canonical_id, org_id=None):
    ent = models.RawEntity(
        org_id=org_id, domain="science", entity_type=entity_type,
        primary_label=label, canonical_id=canonical_id,
        attributes_json="{}", validation_status="derived",
        enrichment_status="derived", source="graph_materializer",
    )
    db.add(ent)
    db.flush()
    return ent


# ── entity_type filtering ─────────────────────────────────────────────────────

def test_distinct_values_filters_by_entity_type(db_session):
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    _entity(db_session, label="Open Lab", entity_type="affiliation", canonical_id="affiliation:ol")
    _entity(db_session, label="Some Paper", entity_type="work", canonical_id="doi:10.1/x")
    db_session.flush()

    authors = _distinct_values(db_session, "primary_label", None, entity_type_filter="author")
    affils = _distinct_values(db_session, "primary_label", None, entity_type_filter="affiliation")

    assert "Ada Lovelace" in authors
    assert "Open Lab" not in authors
    assert "Some Paper" not in authors
    assert affils == ["Open Lab"]


def test_batch_resolution_respects_entity_type_filter(db_session):
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    _entity(db_session, label="Grace Hopper", entity_type="work", canonical_id="doi:10.1/g")
    db_session.flush()

    seen: list[str] = []

    def _fake_resolve(value, entity_type, ctx):
        seen.append(value)
        return []

    summary, _ = execute_batch_resolution(
        db_session, org_id=None, record_org_id=None, field="primary_label",
        entity_type="person", limit=100, skip_existing=False,
        resolve_fn=_fake_resolve, entity_type_filter="author",
    )

    assert seen == ["Ada Lovelace"]  # the 'work' row was excluded
    assert summary["resolved_count"] == 1


# ── enqueue behavior ──────────────────────────────────────────────────────────

def test_enqueue_disabled_by_default(db_session, monkeypatch):
    monkeypatch.delenv("UKIP_AUTO_RESOLVE_ON_INGEST", raising=False)
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    db_session.flush()

    created = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)

    assert created == []
    assert db_session.query(models.AuthorityResolveJob).count() == 0


def test_enqueue_creates_two_jobs_when_enabled(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    db_session.flush()

    created = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)

    assert len(created) == 2
    jobs = db_session.query(models.AuthorityResolveJob).all()
    by_type = {j.entity_type: j for j in jobs}
    assert set(by_type) == {"person", "institution"}
    assert json.loads(by_type["person"].params_json)["entity_type_filter"] == "author"
    assert json.loads(by_type["institution"].params_json)["entity_type_filter"] == "affiliation"
    assert json.loads(by_type["person"].params_json)["skip_existing"] is True


def test_enqueue_is_deduplicated(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_AUTO_RESOLVE_ON_INGEST", "1")
    _entity(db_session, label="Ada Lovelace", entity_type="author", canonical_id="author:ada")
    db_session.flush()

    first = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)
    second = auto_enqueue.enqueue_entity_authority_jobs(db_session, org_id=None)

    assert len(first) == 2
    assert second == []  # open jobs already exist → no duplicates
    assert db_session.query(models.AuthorityResolveJob).count() == 2
