"""
Sprint 59 — Personal profile management tests.
  PATCH /users/me/profile  — any auth (email, display_name, bio)
"""
import pytest


class TestProfileUpdate:
    def test_requires_auth(self, client):
        r = client.patch("/users/me/profile", json={"display_name": "Test"})
        assert r.status_code == 401

    def test_update_display_name(self, client, auth_headers):
        r = client.patch(
            "/users/me/profile",
            json={"display_name": "John Doe"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == "John Doe"

    def test_update_bio(self, client, auth_headers):
        r = client.patch(
            "/users/me/profile",
            json={"bio": "Platform admin since 2024."},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["bio"] == "Platform admin since 2024."

    def test_update_email(self, client, auth_headers):
        r = client.patch(
            "/users/me/profile",
            json={"email": "newemail@example.com"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["email"] == "newemail@example.com"

    def test_update_all_fields(self, client, auth_headers):
        r = client.patch(
            "/users/me/profile",
            json={
                "display_name": "Alice Admin",
                "email": "alice@example.com",
                "bio": "Super admin of UKIP.",
            },
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["display_name"] == "Alice Admin"
        assert data["email"] == "alice@example.com"
        assert data["bio"] == "Super admin of UKIP."

    def test_partial_update_preserves_other_fields(self, client, auth_headers):
        # Set known state
        client.patch(
            "/users/me/profile",
            json={"display_name": "Before", "bio": "Keep me"},
            headers=auth_headers,
        )
        # Update only display_name
        r = client.patch(
            "/users/me/profile",
            json={"display_name": "After"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["display_name"] == "After"
        assert data["bio"] == "Keep me"

    def test_persists_in_users_me(self, client, auth_headers):
        client.patch(
            "/users/me/profile",
            json={"display_name": "Persistent Name"},
            headers=auth_headers,
        )
        r = client.get("/users/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["display_name"] == "Persistent Name"

    def test_bio_max_length_enforced(self, client, auth_headers):
        r = client.patch(
            "/users/me/profile",
            json={"bio": "x" * 501},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_display_name_max_length_enforced(self, client, auth_headers):
        r = client.patch(
            "/users/me/profile",
            json={"display_name": "a" * 101},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_viewer_can_update_own_profile(self, client, viewer_headers):
        r = client.patch(
            "/users/me/profile",
            json={"display_name": "Viewer User", "bio": "Just a viewer."},
            headers=viewer_headers,
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == "Viewer User"

    def test_duplicate_email_rejected(self, client, auth_headers, viewer_headers):
        # Get viewer's email first
        viewer_me = client.get("/users/me", headers=viewer_headers).json()
        viewer_email = viewer_me.get("email")
        if not viewer_email:
            pytest.skip("viewer has no email set")
        r = client.patch(
            "/users/me/profile",
            json={"email": viewer_email},
            headers=auth_headers,
        )
        assert r.status_code == 409
