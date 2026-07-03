"""Journal-name materialization for the science OLAP dimension (issue #102).

The OpenAlex path stored only the journal's ISSN-L on the entity
(``enrichment_issn_l``); the journal *name* lived solely in ``journal_metrics``,
so the OLAP ``journal`` dimension was empty. These tests pin:

1. the importer (``_ingest_records``) writes ``attributes_json["journal"]`` from
   the resolved JournalMetrics name, falling back to the raw venue;
2. the backfill (``backfill_science_journal``) fills existing entities from
   ``journal_metrics`` via the ISSN-L, without overwriting an existing value.
"""
from __future__ import annotations

import json
from typing import Iterable
from unittest.mock import patch

from backend import models
from backend.schemas_enrichment import EnrichedRecord, JournalMetrics
from backend.scripts import backfill_science_journal as backfill


def _attrs(entity: models.RawEntity) -> dict:
    return json.loads(entity.attributes_json or "{}")


def _ingest(db, records: Iterable[EnrichedRecord]) -> int:
    from backend.routers.api_import import _ingest_records

    return _ingest_records(db, list(records), domain="science", source="openalex", org_id=None)


# ── Importer ─────────────────────────────────────────────────────────────────


def test_importer_writes_journal_from_journal_metrics(session_factory):
    rec = EnrichedRecord(
        id="W-j1", doi="10.9001/journal-metrics", title="T", authors=["A"],
        source_api="OpenAlex", journal=JournalMetrics(display_name="Nature"),
    )
    with session_factory() as db:
        try:
            assert _ingest(db, [rec]) == 1
            entity = db.query(models.RawEntity).filter(
                models.RawEntity.enrichment_doi == rec.doi
            ).one()
            assert _attrs(entity).get("journal") == "Nature"
        finally:
            db.query(models.RawEntity).filter(
                models.RawEntity.enrichment_doi == rec.doi
            ).delete()
            db.commit()


def test_importer_falls_back_to_venue(session_factory):
    rec = EnrichedRecord(
        id="W-j2", doi="10.9001/venue-fallback", title="T", authors=["A"],
        source_api="OpenAlex", venue="Cell",
    )
    with session_factory() as db:
        try:
            assert _ingest(db, [rec]) == 1
            entity = db.query(models.RawEntity).filter(
                models.RawEntity.enrichment_doi == rec.doi
            ).one()
            assert _attrs(entity).get("journal") == "Cell"
        finally:
            db.query(models.RawEntity).filter(
                models.RawEntity.enrichment_doi == rec.doi
            ).delete()
            db.commit()


# ── Backfill ─────────────────────────────────────────────────────────────────


def _run_backfill(db_session):
    original_close = db_session.close
    db_session.close = lambda: None
    try:
        with patch.object(backfill, "SessionLocal", return_value=db_session):
            return backfill.run_backfill(dry_run=False, org_id=None, limit=None)
    finally:
        db_session.close = original_close


def test_backfill_fills_journal_from_metrics(db_session):
    entity = models.RawEntity(
        primary_label="P", domain="science",
        enrichment_issn_l="0028-0836", attributes_json="{}",
    )
    db_session.add(entity)
    db_session.add(models.JournalMetric(org_id=None, issn_l="0028-0836", display_name="Nature"))
    db_session.commit()
    entity_id = entity.id

    result = _run_backfill(db_session)

    assert result["filled"] == 1
    refreshed = db_session.query(models.RawEntity).filter_by(id=entity_id).one()
    attrs = json.loads(refreshed.attributes_json)
    assert attrs["journal"] == "Nature"
    assert attrs["_journal_backfill"]["issn_l"] == "0028-0836"


def test_backfill_does_not_overwrite_existing_journal(db_session):
    entity = models.RawEntity(
        primary_label="P", domain="science", enrichment_issn_l="0028-0836",
        attributes_json=json.dumps({"journal": "Existing Name"}),
    )
    db_session.add(entity)
    db_session.add(models.JournalMetric(org_id=None, issn_l="0028-0836", display_name="Nature"))
    db_session.commit()
    entity_id = entity.id

    result = _run_backfill(db_session)

    assert result["already_present"] == 1
    refreshed = db_session.query(models.RawEntity).filter_by(id=entity_id).one()
    assert json.loads(refreshed.attributes_json)["journal"] == "Existing Name"


def test_backfill_skips_when_no_metric(db_session):
    entity = models.RawEntity(
        primary_label="P", domain="science",
        enrichment_issn_l="9999-0000", attributes_json="{}",
    )
    db_session.add(entity)
    db_session.commit()

    result = _run_backfill(db_session)

    assert result["no_journal_metric"] >= 1
    refreshed = db_session.query(models.RawEntity).filter_by(id=entity.id).one()
    assert "journal" not in json.loads(refreshed.attributes_json)
