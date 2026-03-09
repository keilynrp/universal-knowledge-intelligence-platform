"""
Sprint 44 regression tests — Custom Branding Settings.
"""
import pytest


# ── GET /branding/settings — public (no auth) ─────────────────────────────────

def test_get_branding_is_public(client, db_session):
    resp = client.get("/branding/settings")
    assert resp.status_code == 200


# ── GET /branding/settings — returns correct shape ───────────────────────────

def test_get_branding_returns_shape(client, db_session):
    resp = client.get("/branding/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "platform_name" in data
    assert "logo_url" in data
    assert "accent_color" in data
    assert "footer_text" in data


# ── PUT /branding/settings — requires admin ───────────────────────────────────

def test_put_branding_requires_admin(client, db_session):
    resp = client.put(
        "/branding/settings",
        json={"platform_name": "Hacker"},
    )
    assert resp.status_code in (401, 403)


# ── PUT /branding/settings — updates platform_name ───────────────────────────

def test_put_branding_updates_platform_name(client, auth_headers, db_session):
    resp = client.put(
        "/branding/settings",
        json={"platform_name": "MyKnowledgeHub"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["platform_name"] == "MyKnowledgeHub"

    # Verify persisted
    get_resp = client.get("/branding/settings")
    assert get_resp.json()["platform_name"] == "MyKnowledgeHub"


# ── PUT /branding/settings — invalid accent color → 422 ──────────────────────

def test_put_branding_accent_color_validation(client, auth_headers, db_session):
    resp = client.put(
        "/branding/settings",
        json={"accent_color": "not-a-hex"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── Viewer cannot update branding ────────────────────────────────────────────

def test_viewer_cannot_update_branding(client, viewer_headers, db_session):
    resp = client.put(
        "/branding/settings",
        json={"platform_name": "ViewerBrand"},
        headers=viewer_headers,
    )
    assert resp.status_code in (401, 403)
