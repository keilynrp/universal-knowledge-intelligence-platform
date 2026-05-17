"""Tests for platform authentication / SSO settings endpoints."""
import os
from unittest.mock import patch

import pytest


class TestPublicSsoSettings:
    """GET /auth/sso/settings — public, no auth required."""

    def test_returns_defaults(self, client):
        resp = client.get("/auth/sso/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sso_enabled"] is False
        assert data["sso_login_button_visible"] is False
        assert data["sso_provider_label"] == "SSO"
        assert data["sso_provider_configured"] is False

    def test_provider_configured_when_env_set(self, client):
        env = {
            "SSO_CLIENT_ID": "id123",
            "SSO_CLIENT_SECRET": "secret",
            "SSO_METADATA_URL": "https://example.com/.well-known/openid",
        }
        with patch.dict(os.environ, env):
            resp = client.get("/auth/sso/settings")
            assert resp.json()["sso_provider_configured"] is True

    def test_provider_not_configured_partial_env(self, client):
        env = {"SSO_CLIENT_ID": "id123", "SSO_CLIENT_SECRET": "", "SSO_METADATA_URL": ""}
        with patch.dict(os.environ, env):
            resp = client.get("/auth/sso/settings")
            assert resp.json()["sso_provider_configured"] is False


class TestAdminGetSettings:
    """GET /settings/auth — admin+ only."""

    def test_viewer_forbidden(self, client, viewer_headers):
        resp = client.get("/settings/auth", headers=viewer_headers)
        assert resp.status_code == 403

    def test_editor_forbidden(self, client, editor_headers):
        resp = client.get("/settings/auth", headers=editor_headers)
        assert resp.status_code == 403

    def test_admin_can_read(self, client, auth_headers):
        resp = client.get("/settings/auth", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "sso_enabled" in data
        assert "sso_auto_provision" in data
        assert "sso_default_role" in data
        assert "sso_allowed_domains" in data


class TestAdminUpdateSettings:
    """PUT /settings/auth — admin+ only."""

    def test_viewer_forbidden(self, client, viewer_headers):
        resp = client.put("/settings/auth", json={"sso_enabled": True}, headers=viewer_headers)
        assert resp.status_code == 403

    def test_update_sso_enabled(self, client, auth_headers):
        resp = client.put("/settings/auth", json={"sso_enabled": True}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["sso_enabled"] is True

        # Verify persistence
        resp2 = client.get("/settings/auth", headers=auth_headers)
        assert resp2.json()["sso_enabled"] is True

    def test_update_provider_label(self, client, auth_headers):
        resp = client.put(
            "/settings/auth",
            json={"sso_provider_label": "Okta SSO"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["sso_provider_label"] == "Okta SSO"

    def test_update_default_role_valid(self, client, auth_headers):
        resp = client.put("/settings/auth", json={"sso_default_role": "editor"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["sso_default_role"] == "editor"

    def test_update_default_role_invalid(self, client, auth_headers):
        resp = client.put("/settings/auth", json={"sso_default_role": "super_admin"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_update_allowed_domains(self, client, auth_headers):
        resp = client.put(
            "/settings/auth",
            json={"sso_allowed_domains": "example.com,corp.io"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["sso_allowed_domains"] == "example.com,corp.io"

    def test_update_button_visible_reflects_in_public(self, client, auth_headers):
        client.put(
            "/settings/auth",
            json={"sso_login_button_visible": True},
            headers=auth_headers,
        )
        public = client.get("/auth/sso/settings").json()
        assert public["sso_login_button_visible"] is True

    def test_partial_update_preserves_other_fields(self, client, auth_headers):
        # Set label first
        client.put("/settings/auth", json={"sso_provider_label": "Azure AD"}, headers=auth_headers)
        # Update only enabled
        client.put("/settings/auth", json={"sso_enabled": True}, headers=auth_headers)
        # Label should be preserved
        resp = client.get("/settings/auth", headers=auth_headers)
        assert resp.json()["sso_provider_label"] == "Azure AD"
        assert resp.json()["sso_enabled"] is True
