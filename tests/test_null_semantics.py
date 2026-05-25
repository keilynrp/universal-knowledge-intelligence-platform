"""Tests for Task 2.7 — Entity Detail Null Semantics."""
from backend.services.null_semantics import (
    NullReason,
    compute_field_null_reason,
    enrich_entity_with_null_reasons,
)


class TestNotProvided:
    def test_upload_missing_field(self):
        entity = {"source": "upload", "primary_label": "Test", "enrichment_doi": None, "enrichment_status": "done"}
        reason, key = compute_field_null_reason(entity, "enrichment_doi")
        assert reason == NullReason.NOT_PROVIDED

    def test_user_source(self):
        entity = {"source": "user", "enrichment_doi": None, "enrichment_status": "done"}
        reason, key = compute_field_null_reason(entity, "enrichment_doi")
        assert reason == NullReason.NOT_PROVIDED


class TestPendingNormalization:
    def test_pending_canonical_id(self):
        entity = {"validation_status": "pending", "canonical_id": None}
        reason, key = compute_field_null_reason(entity, "canonical_id")
        assert reason == NullReason.PENDING_NORMALIZATION
        assert "pending_normalization" in key


class TestUnresolvedEnrichment:
    def test_enrichment_not_started(self):
        entity = {"enrichment_status": "none", "enrichment_doi": None}
        reason, key = compute_field_null_reason(entity, "enrichment_doi")
        assert reason == NullReason.UNRESOLVED_ENRICHMENT

    def test_enrichment_pending(self):
        entity = {"enrichment_status": "pending", "quality_score": None}
        reason, key = compute_field_null_reason(entity, "quality_score")
        assert reason == NullReason.UNRESOLVED_ENRICHMENT


class TestNotApplicable:
    def test_doi_on_non_publication(self):
        entity = {"entity_type": "dataset", "enrichment_doi": None, "enrichment_status": "done"}
        reason, key = compute_field_null_reason(entity, "enrichment_doi")
        assert reason == NullReason.NOT_APPLICABLE

    def test_citation_count_on_non_publication(self):
        entity = {"entity_type": "person", "enrichment_citation_count": 0, "enrichment_status": "done"}
        reason, key = compute_field_null_reason(entity, "enrichment_citation_count")
        assert reason == NullReason.NOT_APPLICABLE


class TestLegacyRecord:
    def test_unknown_source(self):
        entity = {"source": "legacy_import", "enrichment_concepts": None, "enrichment_status": "done"}
        reason, key = compute_field_null_reason(entity, "enrichment_concepts")
        # enrichment ran but didn't produce concepts → not_provided
        # But source is not user/upload → unknown
        assert reason in (NullReason.NOT_PROVIDED, NullReason.UNKNOWN)


class TestNonNullField:
    def test_field_has_value(self):
        entity = {"enrichment_doi": "10.1234/test"}
        reason, key = compute_field_null_reason(entity, "enrichment_doi")
        assert reason == NullReason.UNKNOWN
        assert key == ""


class TestEnrichEntityBulk:
    def test_bulk_enrichment(self):
        entity = {
            "primary_label": "Test",
            "enrichment_doi": None,
            "enrichment_status": "none",
            "canonical_id": None,
            "validation_status": "pending",
        }
        result = enrich_entity_with_null_reasons(entity)
        assert "enrichment_doi" in result
        assert result["enrichment_doi"]["reason_code"] == "unresolved_enrichment"
        assert "canonical_id" in result
        assert result["canonical_id"]["reason_code"] == "pending_normalization"
        # primary_label has a value, should not appear
        assert "primary_label" not in result

    def test_empty_entity(self):
        result = enrich_entity_with_null_reasons({})
        assert result == {}
