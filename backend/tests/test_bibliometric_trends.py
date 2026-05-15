"""Tests for Trend Topics analyzer (task 1.4)."""
import json
import pytest
from backend import models
from backend.database import SessionLocal


def _seed_entities_with_years(concepts_by_year: dict[int, list[str]], domain: str = "default"):
    """Seed entities with concepts and year in attributes_json using a fresh session."""
    db = SessionLocal()
    try:
        for year, concepts_list in concepts_by_year.items():
            for concepts in concepts_list:
                db.add(models.RawEntity(
                    primary_label=f"Paper {year}",
                    domain=domain,
                    enrichment_concepts=concepts,
                    enrichment_status="completed",
                    attributes_json=json.dumps({"year": year}),
                ))
        db.commit()
    finally:
        db.close()


class TestTrendAnalyzer:
    def test_emerging_topic(self):
        _seed_entities_with_years({
            2020: ["AI"],
            2021: ["AI", "AI"],
            2022: ["AI", "AI", "AI"],
            2023: ["AI", "AI", "AI", "AI"],
            2024: ["AI", "AI", "AI", "AI", "AI"],
        })
        from backend.analyzers.trend_analysis import TrendAnalyzer
        result = TrendAnalyzer().trends("default")
        trends = result["trends"]
        assert len(trends) >= 1
        ai_trend = next(t for t in trends if t["concept"] == "AI")
        assert ai_trend["classification"] == "emerging"
        assert ai_trend["slope"] > 0

    def test_declining_topic(self):
        _seed_entities_with_years({
            2020: ["Legacy"] * 5,
            2021: ["Legacy"] * 4,
            2022: ["Legacy"] * 3,
            2023: ["Legacy"] * 2,
            2024: ["Legacy"],
        })
        from backend.analyzers.trend_analysis import TrendAnalyzer
        result = TrendAnalyzer().trends("default")
        legacy = next(t for t in result["trends"] if t["concept"] == "Legacy")
        assert legacy["classification"] == "declining"
        assert legacy["slope"] < 0

    def test_stable_topic(self):
        _seed_entities_with_years({
            2020: ["Stable"] * 3,
            2021: ["Stable"] * 3,
            2022: ["Stable"] * 3,
            2023: ["Stable"] * 3,
        })
        from backend.analyzers.trend_analysis import TrendAnalyzer
        result = TrendAnalyzer().trends("default")
        stable = next(t for t in result["trends"] if t["concept"] == "Stable")
        assert stable["classification"] == "stable"

    def test_min_years_filter(self):
        _seed_entities_with_years({
            2023: ["ShortLived"],
            2024: ["ShortLived"],
        })
        from backend.analyzers.trend_analysis import TrendAnalyzer
        result = TrendAnalyzer().trends("default", min_years=3)
        assert result["skipped_count"] >= 1
        assert not any(t["concept"] == "ShortLived" for t in result["trends"])

    def test_year_range_filter(self):
        _seed_entities_with_years({
            2018: ["Old"],
            2019: ["Old"],
            2020: ["Old", "New"],
            2021: ["New", "New"],
            2022: ["New", "New", "New"],
        })
        from backend.analyzers.trend_analysis import TrendAnalyzer
        result = TrendAnalyzer().trends("default", min_year=2020, max_year=2022)
        concepts = {t["concept"] for t in result["trends"]}
        # "Old" only has 1 year in range (2020), should be skipped with min_years=3
        assert "Old" not in concepts

    def test_empty_domain(self):
        """Use a domain name that is never seeded to test empty results."""
        from backend.analyzers.trend_analysis import TrendAnalyzer
        # Domain "all" won't 404, but with no data the result should reflect it
        # Use a domain that passes validation but has no entities
        _seed_entities_with_years({2020: ["placeholder"]}, domain="__empty_test_domain__")
        result = TrendAnalyzer().trends("__empty_test_domain__", min_years=99)
        assert result["trends"] == []

    def test_limit_param(self):
        _seed_entities_with_years({
            2020: ["A", "B", "C"],
            2021: ["A", "B", "C"],
            2022: ["A", "B", "C"],
        })
        from backend.analyzers.trend_analysis import TrendAnalyzer
        result = TrendAnalyzer().trends("default", limit=1)
        assert len(result["trends"]) <= 1

    def test_yearly_counts_in_response(self):
        _seed_entities_with_years({
            2020: ["X"],
            2021: ["X", "X"],
            2022: ["X", "X", "X"],
        })
        from backend.analyzers.trend_analysis import TrendAnalyzer
        result = TrendAnalyzer().trends("default")
        x_trend = next(t for t in result["trends"] if t["concept"] == "X")
        assert x_trend["yearly_counts"][2020] == 1
        assert x_trend["yearly_counts"][2021] == 2
        assert x_trend["yearly_counts"][2022] == 3
        assert x_trend["total_count"] == 6


class TestTrendEndpoint:
    def test_trends_endpoint_ok(self, client, auth_headers):
        _seed_entities_with_years({
            2020: ["ML"],
            2021: ["ML", "ML"],
            2022: ["ML", "ML", "ML"],
        })
        resp = client.get("/analyzers/trends/default?limit=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "trends" in data
        assert data["domain_id"] == "default"

    def test_trends_endpoint_invalid_domain(self, client, auth_headers):
        resp = client.get("/analyzers/trends/nonexistent_xyz_999", headers=auth_headers)
        assert resp.status_code == 404

    def test_trends_endpoint_requires_auth(self, client):
        resp = client.get("/analyzers/trends/default")
        assert resp.status_code in (401, 403)
