"""Tests for bulk enrichment feedback: /enrich/progress and /enrich/bulk-ids guard."""
import pytest
from backend import models


class TestEnrichProgress:
    """POST /enrich/progress endpoint."""

    def test_returns_status_breakdown(self, client, auth_headers, db_session):
        e1 = models.RawEntity(primary_label="A", enrichment_status="completed", org_id=1)
        e2 = models.RawEntity(primary_label="B", enrichment_status="pending", org_id=1)
        e3 = models.RawEntity(primary_label="C", enrichment_status="failed", org_id=1)
        e4 = models.RawEntity(primary_label="D", enrichment_status="processing", org_id=1)
        db_session.add_all([e1, e2, e3, e4])
        db_session.commit()

        res = client.post(
            "/enrich/progress",
            json={"ids": [e1.id, e2.id, e3.id, e4.id]},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 4
        assert data["completed"] == 1
        assert data["pending"] == 1
        assert data["failed"] == 1
        assert data["processing"] == 1

    def test_empty_ids_returns_422(self, client, auth_headers):
        res = client.post("/enrich/progress", json={"ids": []}, headers=auth_headers)
        assert res.status_code == 422

    def test_requires_auth(self, client):
        res = client.post("/enrich/progress", json={"ids": [1, 2]})
        assert res.status_code == 401

    def test_unknown_ids_return_zeroes(self, client, auth_headers):
        res = client.post(
            "/enrich/progress",
            json={"ids": [99999, 99998]},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 2
        assert data["completed"] == 0
        assert data["pending"] == 0
        assert data["failed"] == 0
        assert data["processing"] == 0


class TestBulkIdsGuard:
    """POST /enrich/bulk-ids with force parameter."""

    def test_default_skips_completed(self, client, auth_headers, db_session):
        e1 = models.RawEntity(primary_label="X", enrichment_status="none", org_id=1)
        e2 = models.RawEntity(primary_label="Y", enrichment_status="completed", org_id=1)
        db_session.add_all([e1, e2])
        db_session.commit()

        res = client.post(
            "/enrich/bulk-ids",
            json={"ids": [e1.id, e2.id]},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["queued"] == 1
        assert data["skipped"] == 1

        db_session.expire_all()
        assert db_session.get(models.RawEntity, e1.id).enrichment_status == "pending"
        assert db_session.get(models.RawEntity, e2.id).enrichment_status == "completed"

    def test_force_re_queues_completed(self, client, auth_headers, db_session):
        e1 = models.RawEntity(primary_label="Z", enrichment_status="completed", org_id=1)
        db_session.add(e1)
        db_session.commit()

        res = client.post(
            "/enrich/bulk-ids",
            json={"ids": [e1.id], "force": True},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["queued"] == 1
        assert data["skipped"] == 0

        db_session.expire_all()
        assert db_session.get(models.RawEntity, e1.id).enrichment_status == "pending"

    def test_all_completed_without_force(self, client, auth_headers, db_session):
        e1 = models.RawEntity(primary_label="A", enrichment_status="completed", org_id=1)
        e2 = models.RawEntity(primary_label="B", enrichment_status="completed", org_id=1)
        db_session.add_all([e1, e2])
        db_session.commit()

        res = client.post(
            "/enrich/bulk-ids",
            json={"ids": [e1.id, e2.id]},
            headers=auth_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["queued"] == 0
        assert data["skipped"] == 2
