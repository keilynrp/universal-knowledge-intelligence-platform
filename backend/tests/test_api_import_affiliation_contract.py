"""Regression tests for the OpenAlex/PubMed import affiliation contract.

Guards two invariants that broke between commits ``cbe3255`` and ``19e97ff``:

1. ``_ingest_records`` must NEVER write ``rec.publisher`` into
   ``attributes_json.affiliation``. Publisher belongs to ``attrs.publisher``.

2. ``_ingest_records`` must populate ``attrs.affiliation`` and
   ``attrs.affiliations`` strictly from ``rec.affiliations`` (the list of
   institutional names extracted from ``authorships[].institutions[]``).

Companion: ``backend.scripts.fix_legacy_affiliations`` cleans up rows that
still carry the legacy bug residue. Smoke tests for that script live here too.
"""

from __future__ import annotations

import json
from typing import Iterable

import pytest

from backend import models
from backend.schemas_enrichment import EnrichedRecord


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_record(**overrides) -> EnrichedRecord:
    """Build an EnrichedRecord with sensible defaults; ``overrides`` win."""
    defaults = dict(
        id="W-test-1",
        doi="10.0001/test",
        title="A Test Paper",
        authors=["Doe, Jane"],
        citation_count=3,
        publication_year=2024,
        publisher=None,
        is_open_access=False,
        concepts=["test"],
        source_api="OpenAlex",
        affiliations=[],
    )
    defaults.update(overrides)
    return EnrichedRecord(**defaults)


def _load_attrs(entity: models.RawEntity) -> dict:
    raw = entity.attributes_json or "{}"
    return json.loads(raw)


def _ingest(db, records: Iterable[EnrichedRecord], *, domain: str = "science", source: str = "openalex") -> int:
    """Thin wrapper around the production helper to keep tests focused."""
    from backend.routers.api_import import _ingest_records

    return _ingest_records(db, list(records), domain=domain, source=source, org_id=None)


# ── 1. Contract: publisher never leaks into affiliation ──────────────────────


class TestIngestAffiliationContract:
    """The exact regression that introduced the production bug.

    With ``rec.publisher`` populated (this is the journal name from OpenAlex
    ``primary_location.source.display_name``) and ``rec.affiliations`` empty,
    the entity must still NOT carry that value under affiliation.
    """

    def test_publisher_only_record_does_not_set_affiliation(self, session_factory):
        rec = _make_record(
            doi="10.0001/journal-only",
            publisher="Journal of the Medical Library Association JMLA",
            affiliations=[],
        )
        with session_factory() as db:
            try:
                inserted = _ingest(db, [rec])
                assert inserted == 1
                entity = db.query(models.RawEntity).filter(
                    models.RawEntity.enrichment_doi == rec.doi
                ).one()
                attrs = _load_attrs(entity)
                assert "affiliation" not in attrs, (
                    "Publisher must not be mirrored into attrs.affiliation"
                )
                assert "affiliations" not in attrs
                assert attrs.get("publisher") == rec.publisher
            finally:
                db.query(models.RawEntity).filter(
                    models.RawEntity.enrichment_doi == rec.doi
                ).delete()
                db.commit()

    def test_real_affiliations_populate_both_affiliation_keys(self, session_factory):
        rec = _make_record(
            doi="10.0001/real-aff",
            publisher="Nature",
            affiliations=["MIT, US", "Stanford University, US"],
        )
        with session_factory() as db:
            try:
                _ingest(db, [rec])
                entity = db.query(models.RawEntity).filter(
                    models.RawEntity.enrichment_doi == rec.doi
                ).one()
                attrs = _load_attrs(entity)
                assert attrs["affiliation"] == "MIT, US; Stanford University, US"
                assert attrs["affiliations"] == ["MIT, US", "Stanford University, US"]
                assert attrs["publisher"] == "Nature"
            finally:
                db.query(models.RawEntity).filter(
                    models.RawEntity.enrichment_doi == rec.doi
                ).delete()
                db.commit()

    def test_no_affiliation_and_no_publisher_keeps_attrs_clean(self, session_factory):
        rec = _make_record(doi="10.0001/empty", publisher=None, affiliations=[])
        with session_factory() as db:
            try:
                _ingest(db, [rec])
                entity = db.query(models.RawEntity).filter(
                    models.RawEntity.enrichment_doi == rec.doi
                ).one()
                attrs = _load_attrs(entity)
                assert "affiliation" not in attrs
                assert "affiliations" not in attrs
                assert "publisher" not in attrs
            finally:
                db.query(models.RawEntity).filter(
                    models.RawEntity.enrichment_doi == rec.doi
                ).delete()
                db.commit()


# ── 2. Migration script: legacy backfill ─────────────────────────────────────


