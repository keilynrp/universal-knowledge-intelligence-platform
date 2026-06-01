"""Tests for dedup_entities script and _dedup_before_insert import guard."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from backend import models
from backend.scripts import dedup_entities as dedup
from backend.routers.ingest_helpers import _dedup_before_insert


# ── Helpers ──────────────────────────────────────────────────────────────────


def _seed(db, **kwargs):
    entity = models.RawEntity(**kwargs)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# ── dedup_entities script ────────────────────────────────────────────────────


class TestDedupScript:

    def test_wrong_doi_is_cleared(self, db_session):
        winner = _seed(
            db_session,
            primary_label="Real Paper Title",
            domain="science",
            canonical_id="10.1000/real",
            entity_type="publication",
            enrichment_doi="10.1000/real",
            enrichment_source="openalex",
        )
        wrong = _seed(
            db_session,
            primary_label="Completely Different Paper",
            domain="science",
            canonical_id=None,
            entity_type=None,
            enrichment_doi="10.1000/real",
            enrichment_source="openalex",
        )

        original_close = db_session.close
        db_session.close = lambda: None
        try:
            with patch.object(dedup, "SessionLocal", return_value=db_session):
                result = dedup.run(dry_run=False)
        finally:
            db_session.close = original_close

        assert result["fixed_wrong_doi"] == 1
        assert result["deleted_duplicates"] == 0

        db_session.refresh(wrong)
        assert wrong.enrichment_doi is None
        assert wrong.entity_type == "publication"
        assert wrong.enrichment_status == "pending"
        attrs = json.loads(wrong.attributes_json or "{}")
        assert attrs["_dedup_fix"]["action"] == "cleared_wrong_enrichment_doi"

    def test_true_duplicate_is_deleted(self, db_session):
        winner = _seed(
            db_session,
            primary_label="Same Title Here",
            domain="science",
            canonical_id="10.1000/dup",
            entity_type="publication",
            enrichment_doi="10.1000/dup",
            enrichment_source="openalex",
        )
        duplicate = _seed(
            db_session,
            primary_label="Same Title Here",
            domain="science",
            canonical_id=None,
            entity_type=None,
            enrichment_doi="10.1000/dup",
            enrichment_source="openalex",
        )
        dup_id = duplicate.id

        original_close = db_session.close
        db_session.close = lambda: None
        try:
            with patch.object(dedup, "SessionLocal", return_value=db_session):
                result = dedup.run(dry_run=False)
        finally:
            db_session.close = original_close

        assert result["deleted_duplicates"] == 1
        assert db_session.query(models.RawEntity).filter_by(id=dup_id).first() is None

    def test_merge_richer_attrs_into_winner(self, db_session):
        winner = _seed(
            db_session,
            primary_label="Merge Test",
            domain="science",
            canonical_id="10.1000/merge",
            entity_type="publication",
            enrichment_doi="10.1000/merge",
            attributes_json=json.dumps({"year": 2020}),
        )
        richer_dup = _seed(
            db_session,
            primary_label="Merge Test",
            domain="science",
            canonical_id=None,
            entity_type=None,
            enrichment_doi="10.1000/merge",
            attributes_json=json.dumps({"year": 2020, "abstract": "Important findings", "keywords": "science"}),
        )

        original_close = db_session.close
        db_session.close = lambda: None
        try:
            with patch.object(dedup, "SessionLocal", return_value=db_session):
                dedup.run(dry_run=False)
        finally:
            db_session.close = original_close

        db_session.refresh(winner)
        attrs = json.loads(winner.attributes_json)
        assert attrs["abstract"] == "Important findings"
        assert attrs["keywords"] == "science"
        assert attrs["_dedup_merged_from"] == richer_dup.id

    def test_dry_run_no_changes(self, db_session):
        winner = _seed(
            db_session,
            primary_label="Dry Run Title",
            domain="science",
            canonical_id="10.1000/dry",
            entity_type="publication",
            enrichment_doi="10.1000/dry",
        )
        dup = _seed(
            db_session,
            primary_label="Dry Run Title",
            domain="science",
            canonical_id=None,
            entity_type=None,
            enrichment_doi="10.1000/dry",
        )
        dup_id = dup.id

        original_close = db_session.close
        db_session.close = lambda: None
        try:
            with patch.object(dedup, "SessionLocal", return_value=db_session):
                result = dedup.run(dry_run=True)
        finally:
            db_session.close = original_close

        assert result["deleted_duplicates"] == 1
        db_session.expire_all()
        assert db_session.query(models.RawEntity).filter_by(id=dup_id).first() is not None

    def test_skips_records_without_doi(self, db_session):
        _seed(
            db_session,
            primary_label="No DOI",
            domain="default",
            canonical_id=None,
            entity_type=None,
            enrichment_doi=None,
        )

        original_close = db_session.close
        db_session.close = lambda: None
        try:
            with patch.object(dedup, "SessionLocal", return_value=db_session):
                result = dedup.run(dry_run=False)
        finally:
            db_session.close = original_close

        assert result["skipped"] == 1
        assert result["fixed_wrong_doi"] == 0
        assert result["deleted_duplicates"] == 0


# ── _dedup_before_insert import guard ────────────────────────────────────────


class TestDedupBeforeInsert:

    def test_skips_entity_with_existing_canonical_id(self, db_session):
        _seed(
            db_session,
            primary_label="Existing",
            domain="science",
            canonical_id="10.1000/exists",
            entity_type="publication",
        )

        new_entity = models.RawEntity(
            primary_label="Incoming duplicate",
            domain="science",
            canonical_id="10.1000/exists",
            entity_type="publication",
        )
        kept, skipped = _dedup_before_insert(db_session, [new_entity], org_id=None)
        assert skipped == 1
        assert len(kept) == 0

    def test_skips_intra_batch_duplicate(self, db_session):
        e1 = models.RawEntity(
            primary_label="First",
            domain="science",
            canonical_id="10.1000/batch",
            entity_type="publication",
        )
        e2 = models.RawEntity(
            primary_label="Second same DOI",
            domain="science",
            canonical_id="10.1000/batch",
            entity_type="publication",
        )
        kept, skipped = _dedup_before_insert(db_session, [e1, e2], org_id=None)
        assert skipped == 1
        assert len(kept) == 1
        assert kept[0].primary_label == "First"

    def test_allows_entities_without_canonical_id(self, db_session):
        e1 = models.RawEntity(
            primary_label="No ID 1",
            domain="default",
            canonical_id=None,
            entity_type=None,
        )
        e2 = models.RawEntity(
            primary_label="No ID 2",
            domain="default",
            canonical_id=None,
            entity_type=None,
        )
        kept, skipped = _dedup_before_insert(db_session, [e1, e2], org_id=None)
        assert skipped == 0
        assert len(kept) == 2

    def test_allows_same_canonical_id_different_domain(self, db_session):
        _seed(
            db_session,
            primary_label="Science version",
            domain="science",
            canonical_id="10.1000/cross",
            entity_type="publication",
        )
        new_entity = models.RawEntity(
            primary_label="Healthcare version",
            domain="healthcare",
            canonical_id="10.1000/cross",
            entity_type="publication",
        )
        kept, skipped = _dedup_before_insert(db_session, [new_entity], org_id=None)
        assert skipped == 0
        assert len(kept) == 1

    def test_empty_list_returns_empty(self, db_session):
        kept, skipped = _dedup_before_insert(db_session, [], org_id=None)
        assert kept == []
        assert skipped == 0
