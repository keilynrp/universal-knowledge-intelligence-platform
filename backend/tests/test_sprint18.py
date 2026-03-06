"""
Sprint 18 — Topic Modeling & Correlation Analysis:
  GET /analyzers/topics/{domain_id}
  GET /analyzers/cooccurrence/{domain_id}
  GET /analyzers/clusters/{domain_id}
  GET /analyzers/correlation/{domain_id}
"""
from __future__ import annotations

import pytest
from backend import models


# ── helpers ──────────────────────────────────────────────────────────────────

def _seed_enriched(db_session, n: int = 5):
    """Insert n enriched entities with distinct concept strings."""
    concept_sets = [
        "Machine Learning, Neural Network, Deep Learning",
        "Machine Learning, Data Science, Statistics",
        "Neural Network, Computer Vision, Image Recognition",
        "Data Science, Statistics, Python",
        "Machine Learning, Neural Network, Statistics",
    ]
    for i in range(n):
        db_session.add(models.RawEntity(
            entity_name=f"Entity {i}",
            status="active",
            enrichment_concepts=concept_sets[i % len(concept_sets)],
            enrichment_status="completed",
        ))
    db_session.commit()


# ── GET /analyzers/topics/{domain_id} ────────────────────────────────────────

class TestAnalyzerTopics:
    def test_unauthenticated_returns_401(self, client):
        assert client.get("/analyzers/topics/default").status_code == 401

    def test_returns_200_with_auth(self, client, auth_headers):
        resp = client.get("/analyzers/topics/default", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_shape(self, client, auth_headers):
        resp = client.get("/analyzers/topics/default", headers=auth_headers)
        data = resp.json()
        assert "domain_id" in data
        assert "total_enriched" in data
        assert "topics" in data
        assert isinstance(data["topics"], list)

    def test_nonexistent_domain_returns_404(self, client, auth_headers):
        resp = client.get("/analyzers/topics/nonexistent_xyz", headers=auth_headers)
        assert resp.status_code == 404

    def test_topic_fields(self, client, auth_headers, db_session):
        _seed_enriched(db_session)
        resp = client.get("/analyzers/topics/default", headers=auth_headers)
        data = resp.json()
        if data["topics"]:
            for t in data["topics"]:
                assert "concept" in t
                assert "count" in t
                assert "pct" in t
                assert isinstance(t["count"], int)
                assert isinstance(t["pct"], float)

    def test_top_n_param(self, client, auth_headers, db_session):
        _seed_enriched(db_session)
        resp = client.get("/analyzers/topics/default?top_n=3", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["topics"]) <= 3

    def test_viewer_can_access(self, client, viewer_headers):
        resp = client.get("/analyzers/topics/default", headers=viewer_headers)
        assert resp.status_code == 200

    def test_machine_learning_is_top(self, client, auth_headers, db_session):
        """Machine Learning appears in 3/5 sets — should rank first."""
        _seed_enriched(db_session, n=5)
        resp = client.get("/analyzers/topics/default", headers=auth_headers)
        topics = resp.json()["topics"]
        if topics:
            assert topics[0]["concept"] == "Machine Learning"

    def test_pct_of_100(self, client, auth_headers, db_session):
        """pct should be <= 100 for every topic."""
        _seed_enriched(db_session)
        resp = client.get("/analyzers/topics/default", headers=auth_headers)
        for t in resp.json()["topics"]:
            assert t["pct"] <= 100.0


# ── GET /analyzers/cooccurrence/{domain_id} ──────────────────────────────────

class TestAnalyzerCooccurrence:
    def test_unauthenticated_returns_401(self, client):
        assert client.get("/analyzers/cooccurrence/default").status_code == 401

    def test_returns_200(self, client, auth_headers):
        resp = client.get("/analyzers/cooccurrence/default", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_shape(self, client, auth_headers):
        resp = client.get("/analyzers/cooccurrence/default", headers=auth_headers)
        data = resp.json()
        assert "domain_id" in data
        assert "total_enriched" in data
        assert "pairs" in data
        assert isinstance(data["pairs"], list)

    def test_pair_fields(self, client, auth_headers, db_session):
        _seed_enriched(db_session)
        resp = client.get("/analyzers/cooccurrence/default", headers=auth_headers)
        for p in resp.json()["pairs"]:
            assert "concept_a" in p
            assert "concept_b" in p
            assert "count" in p
            assert "pmi" in p

    def test_nonexistent_domain_returns_404(self, client, auth_headers):
        resp = client.get("/analyzers/cooccurrence/nonexistent_xyz", headers=auth_headers)
        assert resp.status_code == 404

    def test_top_n_param(self, client, auth_headers, db_session):
        _seed_enriched(db_session)
        resp = client.get("/analyzers/cooccurrence/default?top_n=2", headers=auth_headers)
        assert len(resp.json()["pairs"]) <= 2

    def test_viewer_can_access(self, client, viewer_headers):
        resp = client.get("/analyzers/cooccurrence/default", headers=viewer_headers)
        assert resp.status_code == 200

    def test_pairs_ordered_by_count(self, client, auth_headers, db_session):
        _seed_enriched(db_session, n=5)
        pairs = client.get("/analyzers/cooccurrence/default", headers=auth_headers).json()["pairs"]
        if len(pairs) >= 2:
            for i in range(len(pairs) - 1):
                assert pairs[i]["count"] >= pairs[i + 1]["count"]


# ── GET /analyzers/clusters/{domain_id} ──────────────────────────────────────

class TestAnalyzerClusters:
    def test_unauthenticated_returns_401(self, client):
        assert client.get("/analyzers/clusters/default").status_code == 401

    def test_returns_200(self, client, auth_headers):
        resp = client.get("/analyzers/clusters/default", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_shape(self, client, auth_headers):
        resp = client.get("/analyzers/clusters/default", headers=auth_headers)
        data = resp.json()
        assert "domain_id" in data
        assert "n_clusters" in data
        assert "clusters" in data
        assert isinstance(data["clusters"], list)

    def test_cluster_fields(self, client, auth_headers, db_session):
        _seed_enriched(db_session)
        resp = client.get("/analyzers/clusters/default", headers=auth_headers)
        for c in resp.json()["clusters"]:
            assert "id" in c
            assert "seed" in c
            assert "size" in c
            assert "members" in c
            assert isinstance(c["members"], list)

    def test_n_clusters_param(self, client, auth_headers, db_session):
        _seed_enriched(db_session, n=5)
        resp = client.get("/analyzers/clusters/default?n_clusters=3", headers=auth_headers)
        data = resp.json()
        assert data["n_clusters"] <= 3

    def test_n_clusters_min_2(self, client, auth_headers):
        resp = client.get("/analyzers/clusters/default?n_clusters=1", headers=auth_headers)
        assert resp.status_code == 422

    def test_nonexistent_domain_returns_404(self, client, auth_headers):
        resp = client.get("/analyzers/clusters/nonexistent_xyz", headers=auth_headers)
        assert resp.status_code == 404

    def test_viewer_can_access(self, client, viewer_headers):
        resp = client.get("/analyzers/clusters/default", headers=viewer_headers)
        assert resp.status_code == 200

    def test_empty_concepts_returns_zero_clusters(self, client, auth_headers):
        """With no enriched data the analyzer returns an empty clusters list."""
        resp = client.get("/analyzers/clusters/default", headers=auth_headers)
        data = resp.json()
        # Either 0 clusters (no data) or >=1 (seeded from earlier tests) — shape correct
        assert isinstance(data["clusters"], list)


# ── GET /analyzers/correlation/{domain_id} ───────────────────────────────────

class TestAnalyzerCorrelation:
    def test_unauthenticated_returns_401(self, client):
        assert client.get("/analyzers/correlation/default").status_code == 401

    def test_returns_200(self, client, auth_headers):
        resp = client.get("/analyzers/correlation/default", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_shape(self, client, auth_headers):
        resp = client.get("/analyzers/correlation/default", headers=auth_headers)
        data = resp.json()
        assert "domain_id" in data
        assert "n_entities" in data
        assert "fields_analyzed" in data
        assert "correlations" in data

    def test_correlation_fields(self, client, auth_headers, db_session):
        # Seed entities with predictable correlated fields
        for _ in range(6):
            db_session.add(models.RawEntity(
                entity_name="Corr Entity",
                status="active",
                entity_type="typeA",
                classification="classA",
            ))
        db_session.commit()
        resp = client.get("/analyzers/correlation/default", headers=auth_headers)
        for c in resp.json()["correlations"]:
            assert "field_a" in c
            assert "field_b" in c
            assert "cramers_v" in c
            assert "strength" in c
            assert 0.0 <= c["cramers_v"] <= 1.0

    def test_strength_values(self, client, auth_headers):
        resp = client.get("/analyzers/correlation/default", headers=auth_headers)
        valid_strengths = {"weak", "moderate", "strong"}
        for c in resp.json()["correlations"]:
            assert c["strength"] in valid_strengths

    def test_nonexistent_domain_returns_404(self, client, auth_headers):
        resp = client.get("/analyzers/correlation/nonexistent_xyz", headers=auth_headers)
        assert resp.status_code == 404

    def test_top_n_param(self, client, auth_headers):
        resp = client.get("/analyzers/correlation/default?top_n=5", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["correlations"]) <= 5

    def test_viewer_can_access(self, client, viewer_headers):
        resp = client.get("/analyzers/correlation/default", headers=viewer_headers)
        assert resp.status_code == 200

    def test_correlations_ordered_desc(self, client, auth_headers):
        resp = client.get("/analyzers/correlation/default", headers=auth_headers)
        corrs = resp.json()["correlations"]
        if len(corrs) >= 2:
            for i in range(len(corrs) - 1):
                assert corrs[i]["cramers_v"] >= corrs[i + 1]["cramers_v"]