class TestLegacyAffiliationBackfill:
    """Smoke tests for ``backend.scripts.fix_legacy_affiliations``.

    The script must clear journal/publisher residue while preserving real
    institutional affiliations. It must be safe to re-run.
    """

    @pytest.fixture(autouse=True)
    def _patch_session_local(self, monkeypatch, session_factory):
        """Point the script at the test SessionLocal so it operates on the
        in-memory DB instead of the production database URL captured at import time."""
        import backend.scripts.fix_legacy_affiliations as script
        monkeypatch.setattr(script, "SessionLocal", session_factory)
        yield

    def _seed(self, session_factory, *, doi: str, enrichment_source: str, attrs: dict) -> int:
        with session_factory() as db:
            entity = models.RawEntity(
                primary_label="Test",
                secondary_label=None,
                domain="science",
                source="test",
                enrichment_doi=doi,
                enrichment_source=enrichment_source,
                enrichment_status="completed",
                attributes_json=json.dumps(attrs, ensure_ascii=False),
            )
            db.add(entity)
            db.commit()
            return entity.id

    def _cleanup(self, session_factory, ids: list[int]) -> None:
        with session_factory() as db:
            db.query(models.RawEntity).filter(models.RawEntity.id.in_(ids)).delete(
                synchronize_session=False
            )
            db.commit()

    def test_clears_legacy_journal_in_affiliation(self, session_factory):
        from backend.scripts.fix_legacy_affiliations import run

        # Legacy bug residue: journal name in affiliation, no canonical_affiliations
        # to corroborate it as a real institution.
        eid = self._seed(
            session_factory,
            doi="10.0001/legacy-journal",
            enrichment_source="openalex",
            attrs={"affiliation": "Journal of the Medical Library Association"},
        )
        try:
            result = run(dry_run=False)
            assert result["fixed"] >= 1

            with session_factory() as db:
                entity = db.query(models.RawEntity).filter_by(id=eid).one()
                attrs = json.loads(entity.attributes_json)
                assert "affiliation" not in attrs
                assert attrs["_legacy_affiliation_backup"]["affiliation"] == (
                    "Journal of the Medical Library Association"
                )
        finally:
            self._cleanup(session_factory, [eid])

    def test_preserves_real_affiliation_when_canonical_matches(self, session_factory):
        from backend.scripts.fix_legacy_affiliations import run

        eid = self._seed(
            session_factory,
            doi="10.0001/real-keep",
            enrichment_source="openalex",
            attrs={
                "affiliation": "MIT",
                "canonical_affiliations": [{"name": "MIT", "country_code": "US"}],
            },
        )
        try:
            result = run(dry_run=False)
            # No fix should have happened on this row.
            with session_factory() as db:
                entity = db.query(models.RawEntity).filter_by(id=eid).one()
                attrs = json.loads(entity.attributes_json)
                assert attrs["affiliation"] == "MIT"
                assert "_legacy_affiliation_backup" not in attrs
            assert result["scanned"] >= 1
        finally:
            self._cleanup(session_factory, [eid])

    def test_dry_run_does_not_persist_changes(self, session_factory):
        from backend.scripts.fix_legacy_affiliations import run

        eid = self._seed(
            session_factory,
            doi="10.0001/dry-run",
            enrichment_source="openalex",
            attrs={"affiliation": "Nature"},
        )
        try:
            result = run(dry_run=True)
            assert result["fixed"] >= 1
            with session_factory() as db:
                entity = db.query(models.RawEntity).filter_by(id=eid).one()
                attrs = json.loads(entity.attributes_json)
                # Untouched because the transaction was rolled back.
                assert attrs["affiliation"] == "Nature"
                assert "_legacy_affiliation_backup" not in attrs
        finally:
            self._cleanup(session_factory, [eid])

    def test_skips_entities_from_unaffected_sources(self, session_factory):
        from backend.scripts.fix_legacy_affiliations import run

        # An entity from a non-affected source (e.g. a CSV upload) must be
        # left alone even if its affiliation looks suspicious.
        eid = self._seed(
            session_factory,
            doi="10.0001/csv-source",
            enrichment_source="csv_upload",
            attrs={"affiliation": "Journal of Something"},
        )
        try:
            run(dry_run=False)
            with session_factory() as db:
                entity = db.query(models.RawEntity).filter_by(id=eid).one()
                attrs = json.loads(entity.attributes_json)
                assert attrs["affiliation"] == "Journal of Something"
                assert "_legacy_affiliation_backup" not in attrs
        finally:
            self._cleanup(session_factory, [eid])

    def test_requeue_enrichment_marks_pending(self, session_factory):
        from backend.scripts.fix_legacy_affiliations import run

        eid = self._seed(
            session_factory,
            doi="10.0001/requeue",
            enrichment_source="openalex",
            attrs={"affiliation": "Nature"},
        )
        try:
            run(dry_run=False, requeue_enrichment=True)
            with session_factory() as db:
                entity = db.query(models.RawEntity).filter_by(id=eid).one()
                assert entity.enrichment_status == "pending"
        finally:
            self._cleanup(session_factory, [eid])

    def test_idempotent(self, session_factory):
        from backend.scripts.fix_legacy_affiliations import run

        eid = self._seed(
            session_factory,
            doi="10.0001/idempotent",
            enrichment_source="openalex",
            attrs={"affiliation": "Some Journal"},
        )
        try:
            first = run(dry_run=False)
            second = run(dry_run=False)
            # First pass fixes; second pass finds nothing left to fix.
            assert first["fixed"] >= 1
            assert second["fixed"] == 0
        finally:
            self._cleanup(session_factory, [eid])
