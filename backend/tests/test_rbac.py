"""
RBAC regression tests:
- /users endpoints require super_admin (401 without auth, 403 for lower roles)
- POST /users creates a user → 201
- Duplicate username → 409
- GET /users/me works for any authenticated role
- PUT /users/{id} updates user
- DELETE /users/{id} soft-deletes user
- Editor can write entities data (POST /upload → 201)
- Viewer cannot write (POST /upload → 403)
- Viewer can read (GET /entities → 200)
- Viewer cannot access stores (GET /stores → 403)
"""
import io
import pytest

pytestmark = pytest.mark.security


# ── /users requires auth ──────────────────────────────────────────────────────

def test_list_users_without_auth_returns_401(client):
    assert client.get("/users").status_code == 401


def test_list_users_with_viewer_returns_403(client, viewer_headers):
    assert client.get("/users", headers=viewer_headers).status_code == 403


def test_list_users_with_editor_returns_403(client, editor_headers):
    assert client.get("/users", headers=editor_headers).status_code == 403


def test_list_users_with_super_admin_returns_200(client, auth_headers):
    resp = client.get("/users", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    # At least the bootstrap super_admin must be present
    assert any(u["username"] == "testadmin" for u in resp.json())


# ── POST /users ───────────────────────────────────────────────────────────────

def test_create_user_returns_201(client, auth_headers):
    resp = client.post(
        "/users",
        json={"username": "rbac_new_user", "password": "password123", "role": "admin"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "rbac_new_user"
    assert data["role"] == "admin"
    assert data["is_active"] is True


def test_create_user_duplicate_returns_409(client, auth_headers):
    # First creation
    client.post(
        "/users",
        json={"username": "rbac_dup_user", "password": "password123", "role": "viewer"},
        headers=auth_headers,
    )
    # Second creation with same username
    resp = client.post(
        "/users",
        json={"username": "rbac_dup_user", "password": "password456", "role": "viewer"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


def test_create_user_short_password_returns_422(client, auth_headers):
    resp = client.post(
        "/users",
        json={"username": "rbac_short_pw", "password": "short", "role": "viewer"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_user_invalid_role_returns_422(client, auth_headers):
    resp = client.post(
        "/users",
        json={"username": "rbac_bad_role", "password": "password123", "role": "superuser"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ── GET /users/me ─────────────────────────────────────────────────────────────

def test_get_my_profile_super_admin(client, auth_headers):
    resp = client.get("/users/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "testadmin"
    assert resp.json()["role"] == "super_admin"


def test_get_my_profile_editor(client, editor_headers):
    resp = client.get("/users/me", headers=editor_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "editor"


def test_get_my_profile_viewer(client, viewer_headers):
    resp = client.get("/users/me", headers=viewer_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "viewer"


def test_get_my_profile_without_auth_returns_401(client):
    assert client.get("/users/me").status_code == 401


# ── GET /users/{id} ───────────────────────────────────────────────────────────

def test_get_user_by_id_super_admin(client, auth_headers):
    users = client.get("/users", headers=auth_headers).json()
    user_id = users[0]["id"]
    resp = client.get(f"/users/{user_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == user_id


def test_get_user_by_id_editor_returns_403(client, editor_headers):
    resp = client.get("/users/1", headers=editor_headers)
    assert resp.status_code == 403


def test_get_user_nonexistent_returns_404(client, auth_headers):
    resp = client.get("/users/99999", headers=auth_headers)
    assert resp.status_code == 404


# ── PUT /users/{id} ───────────────────────────────────────────────────────────

def test_update_user_email(client, auth_headers):
    # Create a user to update
    create_resp = client.post(
        "/users",
        json={"username": "rbac_update_me", "password": "password123", "role": "viewer"},
        headers=auth_headers,
    )
    user_id = create_resp.json()["id"]
    resp = client.put(
        f"/users/{user_id}",
        json={"email": "updated@example.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "updated@example.com"


def test_update_user_role(client, auth_headers):
    create_resp = client.post(
        "/users",
        json={"username": "rbac_role_change", "password": "password123", "role": "viewer"},
        headers=auth_headers,
    )
    user_id = create_resp.json()["id"]
    resp = client.put(
        f"/users/{user_id}",
        json={"role": "editor"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "editor"


# ── DELETE /users/{id} ────────────────────────────────────────────────────────

def test_delete_user_deactivates(client, auth_headers):
    create_resp = client.post(
        "/users",
        json={"username": "rbac_to_delete", "password": "password123", "role": "viewer"},
        headers=auth_headers,
    )
    user_id = create_resp.json()["id"]
    resp = client.delete(f"/users/{user_id}", headers=auth_headers)
    assert resp.status_code == 200
    # Verify user is now inactive
    detail = client.get(f"/users/{user_id}", headers=auth_headers)
    assert detail.json()["is_active"] is False


def test_cannot_delete_self(client, auth_headers):
    me = client.get("/users/me", headers=auth_headers).json()
    resp = client.delete(f"/users/{me['id']}", headers=auth_headers)
    assert resp.status_code == 400


# ── Role-based access to data endpoints ──────────────────────────────────────

def test_viewer_can_read_entities(client, viewer_headers):
    resp = client.get("/entities", headers=viewer_headers)
    assert resp.status_code == 200


def test_viewer_cannot_upload(client, viewer_headers):
    csv_bytes = b"entity_name,sku\nWidget,SKU-001\n"
    resp = client.post(
        "/upload",
        files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=viewer_headers,
    )
    assert resp.status_code == 403


def test_editor_can_upload(client, editor_headers):
    csv_bytes = b"entity_name,sku\nWidget,SKU-001\n"
    resp = client.post(
        "/upload",
        files={"file": ("test.csv", io.BytesIO(csv_bytes), "text/csv")},
        headers=editor_headers,
    )
    assert resp.status_code == 201


def test_viewer_cannot_access_stores(client, viewer_headers):
    resp = client.get("/stores", headers=viewer_headers)
    assert resp.status_code == 403


def test_editor_cannot_access_stores(client, editor_headers):
    resp = client.get("/stores", headers=editor_headers)
    assert resp.status_code == 403


def test_admin_can_access_stores(client, auth_headers):
    # super_admin has full access
    resp = client.get("/stores", headers=auth_headers)
    assert resp.status_code == 200
