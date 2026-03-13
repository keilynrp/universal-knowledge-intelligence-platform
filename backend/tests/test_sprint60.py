"""
Sprint 60 — Webhooks UI Panel: backend tests.

Tests cover:
  - GET  /webhooks/stats          (summary stats)
  - POST /webhooks                (create)
  - GET  /webhooks                (list)
  - PUT  /webhooks/{id}           (update)
  - POST /webhooks/{id}/test      (sync test ping, returns delivery result)
  - GET  /webhooks/{id}/deliveries (paginated delivery history)
  - DELETE /webhooks/{id}         (cascade-deletes deliveries)
  - RBAC: viewer cannot access webhook endpoints
"""

import pytest
from backend import models


# ── helpers ───────────────────────────────────────────────────────────────────

def _create_webhook(client, auth_headers, url="https://example.com/hook", events=None):
    return client.post(
        "/webhooks",
        json={
            "url": url,
            "events": events or ["upload", "entity.update"],
            "secret": "test-secret",
        },
        headers=auth_headers,
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

class TestWebhookStats:
    def test_stats_empty(self, client, auth_headers, db_session):
        r = client.get("/webhooks/stats", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["active"] == 0
        assert data["failing"] == 0
        assert data["total_deliveries"] == 0

    def test_stats_after_create(self, client, auth_headers, db_session):
        _create_webhook(client, auth_headers)
        r = client.get("/webhooks/stats", headers=auth_headers)
        data = r.json()
        assert data["total"] == 1
        assert data["active"] == 1

    def test_stats_rbac_viewer(self, client, viewer_headers, db_session):
        r = client.get("/webhooks/stats", headers=viewer_headers)
        assert r.status_code == 403


# ── CRUD ──────────────────────────────────────────────────────────────────────

class TestWebhookCRUD:
    def test_create(self, client, auth_headers, db_session):
        r = _create_webhook(client, auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["url"] == "https://example.com/hook"
        assert "upload" in data["events"]

    def test_list(self, client, auth_headers, db_session):
        _create_webhook(client, auth_headers, url="https://a.com/h")
        _create_webhook(client, auth_headers, url="https://b.com/h")
        r = client.get("/webhooks", headers=auth_headers)
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_get_single(self, client, auth_headers, db_session):
        cr = _create_webhook(client, auth_headers)
        wid = cr.json()["id"]
        r = client.get(f"/webhooks/{wid}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == wid

    def test_get_not_found(self, client, auth_headers, db_session):
        r = client.get("/webhooks/99999", headers=auth_headers)
        assert r.status_code == 404

    def test_update(self, client, auth_headers, db_session):
        cr = _create_webhook(client, auth_headers)
        wid = cr.json()["id"]
        r = client.put(
            f"/webhooks/{wid}",
            json={"url": "https://new-url.com/hook", "is_active": False},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["url"] == "https://new-url.com/hook"
        assert r.json()["is_active"] is False

    def test_delete_cascades_deliveries(self, client, auth_headers, db_session):
        cr = _create_webhook(client, auth_headers)
        wid = cr.json()["id"]
        # Manually insert a delivery
        db_session.add(models.WebhookDelivery(
            webhook_id=wid, event="upload", url="https://example.com/hook",
            status_code=200, success=True,
        ))
        db_session.commit()
        assert db_session.query(models.WebhookDelivery).filter(
            models.WebhookDelivery.webhook_id == wid
        ).count() == 1
        # Delete the webhook
        r = client.delete(f"/webhooks/{wid}", headers=auth_headers)
        assert r.status_code == 200
        # Deliveries should be gone
        assert db_session.query(models.WebhookDelivery).filter(
            models.WebhookDelivery.webhook_id == wid
        ).count() == 0


# ── Test ping (sync) ─────────────────────────────────────────────────────────

class TestWebhookTestPing:
    def test_test_returns_delivery_result(self, client, auth_headers, db_session):
        """Test ping to an unreachable URL returns delivery result with error."""
        cr = _create_webhook(
            client, auth_headers,
            url="http://localhost:19999/nonexistent",
            events=["ping"],
        )
        wid = cr.json()["id"]
        r = client.post(f"/webhooks/{wid}/test", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "delivery_id" in data
        assert "latency_ms" in data
        assert data["success"] is False  # unreachable URL
        assert data["error"] is not None

    def test_test_not_found(self, client, auth_headers, db_session):
        r = client.post("/webhooks/99999/test", headers=auth_headers)
        assert r.status_code == 404


# ── Delivery history ──────────────────────────────────────────────────────────

class TestDeliveryHistory:
    def test_empty_deliveries(self, client, auth_headers, db_session):
        cr = _create_webhook(client, auth_headers)
        wid = cr.json()["id"]
        r = client.get(f"/webhooks/{wid}/deliveries", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_deliveries_after_test(self, client, auth_headers, db_session):
        cr = _create_webhook(
            client, auth_headers,
            url="http://localhost:19999/hook",
            events=["ping"],
        )
        wid = cr.json()["id"]
        client.post(f"/webhooks/{wid}/test", headers=auth_headers)
        r = client.get(f"/webhooks/{wid}/deliveries", headers=auth_headers)
        data = r.json()
        assert data["total"] >= 1
        item = data["items"][0]
        assert item["event"] == "ping"
        assert "latency_ms" in item

    def test_deliveries_pagination(self, client, auth_headers, db_session):
        cr = _create_webhook(client, auth_headers, events=["ping"])
        wid = cr.json()["id"]
        # Insert 5 deliveries
        for i in range(5):
            db_session.add(models.WebhookDelivery(
                webhook_id=wid, event="ping",
                url="https://example.com/hook",
                status_code=200, success=True,
            ))
        db_session.commit()
        r = client.get(f"/webhooks/{wid}/deliveries?page=1&size=2", headers=auth_headers)
        data = r.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 1

    def test_deliveries_not_found(self, client, auth_headers, db_session):
        r = client.get("/webhooks/99999/deliveries", headers=auth_headers)
        assert r.status_code == 404


# ── RBAC ──────────────────────────────────────────────────────────────────────

class TestWebhookRBAC:
    def test_viewer_cannot_list(self, client, viewer_headers, db_session):
        r = client.get("/webhooks", headers=viewer_headers)
        assert r.status_code == 403

    def test_viewer_cannot_create(self, client, viewer_headers, db_session):
        r = client.post(
            "/webhooks",
            json={"url": "https://x.com/h", "events": ["upload"]},
            headers=viewer_headers,
        )
        assert r.status_code == 403

    def test_editor_cannot_access(self, client, editor_headers, db_session):
        r = client.get("/webhooks", headers=editor_headers)
        assert r.status_code == 403


# ── Model tests ──────────────────────────────────────────────────────────────

class TestWebhookDeliveryModel:
    def test_model_fields(self, db_session):
        d = models.WebhookDelivery(
            webhook_id=1, event="upload", url="https://test.com",
            status_code=200, latency_ms=42, success=True,
        )
        db_session.add(d)
        db_session.commit()
        db_session.refresh(d)
        assert d.id is not None
        assert d.success is True
        assert d.latency_ms == 42
