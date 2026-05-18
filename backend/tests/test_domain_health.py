"""
Tests for community health metrics (domain_health analyzer + endpoints).
"""
import json
import math

import pytest

from backend import models
from backend.schema_registry import (
    DomainSchema,
    DiscourseConfig,
    HealthMetricDef,
    SchemaRegistry,
)
from backend.analyzers.domain_health import (
    _extract_authors,
    _gini_coefficient,
    _international_collaboration_rate,
    _open_access_rate,
    _epistemic_diversity,
    _newcomer_rate,
    compute_health_metrics,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _entity(db, *, authors=None, countries=None, is_oa=None, paradigm=None,
            year=2023, domain="science"):
    attrs = {}
    if authors is not None:
        attrs["enrichment_authors"] = authors
    if countries is not None:
        attrs["countries"] = countries
    if is_oa is not None:
        attrs["is_open_access"] = is_oa
    if paradigm is not None:
        attrs["epistemic_profile"] = {"dominant": paradigm}
    if year is not None:
        attrs["year"] = year
    e = models.RawEntity(
        primary_label="Test",
        domain=domain,
        enrichment_status="completed",
        attributes_json=json.dumps(attrs),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


# ── Schema loading tests ────────────────────────────────────────────────────

class TestDiscourseSchema:

    def test_science_domain_has_discourse_community(self):
        reg = SchemaRegistry()
        science = reg.get_domain("science")
        assert science is not None
        assert science.discourse_community is not None
        assert len(science.discourse_community.health_metrics) == 5
        ids = [m.id for m in science.discourse_community.health_metrics]
        assert "gini_authorship" in ids
        assert "epistemic_diversity" in ids

    def test_domain_without_discourse_community_loads(self):
        reg = SchemaRegistry()
        for did in reg.domains:
            domain = reg.get_domain(did)
            if did != "science":
                assert domain.discourse_community is None, (
                    f"Domain {did} should not have discourse_community"
                )

    def test_domain_schema_without_discourse_community_key(self):
        schema = DomainSchema(
            id="test", name="Test", description="desc",
            primary_entity="entity", attributes=[],
        )
        assert schema.discourse_community is None


# ── Gini coefficient tests ──────────────────────────────────────────────────

class TestGiniCoefficient:

    def test_balanced_authors_low_gini(self):
        counts = [2] * 50  # 50 authors, 2 each
        g = _gini_coefficient(counts)
        assert g < 0.15

    def test_concentrated_authors_high_gini(self):
        counts = [80] + [1] * 20  # 1 author has 80, 20 have 1
        g = _gini_coefficient(counts)
        assert g > 0.7

    def test_single_author_zero_gini(self):
        counts = [10]
        g = _gini_coefficient(counts)
        assert g == 0.0

    def test_empty_counts(self):
        g = _gini_coefficient([])
        assert g == 0.0

    def test_perfectly_equal(self):
        counts = [5, 5, 5, 5]
        g = _gini_coefficient(counts)
        assert g < 0.01


# ── Author extraction tests ────────────────────────────────────────────────

class TestExtractAuthors:

    def test_extract_from_enrichment_authors(self):
        entities = [
            type("E", (), {"attributes_json": json.dumps({"enrichment_authors": ["Alice", "Bob"]})})(),
            type("E", (), {"attributes_json": json.dumps({"enrichment_authors": ["Bob", "Carol"]})})(),
        ]
        authors = _extract_authors(entities)
        assert authors == {"Alice": 1, "Bob": 2, "Carol": 1}

    def test_extract_no_authors(self):
        entities = [
            type("E", (), {"attributes_json": json.dumps({})})(),
        ]
        authors = _extract_authors(entities)
        assert authors == {}


# ── International collaboration tests ───────────────────────────────────────

class TestInternationalCollaboration:

    def test_mixed_corpus(self):
        entities = []
        for _ in range(20):
            entities.append(type("E", (), {"attributes_json": json.dumps({"countries": ["US", "UK"]})})())
        for _ in range(60):
            entities.append(type("E", (), {"attributes_json": json.dumps({"countries": ["US"]})})())
        rate = _international_collaboration_rate(entities)
        assert abs(rate - 0.25) < 0.01

    def test_no_country_data(self):
        entities = [
            type("E", (), {"attributes_json": json.dumps({})})(),
        ]
        rate = _international_collaboration_rate(entities)
        assert rate is None


# ── Open Access rate tests ──────────────────────────────────────────────────

class TestOpenAccessRate:

    def test_partial_oa(self):
        entities = []
        for _ in range(30):
            entities.append(type("E", (), {"attributes_json": json.dumps({"is_open_access": True})})())
        for _ in range(30):
            entities.append(type("E", (), {"attributes_json": json.dumps({"is_open_access": False})})())
        rate = _open_access_rate(entities)
        assert abs(rate - 0.5) < 0.01

    def test_no_oa_data(self):
        entities = [
            type("E", (), {"attributes_json": json.dumps({})})(),
        ]
        rate = _open_access_rate(entities)
        assert rate is None


# ── Epistemic diversity tests ───────────────────────────────────────────────

class TestEpistemicDiversity:

    def test_uniform_distribution(self):
        entities = []
        for p in ["empiricist", "constructivist", "critical"]:
            for _ in range(33):
                entities.append(type("E", (), {
                    "attributes_json": json.dumps({"epistemic_profile": {"dominant": p}})
                })())
        d = _epistemic_diversity(entities, paradigm_count=3)
        assert d is not None
        assert abs(d - 1.0) < 0.05

    def test_single_paradigm(self):
        entities = []
        for _ in range(95):
            entities.append(type("E", (), {
                "attributes_json": json.dumps({"epistemic_profile": {"dominant": "empiricist"}})
            })())
        for _ in range(5):
            entities.append(type("E", (), {
                "attributes_json": json.dumps({"epistemic_profile": {"dominant": "critical"}})
            })())
        d = _epistemic_diversity(entities, paradigm_count=3)
        assert d is not None
        assert d < 0.3

    def test_no_profiles(self):
        entities = [
            type("E", (), {"attributes_json": json.dumps({})})(),
        ]
        d = _epistemic_diversity(entities, paradigm_count=3)
        assert d is None


# ── Newcomer rate tests ─────────────────────────────────────────────────────

class TestNewcomerRate:

    def test_year_with_many_newcomers(self):
        entities = []
        # 20 authors first appeared in 2024 only
        for i in range(20):
            entities.append(type("E", (), {
                "attributes_json": json.dumps({"enrichment_authors": [f"New{i}"], "year": 2024}),
                "normalized_json": None,
            })())
        # 30 authors who also appeared in 2023
        for i in range(30):
            entities.append(type("E", (), {
                "attributes_json": json.dumps({"enrichment_authors": [f"Old{i}"], "year": 2023}),
                "normalized_json": None,
            })())
            entities.append(type("E", (), {
                "attributes_json": json.dumps({"enrichment_authors": [f"Old{i}"], "year": 2024}),
                "normalized_json": None,
            })())
        rate = _newcomer_rate(entities, year=2024)
        assert rate is not None
        # 20 newcomers out of 50 unique authors in 2024
        assert abs(rate - 0.4) < 0.01

    def test_established_community(self):
        entities = []
        for i in range(50):
            entities.append(type("E", (), {
                "attributes_json": json.dumps({"enrichment_authors": [f"Author{i}"], "year": 2023}),
                "normalized_json": None,
            })())
            entities.append(type("E", (), {
                "attributes_json": json.dumps({"enrichment_authors": [f"Author{i}"], "year": 2024}),
                "normalized_json": None,
            })())
        # 5 true newcomers in 2024
        for i in range(5):
            entities.append(type("E", (), {
                "attributes_json": json.dumps({"enrichment_authors": [f"Newcomer{i}"], "year": 2024}),
                "normalized_json": None,
            })())
        rate = _newcomer_rate(entities, year=2024)
        assert rate is not None
        assert abs(rate - 5 / 55) < 0.01


# ── Integration: compute_health_metrics ─────────────────────────────────────

class TestComputeHealthMetrics:

    def test_full_metrics(self, db_session):
        for i in range(25):
            _entity(db_session, authors=[f"Author{i % 5}"],
                    countries=["US", "UK"] if i % 4 == 0 else ["US"],
                    is_oa=(i % 3 == 0), paradigm="empiricist" if i < 15 else "constructivist",
                    year=2023)
        result = compute_health_metrics(db_session, "science")
        assert "gini_authorship" in result
        assert "international_collaboration_rate" in result
        assert "open_access_rate" in result
        assert "epistemic_diversity" in result
        assert "newcomer_rate" in result
        assert result["gini_authorship"]["value"] is not None
        assert "by_year" in result["gini_authorship"]

    def test_empty_domain(self, db_session):
        result = compute_health_metrics(db_session, "science")
        for key in ["gini_authorship", "international_collaboration_rate",
                     "open_access_rate", "epistemic_diversity", "newcomer_rate"]:
            assert result[key]["value"] is None

    def test_small_sample_warning(self, db_session):
        for i in range(10):
            _entity(db_session, authors=[f"A{i}"], is_oa=True, year=2023)
        result = compute_health_metrics(db_session, "science")
        assert result["gini_authorship"].get("low_sample") is True


# ── Endpoint tests ──────────────────────────────────────────────────────────

class TestDomainHealthEndpoints:

    def test_health_endpoint(self, client, auth_headers, db_session):
        for i in range(10):
            _entity(db_session, authors=[f"A{i}"], is_oa=True, year=2023)
        resp = client.get("/analytics/domain-health/science", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "gini_authorship" in data

    def test_health_unconfigured_domain(self, client, auth_headers):
        resp = client.get("/analytics/domain-health/healthcare", headers=auth_headers)
        assert resp.status_code == 400

    def test_compare_endpoint(self, client, auth_headers, db_session):
        for i in range(5):
            _entity(db_session, authors=[f"A{i}"], year=2023)
        resp = client.get(
            "/analytics/domain-health/compare?domains=science",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "science" in data

    def test_viewer_can_access(self, client, viewer_headers, db_session):
        resp = client.get("/analytics/domain-health/science", headers=viewer_headers)
        assert resp.status_code == 200
