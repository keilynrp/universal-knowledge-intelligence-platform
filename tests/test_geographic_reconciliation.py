"""Tests for Task 2.4 — Geographic Reconciliation Service."""
from backend.services.geographic_reconciliation import (
    GeoCandidate,
    GeographicReconciliationService,
)
from backend.services.geographic_entities import GeoEntityType


class TestISOReconciliation:
    def test_exact_iso_code(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile("US")
        assert len(candidates) == 1
        assert candidates[0].confidence == 1.0
        assert candidates[0].entity.country_code == "US"
        assert candidates[0].extraction_method == "iso_exact"

    def test_lowercase_iso(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile("de")
        assert len(candidates) == 1
        assert candidates[0].entity.country_code == "DE"

    def test_invalid_iso(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile("ZZ")
        assert len(candidates) == 0


class TestCountryNameReconciliation:
    def test_common_name(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile("United States")
        assert len(candidates) == 1
        assert candidates[0].entity.country_code == "US"
        assert candidates[0].confidence >= 0.9
        assert candidates[0].extraction_method == "name_exact"

    def test_spanish_name(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile("España")
        assert len(candidates) == 1
        assert candidates[0].entity.country_code == "ES"

    def test_german_name(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile("Deutschland")
        assert len(candidates) == 1
        assert candidates[0].entity.country_code == "DE"

    def test_case_insensitive(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile("JAPAN")
        assert len(candidates) == 1
        assert candidates[0].entity.country_code == "JP"


class TestVariantMatching:
    def test_diacritic_variant(self):
        svc = GeographicReconciliationService()
        # "espana" without tilde should match "españa" → ES
        candidates = svc.reconcile("espana")
        assert len(candidates) == 1
        assert candidates[0].entity.country_code == "ES"
        assert candidates[0].extraction_method in ("name_exact", "name_alias")
        assert candidates[0].confidence >= 0.8


class TestAmbiguousNames:
    def test_georgia_ambiguous(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile("Georgia")
        assert len(candidates) >= 2
        assert all(c.confidence < 0.7 for c in candidates)
        assert all(c.extraction_method == "ambiguous" for c in candidates)


class TestCoordinates:
    def test_valid_coordinates(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile_coordinates(40.7128, -74.0060)
        assert len(candidates) == 1
        assert candidates[0].entity.type == GeoEntityType.SPATIAL_AREA
        assert candidates[0].confidence == 0.7

    def test_invalid_coordinates(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile_coordinates(91.0, 0.0)
        assert len(candidates) == 0


class TestAffiliationExtraction:
    def test_affiliation_with_country(self):
        svc = GeographicReconciliationService()
        candidates = svc.extract_from_affiliation("MIT, Cambridge, United States")
        country_codes = [c.entity.country_code for c in candidates]
        assert "US" in country_codes

    def test_empty_affiliation(self):
        svc = GeographicReconciliationService()
        candidates = svc.extract_from_affiliation("")
        assert len(candidates) == 0


class TestRecordExtraction:
    def test_country_field(self):
        svc = GeographicReconciliationService()
        candidates = svc.extract_from_record({"country": "Germany"})
        assert len(candidates) >= 1
        assert candidates[0].entity.country_code == "DE"

    def test_country_code_field(self):
        svc = GeographicReconciliationService()
        candidates = svc.extract_from_record({"country_code": "BR"})
        assert len(candidates) == 1
        assert candidates[0].entity.country_code == "BR"

    def test_coordinates_in_record(self):
        svc = GeographicReconciliationService()
        candidates = svc.extract_from_record({"latitude": 48.8566, "longitude": 2.3522})
        spatial = [c for c in candidates if c.entity.type == GeoEntityType.SPATIAL_AREA]
        assert len(spatial) == 1

    def test_empty_record(self):
        svc = GeographicReconciliationService()
        candidates = svc.extract_from_record({})
        assert len(candidates) == 0

    def test_no_match(self):
        svc = GeographicReconciliationService()
        candidates = svc.reconcile("xyzzy nowhere")
        assert len(candidates) == 0
