"""Tests for layer_boundaries.py — Task 3.8."""
import pytest

from backend.services.layer_boundaries import (
    LayerSnapshot,
    LayerViolationError,
    classify_layer,
    enforce_layer_boundaries,
    safe_enrichment_rollback,
    snapshot_entity,
    validate_authority_apply,
    validate_enrichment_apply,
    validate_promotion,
    validate_reingestion,
)


class TestClassifyLayer:
    def test_source_fields(self):
        assert classify_layer("primary_label") == "source"
        assert classify_layer("domain") == "source"
        assert classify_layer("entity_type") == "source"

    def test_enrichment_fields(self):
        assert classify_layer("enrichment_doi") == "enrichment"
        assert classify_layer("quality_score") == "enrichment"
        assert classify_layer("normalized_json") == "enrichment"

    def test_canonical_fields(self):
        assert classify_layer("canonical_id") == "canonical"

    def test_authority_fields(self):
        assert classify_layer("authority_source") == "authority"
        assert classify_layer("confidence") == "authority"
        assert classify_layer("resolution_status") == "authority"

    def test_unknown_defaults_to_source(self):
        assert classify_layer("some_random_field") == "source"


class TestSnapshotEntity:
    def test_basic_split(self):
        entity = {
            "primary_label": "Test",
            "enrichment_doi": "10.1234",
            "canonical_id": "C-1",
            "authority_source": "wikidata",
        }
        snap = snapshot_entity(entity)
        assert snap.source == {"primary_label": "Test"}
        assert snap.enrichment == {"enrichment_doi": "10.1234"}
        assert snap.canonical == {"canonical_id": "C-1"}
        assert snap.authority == {"authority_source": "wikidata"}

    def test_empty_entity(self):
        snap = snapshot_entity({})
        assert snap.source == {}
        assert snap.enrichment == {}

    def test_to_dict(self):
        snap = snapshot_entity({"primary_label": "X"})
        d = snap.to_dict()
        assert "source" in d
        assert "enrichment" in d
        assert "canonical" in d
        assert "authority" in d


class TestValidateEnrichmentApply:
    def _snap(self):
        return LayerSnapshot(source={}, enrichment={}, canonical={}, authority={})

    def test_valid_enrichment(self):
        violations = validate_enrichment_apply(
            self._snap(), {"enrichment_doi": "10.1234"}
        )
        assert violations == []

    def test_cannot_overwrite_source(self):
        violations = validate_enrichment_apply(
            self._snap(), {"primary_label": "overwrite"}
        )
        assert len(violations) == 1
        assert "source" in violations[0].lower()

    def test_cannot_overwrite_canonical(self):
        violations = validate_enrichment_apply(
            self._snap(), {"canonical_id": "C-999"}
        )
        assert len(violations) == 1

    def test_cannot_overwrite_authority(self):
        violations = validate_enrichment_apply(
            self._snap(), {"authority_source": "bad"}
        )
        assert len(violations) == 1

    def test_multiple_violations(self):
        violations = validate_enrichment_apply(
            self._snap(), {"primary_label": "x", "canonical_id": "y"}
        )
        assert len(violations) == 2


class TestValidateAuthorityApply:
    def _snap(self):
        return LayerSnapshot(source={}, enrichment={}, canonical={}, authority={})

    def test_valid_authority(self):
        violations = validate_authority_apply(
            self._snap(), {"authority_source": "viaf", "confidence": 0.9}
        )
        assert violations == []

    def test_cannot_overwrite_enrichment(self):
        violations = validate_authority_apply(
            self._snap(), {"enrichment_doi": "10.bad"}
        )
        assert len(violations) == 1
        assert "enrichment" in violations[0].lower()

    def test_cannot_overwrite_source(self):
        violations = validate_authority_apply(
            self._snap(), {"primary_label": "bad"}
        )
        assert len(violations) == 1


class TestValidatePromotion:
    def _snap(self):
        return LayerSnapshot(source={}, enrichment={}, canonical={}, authority={})

    def test_valid_promotion(self):
        violations = validate_promotion(
            self._snap(), {"canonical_id": "C-1"}
        )
        assert violations == []

    def test_cannot_destroy_source(self):
        violations = validate_promotion(
            self._snap(), {"primary_label": "overwrite"}
        )
        assert len(violations) == 1
        assert "source" in violations[0].lower()


class TestValidateReingestion:
    def _snap(self):
        return LayerSnapshot(source={}, enrichment={}, canonical={}, authority={})

    def test_valid_reingestion(self):
        violations = validate_reingestion(
            self._snap(), {"primary_label": "new", "domain": "science"}
        )
        assert violations == []

    def test_cannot_overwrite_canonical(self):
        violations = validate_reingestion(
            self._snap(), {"canonical_id": "C-1"}
        )
        assert len(violations) == 1

    def test_cannot_overwrite_authority(self):
        violations = validate_reingestion(
            self._snap(), {"authority_source": "bad"}
        )
        assert len(violations) == 1


class TestEnforceBoundaries:
    def _snap(self):
        return LayerSnapshot(source={}, enrichment={}, canonical={}, authority={})

    def test_valid_enrichment_passes(self):
        enforce_layer_boundaries("enrichment", self._snap(), {"enrichment_doi": "10.1"})

    def test_invalid_enrichment_raises(self):
        with pytest.raises(LayerViolationError) as exc_info:
            enforce_layer_boundaries("enrichment", self._snap(), {"primary_label": "x"})
        assert "enrichment" in str(exc_info.value).lower()

    def test_unknown_operation(self):
        with pytest.raises(ValueError):
            enforce_layer_boundaries("bogus", self._snap(), {})

    def test_authority_valid(self):
        enforce_layer_boundaries("authority", self._snap(), {"authority_source": "viaf"})

    def test_promotion_valid(self):
        enforce_layer_boundaries("promotion", self._snap(), {"canonical_id": "C-1"})

    def test_reingestion_valid(self):
        enforce_layer_boundaries("reingestion", self._snap(), {"primary_label": "new"})


class TestSafeEnrichmentRollback:
    def test_clears_enrichment(self):
        entity = {
            "primary_label": "Test",
            "enrichment_doi": "10.1234",
            "enrichment_citation_count": "5",
            "authority_source": "viaf",
        }
        result = safe_enrichment_rollback(entity)
        assert result["primary_label"] == "Test"
        assert result["enrichment_doi"] is None
        assert result["enrichment_citation_count"] is None
        assert result["authority_source"] == "viaf"

    def test_does_not_mutate_original(self):
        entity = {"enrichment_doi": "10.1234"}
        safe_enrichment_rollback(entity)
        assert entity["enrichment_doi"] == "10.1234"

    def test_missing_fields_ok(self):
        entity = {"primary_label": "Test"}
        result = safe_enrichment_rollback(entity)
        assert result["primary_label"] == "Test"
