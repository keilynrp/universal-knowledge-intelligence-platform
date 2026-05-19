"""Sprint 87 — Dynamic faceting tests."""
import pytest
from backend import models

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _seed(db, **kwargs):
    defaults = dict(
        primary_label="Test", entity_type="paper", domain="default",
        validation_status="pending", enrichment_status="none", source="user",
    )
    defaults.update(kwargs)
    e = models.RawEntity(**defaults)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


class TestFacetEndpoint:
    def test_facets_returns_all_default_fields(self, client, auth_headers, db_session):
        _seed(db_session, entity_type="paper", validation_status="pending")
        res = client.get("/entities/facets", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        for field in ("entity_type", "domain", "validation_status", "enrichment_status", "source"):
            assert field in data

    def test_facets_counts_are_correct(self, client, auth_headers, db_session):
        _seed(db_session, entity_type="journal")
        _seed(db_session, entity_type="journal")
        _seed(db_session, entity_type="book")
        res = client.get("/entities/facets?fields=entity_type", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        journal_entry = next((x for x in data["entity_type"] if x["value"] == "journal"), None)
        book_entry    = next((x for x in data["entity_type"] if x["value"] == "book"), None)
        assert journal_entry is not None
        assert book_entry is not None
        assert journal_entry["count"] >= 2
        assert book_entry["count"] >= 1

    def test_facets_single_field(self, client, auth_headers, db_session):
        _seed(db_session, domain="science")
        res = client.get("/entities/facets?fields=domain", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "domain" in data
        assert "entity_type" not in data

    def test_facets_unknown_field_ignored(self, client, auth_headers, db_session):
        res = client.get("/entities/facets?fields=nonexistent_field,entity_type", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "nonexistent_field" not in data
        assert "entity_type" in data

    def test_facets_requires_auth(self, client):
        res = client.get("/entities/facets")
        assert res.status_code == 401

    def test_facets_ordered_by_count_desc(self, client, auth_headers, db_session):
        for _ in range(3):
            _seed(db_session, enrichment_status="completed")
        _seed(db_session, enrichment_status="none")
        res = client.get("/entities/facets?fields=enrichment_status", headers=auth_headers)
        assert res.status_code == 200
        values = res.json()["enrichment_status"]
        counts = [v["count"] for v in values]
        assert counts == sorted(counts, reverse=True)


class TestEntityFacetFilters:
    def test_filter_by_entity_type(self, client, auth_headers, db_session):
        _seed(db_session, primary_label="Paper One", entity_type="paper")
        _seed(db_session, primary_label="Book One",  entity_type="book")
        res = client.get("/entities?ft_entity_type=paper", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert all(e["entity_type"] == "paper" for e in data)

    def test_filter_by_validation_status(self, client, auth_headers, db_session):
        _seed(db_session, primary_label="Confirmed", validation_status="confirmed")
        _seed(db_session, primary_label="Pending",   validation_status="pending")
        res = client.get("/entities?ft_validation_status=confirmed", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert all(e["validation_status"] == "confirmed" for e in data)

    def test_filter_by_enrichment_status(self, client, auth_headers, db_session):
        _seed(db_session, primary_label="Done", enrichment_status="completed")
        _seed(db_session, primary_label="Raw",  enrichment_status="none")
        res = client.get("/entities?ft_enrichment_status=completed", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert all(e["enrichment_status"] == "completed" for e in data)

    def test_filter_by_domain(self, client, auth_headers, db_session):
        _seed(db_session, primary_label="SciPaper", domain="science")
        _seed(db_session, primary_label="DefPaper", domain="default")
        res = client.get("/entities?ft_domain=science", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert all(e["domain"] == "science" for e in data)

    def test_filter_by_source(self, client, auth_headers, db_session):
        _seed(db_session, primary_label="UserEntity", source="user")
        _seed(db_session, primary_label="DemoEntity", source="demo")
        res = client.get("/entities?ft_source=demo", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert all(e["source"] == "demo" for e in data)

    def test_filter_by_concept(self, client, auth_headers, db_session):
        _seed(db_session, primary_label="ML Paper", enrichment_concepts="Machine Learning, AI")
        _seed(db_session, primary_label="Bio Paper", enrichment_concepts="Biology")
        res = client.get("/entities?concept=Machine%20Learning", headers=auth_headers)
        assert res.status_code == 200
        labels = [e["primary_label"] for e in res.json()]
        assert "ML Paper" in labels
        assert "Bio Paper" not in labels

    def test_combined_facet_filters(self, client, auth_headers, db_session):
        _seed(db_session, primary_label="Match",    entity_type="paper", domain="science")
        _seed(db_session, primary_label="NoMatch1", entity_type="book",  domain="science")
        _seed(db_session, primary_label="NoMatch2", entity_type="paper", domain="default")
        res = client.get("/entities?ft_entity_type=paper&ft_domain=science", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert all(e["entity_type"] == "paper" and e["domain"] == "science" for e in data)
        labels = [e["primary_label"] for e in data]
        assert "Match" in labels
        assert "NoMatch1" not in labels
        assert "NoMatch2" not in labels

    def test_facet_filter_with_pagination(self, client, auth_headers, db_session):
        for i in range(5):
            _seed(db_session, primary_label=f"Paper {i}", entity_type="article")
        res = client.get("/entities?ft_entity_type=article&limit=2&skip=0", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data) <= 2
        assert all(e["entity_type"] == "article" for e in data)
