"""
Tests for the entity-metadata-contract change.

Covers:
- EnrichmentStatus / ValidationStatus enum correctness
- KNOWN_ATTRIBUTE_KEYS matches EntityAttributesDict
- Startup migration idempotency and legacy-value elimination
- Worker outputs only known attribute keys
"""
import json
import pytest
from sqlalchemy import text

from backend import models
from backend.schemas import (
    EnrichmentStatus,
    ValidationStatus,
    EntityAttributesDict,
    KNOWN_ATTRIBUTE_KEYS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(db, label: str, status: str) -> models.RawEntity:
    e = models.RawEntity(primary_label=label, enrichment_status=status, domain="meta_contract_test")
    db.add(e)
    db.flush()
    return e


def _cleanup(db) -> None:
    db.query(models.RawEntity).filter(models.RawEntity.domain == "meta_contract_test").delete()
    db.commit()


# ---------------------------------------------------------------------------
# 5.3 EnrichmentStatus enum values
# ---------------------------------------------------------------------------

class TestEnrichmentStatusEnum:
    def test_has_exactly_five_values(self):
        values = {s.value for s in EnrichmentStatus}
        assert values == {"none", "pending", "processing", "completed", "failed"}

    def test_is_str_subclass(self):
        assert isinstance(EnrichmentStatus.completed, str)
        assert EnrichmentStatus.completed == "completed"

    def test_none_value(self):
        assert EnrichmentStatus.none.value == "none"

    def test_pending_value(self):
        assert EnrichmentStatus.pending.value == "pending"

    def test_processing_value(self):
        assert EnrichmentStatus.processing.value == "processing"

    def test_completed_value(self):
        assert EnrichmentStatus.completed.value == "completed"

    def test_failed_value(self):
        assert EnrichmentStatus.failed.value == "failed"

    def test_legacy_done_not_a_member(self):
        with pytest.raises((ValueError, KeyError)):
            EnrichmentStatus("done")

    def test_legacy_enriched_not_a_member(self):
        with pytest.raises((ValueError, KeyError)):
            EnrichmentStatus("enriched")


class TestValidationStatusEnum:
    def test_has_exactly_three_values(self):
        values = {s.value for s in ValidationStatus}
        assert values == {"pending", "valid", "invalid"}

    def test_is_str_subclass(self):
        assert isinstance(ValidationStatus.pending, str)


# ---------------------------------------------------------------------------
# 5.4 KNOWN_ATTRIBUTE_KEYS matches EntityAttributesDict
# ---------------------------------------------------------------------------

class TestKnownAttributeKeys:
    def test_matches_typed_dict_annotations(self):
        typed_dict_keys = frozenset(EntityAttributesDict.__annotations__.keys())
        assert KNOWN_ATTRIBUTE_KEYS == typed_dict_keys

    def test_contains_expected_keys(self):
        expected = {
            "enrichment_authors",
            "enrichment_author_orcids",
            "enrichment_affiliations",
            "enrichment_funding",
            "enrichment_mesh_terms",
            "enrichment_tldr",
            "enrichment_influential_citation_count",
            "enrichment_references_count",
            "enrichment_license",
            "enrichment_venue",
            "enrichment_failure",
        }
        assert expected == KNOWN_ATTRIBUTE_KEYS

    def test_has_eleven_keys(self):
        assert len(KNOWN_ATTRIBUTE_KEYS) == 11

    def test_all_keys_are_strings(self):
        assert all(isinstance(k, str) for k in KNOWN_ATTRIBUTE_KEYS)


# ---------------------------------------------------------------------------
# 5.1 + 5.2  Migration idempotency and legacy-value elimination
# ---------------------------------------------------------------------------

class TestStartupMigration:
    def test_migration_converts_done_to_completed(self, db_session):
        _cleanup(db_session)
        e = _make_entity(db_session, "done entity", "done")
        db_session.commit()

        # Run the migration SQL directly (simulates what lifespan does)
        db_session.execute(
            text("UPDATE raw_entities SET enrichment_status = 'completed' WHERE enrichment_status IN ('done', 'enriched')")
        )
        db_session.commit()

        db_session.refresh(e)
        assert e.enrichment_status == "completed"
        _cleanup(db_session)

    def test_migration_converts_enriched_to_completed(self, db_session):
        _cleanup(db_session)
        e = _make_entity(db_session, "enriched entity", "enriched")
        db_session.commit()

        db_session.execute(
            text("UPDATE raw_entities SET enrichment_status = 'completed' WHERE enrichment_status IN ('done', 'enriched')")
        )
        db_session.commit()

        db_session.refresh(e)
        assert e.enrichment_status == "completed"
        _cleanup(db_session)

    def test_migration_is_idempotent(self, db_session):
        """Running the migration a second time affects 0 rows."""
        _cleanup(db_session)
        _make_entity(db_session, "already completed", "completed")
        db_session.commit()

        result = db_session.execute(
            text("UPDATE raw_entities SET enrichment_status = 'completed' WHERE enrichment_status IN ('done', 'enriched')")
        )
        db_session.commit()
        assert result.rowcount == 0
        _cleanup(db_session)

    def test_no_legacy_values_remain_after_migration(self, db_session):
        _cleanup(db_session)
        _make_entity(db_session, "done 1", "done")
        _make_entity(db_session, "enriched 1", "enriched")
        _make_entity(db_session, "completed 1", "completed")
        db_session.commit()

        db_session.execute(
            text("UPDATE raw_entities SET enrichment_status = 'completed' WHERE enrichment_status IN ('done', 'enriched')")
        )
        db_session.commit()

        count = db_session.execute(
            text("SELECT COUNT(*) FROM raw_entities WHERE enrichment_status IN ('done', 'enriched') AND domain = 'meta_contract_test'")
        ).scalar()
        assert count == 0
        _cleanup(db_session)

    def test_migration_does_not_touch_other_statuses(self, db_session):
        _cleanup(db_session)
        _make_entity(db_session, "pending entity", "pending")
        _make_entity(db_session, "failed entity", "failed")
        _make_entity(db_session, "processing entity", "processing")
        _make_entity(db_session, "none entity", "none")
        db_session.commit()

        db_session.execute(
            text("UPDATE raw_entities SET enrichment_status = 'completed' WHERE enrichment_status IN ('done', 'enriched')")
        )
        db_session.commit()

        for status in ("pending", "failed", "processing", "none"):
            count = db_session.execute(
                text(f"SELECT COUNT(*) FROM raw_entities WHERE enrichment_status = '{status}' AND domain = 'meta_contract_test'")
            ).scalar()
            assert count == 1, f"Expected 1 row with status={status}, got {count}"
        _cleanup(db_session)


# ---------------------------------------------------------------------------
# 5.5  Worker attribute keys smoke-check
# ---------------------------------------------------------------------------

class TestAttributeKeyContract:
    def test_enrichment_worker_writes_only_known_keys(self, db_session):
        """
        After a successful mock enrichment, all top-level keys in attributes_json
        must be present in KNOWN_ATTRIBUTE_KEYS (plus any app/system keys that
        are explicitly allowed).
        """
        from unittest.mock import MagicMock, patch
        from backend.enrichment_worker import enrich_single_record

        entity = models.RawEntity(
            primary_label="Metadata Contract Test Paper",
            enrichment_status="processing",
            domain="meta_contract_test",
        )
        db_session.add(entity)
        db_session.commit()

        mock_result = MagicMock()
        mock_result.doi = "10.9999/meta"
        mock_result.citation_count = 5
        mock_result.concepts = ["AI", "Metadata"]
        mock_result.authors = ["Jane Doe"]
        mock_result.author_orcids = [None]
        mock_result.concept_ids = []
        mock_result.funding = None
        mock_result.tldr = None
        mock_result.mesh_terms = None
        mock_result.influential_citation_count = None
        mock_result.references_count = None
        mock_result.license = None
        mock_result.venue = None
        mock_result.affiliations = None

        mock_provider = MagicMock()
        mock_provider.is_active = True
        mock_provider.search_by_title.return_value = [mock_result]
        mock_cb = MagicMock()
        mock_cb.call = lambda fn, *a, **kw: fn(*a, **kw)

        with (
            patch("backend.enrichment_worker._ACTIVE_CASCADE", ["openalex"]),
            patch("backend.enrichment_worker._PROVIDER_MAP", {"openalex": (mock_provider, mock_cb)}),
        ):
            result = enrich_single_record(db_session, entity)

        assert result.enrichment_status == EnrichmentStatus.completed

        if result.attributes_json:
            attrs = json.loads(result.attributes_json)
            # Filter to only enrichment_* keys (system keys like 'enrichment_failure' are allowed)
            enrichment_keys = {k for k in attrs if k.startswith("enrichment_")}
            unknown = enrichment_keys - KNOWN_ATTRIBUTE_KEYS
            assert not unknown, (
                f"Worker wrote undocumented attributes_json keys: {unknown}\n"
                f"Update EntityAttributesDict in backend/schemas.py to document them."
            )

        # Cleanup
        db_session.query(models.RawEntity).filter(
            models.RawEntity.domain == "meta_contract_test"
        ).delete()
        db_session.commit()
