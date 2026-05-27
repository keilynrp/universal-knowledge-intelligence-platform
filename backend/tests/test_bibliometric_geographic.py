"""Tests for Geographic / Country analysis (task 4.6)."""
import json
import pytest
from backend import models
from backend.database import SessionLocal
from backend.analyzers.geographic import country_timeseries, extract_country, geographic_analysis


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


def _seed_entities_with_years(entries: list[dict], domain: str = "__geo_ts_test__"):
    """Seed entities with publication_year + affiliation, using a fresh session."""
    db = SessionLocal()
    try:
        for e in entries:
            attrs: dict = {"affiliation": e.get("affiliation", "")}
            if "publication_year" in e:
                attrs["publication_year"] = e["publication_year"]
            if "extracted_country" in e:
                attrs["extracted_country"] = e["extracted_country"]
            db.add(models.RawEntity(
                primary_label=e.get("title", "Paper"),
                domain=domain,
                enrichment_citation_count=e.get("citations", 0),
                enrichment_status="completed",
                attributes_json=json.dumps(attrs),
            ))
        db.commit()
    finally:
        db.close()


class TestCountryTimeseries:
    def test_returns_requested_span(self):
        _seed_entities_with_years([
            {"affiliation": "MIT, USA", "publication_year": 2020, "citations": 5},
            {"affiliation": "Stanford, USA", "publication_year": 2024, "citations": 10},
        ], domain="__geo_ts_span__")
        result = country_timeseries("__geo_ts_span__", "US", years=9, reference_year=2024)
        assert result["years"] == 9
        assert len(result["series"]) == 9
        assert result["series"][0]["year"] == 2016
        assert result["series"][-1]["year"] == 2024
        # Year buckets reflect seeded data
        years_map = {p["year"]: p["citation_sum"] for p in result["series"]}
        assert years_map[2020] == 5
        assert years_map[2024] == 10
        # All other buckets zero
        assert sum(p["citation_sum"] for p in result["series"]) == 15

    def test_total_aggregates(self):
        _seed_entities_with_years([
            {"affiliation": "MIT, USA", "publication_year": 2022, "citations": 3},
            {"affiliation": "Lab, USA", "publication_year": 2023, "citations": 7},
            {"affiliation": "Lab, Germany", "publication_year": 2023, "citations": 100},
        ], domain="__geo_ts_total__")
        result = country_timeseries("__geo_ts_total__", "US", years=9, reference_year=2024)
        assert result["total_entities"] == 2
        assert result["total_citations"] == 10
        assert result["country_code"] == "US"
        assert result["country_name"] == "United States"

    def test_lowercase_code_normalized(self):
        _seed_entities_with_years([
            {"affiliation": "Lab, France", "publication_year": 2023, "citations": 4},
        ], domain="__geo_ts_lower__")
        result = country_timeseries("__geo_ts_lower__", "fr", years=9, reference_year=2024)
        assert result["country_code"] == "FR"
        assert result["total_entities"] == 1

    def test_unknown_country_empty(self):
        _seed_entities_with_years([
            {"affiliation": "MIT, USA", "publication_year": 2023, "citations": 5},
        ], domain="__geo_ts_empty__")
        result = country_timeseries("__geo_ts_empty__", "JP", years=9, reference_year=2024)
        assert result["total_entities"] == 0
        assert all(p["citation_sum"] == 0 for p in result["series"])

    def test_missing_year_counted_in_total_only(self):
        """Entities without publication_year contribute to total but not to any year bucket."""
        _seed_entities_with_years([
            {"affiliation": "MIT, USA", "citations": 5},  # no year
            {"affiliation": "Lab, USA", "publication_year": 2023, "citations": 7},
        ], domain="__geo_ts_missing_year__")
        result = country_timeseries("__geo_ts_missing_year__", "US", years=9, reference_year=2024)
        assert result["total_entities"] == 2
        assert result["total_citations"] == 12
        year_sum = sum(p["citation_sum"] for p in result["series"])
        assert year_sum == 7  # only the dated paper

    def test_invalid_domain(self):
        with pytest.raises(ValueError):
            country_timeseries("__nonexistent_domain_xyz__", "US", years=9)


class TestCountryTimeseriesEndpoint:
    def test_endpoint_ok(self, client, auth_headers):
        resp = client.get(
            "/analyzers/geographic/default/country/US?years=9", headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["country_code"] == "US"
        assert len(data["series"]) == 9

    def test_endpoint_requires_auth(self, client):
        resp = client.get("/analyzers/geographic/default/country/US")
        assert resp.status_code in (401, 403)

    def test_endpoint_years_bounds(self, client, auth_headers):
        resp = client.get(
            "/analyzers/geographic/default/country/US?years=0", headers=auth_headers,
        )
        assert resp.status_code == 422
        resp = client.get(
            "/analyzers/geographic/default/country/US?years=999", headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_endpoint_invalid_domain(self, client, auth_headers):
        resp = client.get(
            "/analyzers/geographic/nonexistent_xyz_999/country/US",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestGeographicFilters:
    def test_year_range_filter(self):
        _seed_entities_with_years([
            {"affiliation": "MIT, USA", "publication_year": 2010, "citations": 5},
            {"affiliation": "MIT, USA", "publication_year": 2020, "citations": 10},
            {"affiliation": "MIT, USA", "publication_year": 2024, "citations": 15},
        ], domain="__geo_filter_year__")
        result = geographic_analysis(
            "__geo_filter_year__", year_from=2020, year_to=2024,
        )
        us = next((c for c in result["countries"] if c["country_code"] == "US"), None)
        assert us is not None
        assert us["entity_count"] == 2
        assert us["citation_sum"] == 25
        assert result["total_entities"] == 2

    def test_min_citations_filter(self):
        _seed_entities_with_years([
            {"affiliation": "MIT, USA", "publication_year": 2022, "citations": 2},
            {"affiliation": "MIT, USA", "publication_year": 2023, "citations": 50},
        ], domain="__geo_filter_cites__")
        result = geographic_analysis(
            "__geo_filter_cites__", min_citations=10,
        )
        us = next((c for c in result["countries"] if c["country_code"] == "US"), None)
        assert us["entity_count"] == 1
        assert us["citation_sum"] == 50

    def test_year_filter_excludes_undated(self):
        """Entities without publication_year are excluded when a year filter is set."""
        _seed_entities_with_years([
            {"affiliation": "MIT, USA", "citations": 5},  # no year
            {"affiliation": "MIT, USA", "publication_year": 2023, "citations": 10},
        ], domain="__geo_filter_undated__")
        result = geographic_analysis(
            "__geo_filter_undated__", year_from=2020,
        )
        us = next((c for c in result["countries"] if c["country_code"] == "US"), None)
        assert us["entity_count"] == 1

    def test_endpoint_year_param(self, client, auth_headers):
        resp = client.get(
            "/analyzers/geographic/default?year_from=2020&year_to=2024",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_endpoint_min_citations_param(self, client, auth_headers):
        resp = client.get(
            "/analyzers/geographic/default?min_citations=10",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_endpoint_year_out_of_range(self, client, auth_headers):
        resp = client.get(
            "/analyzers/geographic/default?year_from=1800",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_endpoint_negative_min_citations(self, client, auth_headers):
        resp = client.get(
            "/analyzers/geographic/default?min_citations=-1",
            headers=auth_headers,
        )
        assert resp.status_code == 422
