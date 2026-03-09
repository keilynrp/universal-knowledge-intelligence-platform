"""
Sprint 43 regression tests — Email Notification Settings.
"""
from unittest.mock import patch, MagicMock


# ── GET /notifications/settings — requires admin ──────────────────────────────

def test_get_settings_requires_admin(client):
    resp = client.get("/notifications/settings")
    assert resp.status_code in (401, 403)


def test_get_settings_requires_admin_not_viewer(client, viewer_headers):
    resp = client.get("/notifications/settings", headers=viewer_headers)
    assert resp.status_code in (401, 403)


# ── GET /notifications/settings — returns correct shape ──────────────────────

def test_get_settings_returns_shape(client, auth_headers, db_session):
    resp = client.get("/notifications/settings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    expected_keys = {
        "smtp_host", "smtp_port", "smtp_user",
        "from_email", "recipient_email", "enabled",
        "notify_on_enrichment_batch", "notify_on_authority_confirm",
    }
    assert expected_keys.issubset(data.keys())
    # smtp_password must NOT appear in the response
    assert "smtp_password" not in data


# ── PUT /notifications/settings — updates fields ─────────────────────────────

def test_put_settings_updates_fields(client, auth_headers, db_session):
    resp = client.put(
        "/notifications/settings",
        json={
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "recipient_email": "admin@example.com",
            "enabled": False,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["smtp_host"] == "smtp.example.com"
    assert data["recipient_email"] == "admin@example.com"
    assert data["enabled"] is False


# ── POST /notifications/test — disabled → sent=False ─────────────────────────

def test_test_email_returns_sent_false_when_disabled(client, auth_headers, db_session):
    # Ensure notifications are disabled
    client.put(
        "/notifications/settings",
        json={"enabled": False},
        headers=auth_headers,
    )
    resp = client.post("/notifications/test", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["sent"] is False


# ── POST /notifications/test — mocked send ───────────────────────────────────

def test_test_email_calls_send_notification(client, auth_headers, db_session):
    # Enable notifications first
    client.put(
        "/notifications/settings",
        json={"enabled": True, "recipient_email": "test@test.com", "smtp_host": "smtp.test.com"},
        headers=auth_headers,
    )
    with patch("backend.routers.notifications.send_notification") as mock_send:
        mock_send.return_value = True
        resp = client.post("/notifications/test", headers=auth_headers)
    assert resp.status_code == 200
    mock_send.assert_called_once()
    assert resp.json()["sent"] is True


# ── smtp_password not in response ────────────────────────────────────────────

def test_smtp_password_not_in_response(client, auth_headers, db_session):
    # Even after setting a password, it should never be returned
    client.put(
        "/notifications/settings",
        json={"smtp_password": "supersecret"},
        headers=auth_headers,
    )
    resp = client.get("/notifications/settings", headers=auth_headers)
    assert resp.status_code == 200
    assert "smtp_password" not in resp.json()


# ── Viewer cannot access settings ────────────────────────────────────────────

def test_viewer_cannot_access_settings(client, viewer_headers):
    resp = client.get("/notifications/settings", headers=viewer_headers)
    assert resp.status_code in (401, 403)
