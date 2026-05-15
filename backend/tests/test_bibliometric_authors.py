"""Tests for Author Productivity & H-index (task 2.4)."""
import json
import pytest
from backend import models
from backend.analyzers.author_metrics import compute_h_index


class TestHIndex:
    def test_standard_h_index(self):
        # 5 papers with >= 5 citations: [50, 30, 20, 10, 5]
        assert compute_h_index([50, 30, 20, 10, 5, 1]) == 5

    def test_h_index_zero_citations(self):
        assert compute_h_index([0, 0, 0]) == 0

    def test_h_index_all_equal(self):
        assert compute_h_index([5, 5, 5, 5, 5]) == 5

    def test_h_index_single_paper(self):
        assert compute_h_index([100]) == 1

    def test_h_index_empty(self):
        assert compute_h_index([]) == 0

    def test_h_index_one_each(self):
        assert compute_h_index([1, 1, 1]) == 1

    def test_h_index_descending(self):
        assert compute_h_index([10, 8, 5, 4, 3, 0]) == 4


def _seed_author_data(db, author_name: str, papers: list[dict], domain: str = "default"):
    """Seed authority record + entities for an author."""
    ar = models.AuthorityRecord(
        field_name="author",
        original_value=author_name,
        authority_source="openalex",
        authority_id=f"A{hash(author_name) % 10000}",
        canonical_label=author_name,
        confidence=0.9,
        status="confirmed",
    )
    db.add(ar)
    db.flush()

    for paper in papers:
        entity = models.RawEntity(
            primary_label=paper.get("title", f"Paper by {author_name}"),
            domain=domain,
            enrichment_citation_count=paper.get("citations", 0),
            enrichment_status="completed",
            attributes_json=json.dumps({"year": paper.get("year", 2023)}),
        )
        db.add(entity)
        db.flush()

        # Link via authority_record_links
        try:
            db.execute(
                models.Base.metadata.tables["authority_record_links"].insert().values(
                    authority_record_id=ar.id, entity_id=entity.id,
                )
            )
        except Exception:
            # Table might not exist, skip linking
            pass

    db.commit()
    return ar


class TestAuthorRankings:
    def test_author_rankings_empty(self, db_session):
        from backend.analyzers.author_metrics import author_rankings
        result = author_rankings("default")
        assert result["total_analyzed"] == 0
        assert result["authors"] == []


class TestAuthorEndpoints:
    def test_authors_endpoint_ok(self, client, auth_headers):
        resp = client.get("/analyzers/authors/default", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "authors" in data
        assert data["domain_id"] == "default"

    def test_authors_invalid_domain(self, client, auth_headers):
        resp = client.get("/analyzers/authors/nonexistent_xyz_999", headers=auth_headers)
        assert resp.status_code == 404

    def test_authors_requires_auth(self, client):
        resp = client.get("/analyzers/authors/default")
        assert resp.status_code in (401, 403)

    def test_author_detail_not_found(self, client, auth_headers):
        resp = client.get("/analyzers/authors/default/99999", headers=auth_headers)
        assert resp.status_code == 404

    def test_sort_by_param(self, client, auth_headers):
        resp = client.get(
            "/analyzers/authors/default?sort_by=total_publications",
            headers=auth_headers,
        )
        assert resp.status_code == 200
