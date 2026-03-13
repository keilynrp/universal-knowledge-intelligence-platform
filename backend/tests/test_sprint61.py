"""
Sprint 61 — Scheduled Imports: backend tests.

Tests cover:
  - POST /scheduled-imports           (create)
  - GET  /scheduled-imports           (list)
  - GET  /scheduled-imports/stats     (summary stats)
  - GET  /scheduled-imports/{id}      (get single)
  - PUT  /scheduled-imports/{id}      (update)
  - DELETE /scheduled-imports/{id}    (delete)
  - POST /scheduled-imports/{id}/trigger (manual trigger — store doesn't exist → error)
  - RBAC: viewers/editors cannot access
  - Model fields
"""

import pytest
from backend import models


# ── helpers ───────────────────────────────────────────────────────────────────

def _create_schedule(client, auth_headers, name="Nightly pull", store_id=None, interval=60):
    if store_id is None:
        # Create a dummy store connection first
        store_id = _ensure_store(client, auth_headers)
    return client.post(
        "/scheduled-imports",
        json={
            "store_id": store_id,
            "name": name,
            "interval_minutes": interval,
        },
        headers=auth_headers,
    )


def _ensure_store(client, auth_headers):
    """Create a minimal store for testing and return its id."""
    r = client.post(
        "/stores",
        json={
            "name": "Test Store",
            "platform": "woocommerce",
            "base_url": "https://test-store.example.com",
            "api_key": "key123",
            "api_secret": "secret123",
            "access_token": None,
            "custom_headers": None,
            "sync_direction": "pull",
            "notes": None,
        },
        headers=auth_headers,
    )
    assert r.status_code == 201, f"Store creation failed: {r.text}"
    return r.json()["id"]


# ── CRUD ──────────────────────────────────────────────────────────────────────

class TestScheduledImportCRUD:
    def test_create(self, client, auth_headers, db_session):
        r = _create_schedule(client, auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Nightly pull"
        assert data["interval_minutes"] == 60
        assert data["is_active"] is True
        assert data["next_run_at"] is not None

    def test_create_invalid_store(self, client, auth_headers, db_session):
        r = client.post(
            "/scheduled-imports",
            json={"store_id": 99999, "name": "Bad", "interval_minutes": 30},
            headers=auth_headers,
        )
        assert r.status_code == 404

    def test_list(self, client, auth_headers, db_session):
        store_id = _ensure_store(client, auth_headers)
        _create_schedule(client, auth_headers, name="A", store_id=store_id)
        _create_schedule(client, auth_headers, name="B", store_id=store_id)
        r = client.get("/scheduled-imports", headers=auth_headers)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 2
        # Should include store_name enrichment
        assert "store_name" in items[0]

    def test_get_single(self, client, auth_headers, db_session):
        cr = _create_schedule(client, auth_headers)
        sid = cr.json()["id"]
        r = client.get(f"/scheduled-imports/{sid}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == sid

    def test_get_not_found(self, client, auth_headers, db_session):
        r = client.get("/scheduled-imports/99999", headers=auth_headers)
        assert r.status_code == 404

    def test_update(self, client, auth_headers, db_session):
        cr = _create_schedule(client, auth_headers)
        sid = cr.json()["id"]
        r = client.put(
            f"/scheduled-imports/{sid}",
            json={"name": "Updated", "interval_minutes": 120, "is_active": False},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Updated"
        assert data["interval_minutes"] == 120
        assert data["is_active"] is False

    def test_delete(self, client, auth_headers, db_session):
        cr = _create_schedule(client, auth_headers)
        sid = cr.json()["id"]
        r = client.delete(f"/scheduled-imports/{sid}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["deleted"] == sid
        # Verify gone
        r = client.get(f"/scheduled-imports/{sid}", headers=auth_headers)
        assert r.status_code == 404


# ── Stats ─────────────────────────────────────────────────────────────────────

class TestScheduledImportStats:
    def test_stats_empty(self, client, auth_headers, db_session):
        r = client.get("/scheduled-imports/stats", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["active"] == 0
        assert data["total_runs"] == 0

    def test_stats_after_create(self, client, auth_headers, db_session):
        _create_schedule(client, auth_headers)
        r = client.get("/scheduled-imports/stats", headers=auth_headers)
        data = r.json()
        assert data["total"] >= 1
        assert data["active"] >= 1


# ── Manual trigger ────────────────────────────────────────────────────────────

class TestScheduledImportTrigger:
    def test_trigger_returns_result(self, client, auth_headers, db_session):
        """Trigger on a store with no real connection → should return error result."""
        cr = _create_schedule(client, auth_headers)
        sid = cr.json()["id"]
        r = client.post(f"/scheduled-imports/{sid}/trigger", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        # The store adapter will fail since the test store has no real endpoint
        assert "success" in data

    def test_trigger_not_found(self, client, auth_headers, db_session):
        r = client.post("/scheduled-imports/99999/trigger", headers=auth_headers)
        assert r.status_code == 404


# ── RBAC ──────────────────────────────────────────────────────────────────────

class TestScheduledImportRBAC:
    def test_viewer_cannot_list(self, client, viewer_headers, db_session):
        r = client.get("/scheduled-imports", headers=viewer_headers)
        assert r.status_code == 403

    def test_viewer_cannot_create(self, client, viewer_headers, db_session):
        r = client.post(
            "/scheduled-imports",
            json={"store_id": 1, "name": "X", "interval_minutes": 30},
            headers=viewer_headers,
        )
        assert r.status_code == 403

    def test_editor_cannot_access(self, client, editor_headers, db_session):
        r = client.get("/scheduled-imports", headers=editor_headers)
        assert r.status_code == 403


# ── Model test ────────────────────────────────────────────────────────────────

class TestScheduledImportModel:
    def test_model_fields(self, db_session):
        s = models.ScheduledImport(
            store_id=1, name="Test Import", interval_minutes=60,
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        assert s.id is not None
        assert s.total_runs == 0
        assert s.is_active is True
