"""Tests for Geographic / Country analysis (task 4.6)."""
import json
import pytest
from backend import models
from backend.database import SessionLocal
from backend.analyzers.geographic import extract_country, geographic_analysis


class TestCountryExtraction:
    def test_standard_affiliation(self):
        assert extract_country("MIT, Cambridge, MA, United States") == "US"

    def test_abbreviated_prc(self):
        assert extract_country("Tsinghua University, Beijing, PRC") == "CN"

    def test_abbreviated_usa(self):
        assert extract_country("Stanford University, Stanford, CA, USA") == "US"

    def test_uk_abbreviation(self):
        assert extract_country("University of Oxford, UK") == "GB"

    def test_full_country_name(self):
        assert extract_country("University of Tokyo, Japan") == "JP"

    def test_germany(self):
        assert extract_country("Max Planck Institute, Munich, Germany") == "DE"

    def test_unresolvable(self):
        assert extract_country("Unknown Lab, Somewhere") is None

    def test_none_input(self):
        assert extract_country(None) is None

    def test_empty_string(self):
        assert extract_country("") is None

    def test_south_korea(self):
        assert extract_country("KAIST, Daejeon, South Korea") == "KR"

    def test_republic_of_korea(self):
        assert extract_country("Seoul National University, Republic of Korea") == "KR"


def _seed_entities_with_affiliations(entities_data: list[dict], domain: str = "default"):
    """Seed entities using a fresh session."""
    db = SessionLocal()
    try:
        for data in entities_data:
            attrs = {"affiliation": data.get("affiliation", "")}
            if "extracted_country" in data:
                attrs["extracted_country"] = data["extracted_country"]
            db.add(models.RawEntity(
                primary_label=data.get("title", "Test Paper"),
                domain=domain,
                enrichment_citation_count=data.get("citations", 0),
                enrichment_status="completed",
                attributes_json=json.dumps(attrs),
            ))
        db.commit()
    finally:
        db.close()


class TestGeographicAnalysis:
    def test_geographic_aggregation(self):
        _seed_entities_with_affiliations([
            {"title": "Paper 1", "affiliation": "MIT, USA", "citations": 10},
            {"title": "Paper 2", "affiliation": "Stanford, USA", "citations": 20},
            {"title": "Paper 3", "affiliation": "Oxford, United Kingdom", "citations": 5},
        ])
        result = geographic_analysis("default")
        assert result["coverage"] > 0
        us_entry = next((c for c in result["countries"] if c["country_code"] == "US"), None)
        assert us_entry is not None
        assert us_entry["entity_count"] == 2
        assert us_entry["citation_sum"] == 30

    def test_empty_domain(self):
        """Use a unique domain with no affiliations to test empty results."""
        _seed_entities_with_affiliations(
            [{"title": "No affiliation", "affiliation": ""}],
            domain="__geo_empty_test__",
        )
        result = geographic_analysis("__geo_empty_test__")
        assert result["coverage"] == 0.0
        assert result["countries"] == []

    def test_limit_with_others(self):
        _seed_entities_with_affiliations([
            {"affiliation": "Lab, USA"},
            {"affiliation": "Lab, United Kingdom"},
            {"affiliation": "Lab, Germany"},
            {"affiliation": "Lab, France"},
        ])
        result = geographic_analysis("default", limit=2)
        codes = [c["country_code"] for c in result["countries"]]
        assert "OTHER" in codes
        assert len(result["countries"]) == 3  # top 2 + others

    def test_sort_by_citation_sum(self):
        _seed_entities_with_affiliations([
            {"affiliation": "Lab, USA", "citations": 5},
            {"affiliation": "Lab, Germany", "citations": 100},
        ])
        result = geographic_analysis("default", sort_by="citation_sum")
        assert result["countries"][0]["country_code"] == "DE"

    def test_cached_extracted_country(self):
        _seed_entities_with_affiliations([
            {"title": "Cached", "affiliation": "", "extracted_country": "JP"},
        ])
        result = geographic_analysis("default")
        jp = next((c for c in result["countries"] if c["country_code"] == "JP"), None)
        assert jp is not None

    def test_unresolvable_affiliations_lower_coverage(self):
        _seed_entities_with_affiliations([
            {"affiliation": "MIT, USA"},
            {"affiliation": "Unknown Lab, Somewhere"},
            {"affiliation": ""},
        ])
        result = geographic_analysis("default")
        assert result["coverage"] < 1.0


class TestGeographicEndpoints:
    def test_geographic_endpoint_ok(self, client, auth_headers):
        resp = client.get("/analyzers/geographic/default", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "countries" in data
        assert "coverage" in data

    def test_geographic_invalid_domain(self, client, auth_headers):
        resp = client.get("/analyzers/geographic/nonexistent_xyz_999", headers=auth_headers)
        assert resp.status_code == 404

    def test_geographic_requires_auth(self, client):
        resp = client.get("/analyzers/geographic/default")
        assert resp.status_code in (401, 403)

    def test_geographic_collaboration_param(self, client, auth_headers):
        resp = client.get(
            "/analyzers/geographic/default?include_collaboration=true",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "collaboration_rate" in data
