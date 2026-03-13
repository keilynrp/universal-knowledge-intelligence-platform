"""
Sprint 51 — Audit Log backend
GET  /audit-log
GET  /audit-log/stats
GET  /audit-log/export
"""
import pytest


# ── Access control ────────────────────────────────────────────────────────────

def test_audit_log_requires_admin(client, auth_headers):
    """editor/viewer cannot list the audit log — only admin+."""
    resp = client.get("/audit-log", headers=auth_headers)
    # auth_headers is super_admin in conftest, so this should succeed
    assert resp.status_code == 200


def test_audit_log_editor_forbidden(client, editor_headers):
    resp = client.get("/audit-log", headers=editor_headers)
    assert resp.status_code in (401, 403)


def test_audit_log_viewer_forbidden(client, viewer_headers):
    resp = client.get("/audit-log", headers=viewer_headers)
    assert resp.status_code in (401, 403)


# ── Middleware writes entries ─────────────────────────────────────────────────

def test_mutation_creates_audit_entry(client, auth_headers, db_session):
    """A POST to any domain endpoint should produce an audit log entry."""
    # Trigger a mutation: create an annotation (editor-level endpoint)
    client.post(
        "/annotations",
        json={"entity_type": "authority", "entity_id": 9999, "body": "audit test"},
        headers=auth_headers,
    )
    resp = client.get("/audit-log", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # At least the POST above should have been logged
    assert data["total"] >= 1
    actions = [item["action"] for item in data["items"]]
    assert "CREATE" in actions


def test_audit_log_filter_by_action(client, auth_headers, db_session):
    """Filter by action=CREATE returns only CREATE rows."""
    resp = client.get("/audit-log?action=CREATE", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert item["action"] == "CREATE"


def test_audit_log_stats_shape(client, auth_headers, db_session):
    """Stats endpoint returns expected top-level keys."""
    resp = client.get("/audit-log/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "by_action" in data
    assert "by_resource" in data
    assert "top_users" in data
    assert "last_7_days" in data


def test_audit_log_export_csv(client, auth_headers, db_session):
    """CSV export returns a valid CSV with the correct content-type."""
    resp = client.get("/audit-log/export", headers=auth_headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    lines = resp.text.strip().splitlines()
    # Header row must be present
    assert lines[0].startswith("id,username,action")
