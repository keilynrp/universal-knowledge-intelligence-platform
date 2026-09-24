"""Per-session revocation (#368 phase C.3).

The first incident tabletop (2026-09-22) found that containing one stolen token
meant disabling the account or rotating the global signing key, and that a token
belonging to the operator's own account could not be contained at all: the user
endpoints refuse to deactivate your own account or the last active super_admin.

These tests pin the capability that closes that: a token names its session, and
a session can be revoked on its own — without touching the account, without
touching anyone else's session, and without rotating a key.
"""
import os

import pytest
from jose import jwt
from starlette.websockets import WebSocketDisconnect

from backend import models
from backend.auth import ALGORITHM, SECRET_KEY, create_access_token

pytestmark = pytest.mark.security


def _login(client, username=None, password=None):
    resp = client.post(
        "/auth/token",
        data={
            "username": username or os.environ["ADMIN_USERNAME"],
            "password": password or os.environ["ADMIN_PASSWORD"],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _sid(token):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sid"]


# ── The token names its session ──────────────────────────────────────────────

def test_login_issues_a_token_that_names_its_session(client):
    tokens = _login(client)
    payload = jwt.decode(tokens["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert payload.get("sid"), "an access token must carry a session id"


def test_refresh_token_names_the_same_session(client):
    tokens = _login(client)
    assert _sid(tokens["refresh_token"]) == _sid(tokens["access_token"])


def test_login_records_the_session(client, session_factory):
    tokens = _login(client)
    with session_factory() as db:
        row = (
            db.query(models.UserSession)
            .filter(models.UserSession.sid == _sid(tokens["access_token"]))
            .first()
        )
        assert row is not None
        assert row.revoked_at is None


def test_a_token_without_a_session_id_is_rejected(client):
    """Tokens minted before this capability existed are not revocable, so they
    are not accepted. The cost is one re-login at deploy."""
    legacy = jwt.encode(
        {"sub": os.environ["ADMIN_USERNAME"], "role": "super_admin", "type": "access",
         "exp": 4102444800},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    assert client.get("/users/me", headers=_headers(legacy)).status_code == 401


def test_a_token_naming_an_unknown_session_is_rejected(client):
    token = create_access_token(
        subject=os.environ["ADMIN_USERNAME"], role="super_admin", sid="no-such-session"
    )
    assert client.get("/users/me", headers=_headers(token)).status_code == 401


# ── Revoking one session ─────────────────────────────────────────────────────

def test_revoking_a_session_kills_its_token_immediately(client):
    first = _login(client)
    second = _login(client)

    sessions = client.get("/auth/sessions", headers=_headers(second["access_token"])).json()
    target = next(s for s in sessions["items"] if s["sid"] == _sid(first["access_token"]))

    resp = client.delete(f"/auth/sessions/{target['id']}", headers=_headers(second["access_token"]))
    assert resp.status_code == 200, resp.text

    assert client.get("/users/me", headers=_headers(first["access_token"])).status_code == 401


def test_revoking_a_session_leaves_the_other_sessions_alone(client):
    first = _login(client)
    second = _login(client)

    sessions = client.get("/auth/sessions", headers=_headers(second["access_token"])).json()
    target = next(s for s in sessions["items"] if s["sid"] == _sid(first["access_token"]))
    client.delete(f"/auth/sessions/{target['id']}", headers=_headers(second["access_token"]))

    assert client.get("/users/me", headers=_headers(second["access_token"])).status_code == 200


def test_revoking_a_session_leaves_the_account_active(client, session_factory):
    """The whole point: containment without disabling the person."""
    first = _login(client)
    second = _login(client)
    sessions = client.get("/auth/sessions", headers=_headers(second["access_token"])).json()
    target = next(s for s in sessions["items"] if s["sid"] == _sid(first["access_token"]))
    client.delete(f"/auth/sessions/{target['id']}", headers=_headers(second["access_token"]))

    with session_factory() as db:
        user = (
            db.query(models.User)
            .filter(models.User.username == os.environ["ADMIN_USERNAME"])
            .first()
        )
        assert user.is_active is True


def test_revoking_a_session_kills_its_refresh_token_too(client):
    """Otherwise the holder simply refreshes and the revocation contained nothing."""
    first = _login(client)
    second = _login(client)
    sessions = client.get("/auth/sessions", headers=_headers(second["access_token"])).json()
    target = next(s for s in sessions["items"] if s["sid"] == _sid(first["access_token"]))
    client.delete(f"/auth/sessions/{target['id']}", headers=_headers(second["access_token"]))

    resp = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert resp.status_code == 401


def test_the_last_super_admin_can_revoke_their_own_session(client):
    """The tabletop landmine: the user endpoints refuse to deactivate your own
    account or the last active super_admin, which left a stolen owner token with
    no containment. Revoking a session is not deactivation and must be allowed."""
    first = _login(client)
    second = _login(client)
    sessions = client.get("/auth/sessions", headers=_headers(second["access_token"])).json()
    target = next(s for s in sessions["items"] if s["sid"] == _sid(first["access_token"]))

    resp = client.delete(f"/auth/sessions/{target['id']}", headers=_headers(second["access_token"]))
    assert resp.status_code == 200, resp.text


# ── Refresh keeps the session ────────────────────────────────────────────────

def test_refresh_keeps_the_same_session(client):
    tokens = _login(client)
    refreshed = client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).json()
    assert _sid(refreshed["access_token"]) == _sid(tokens["access_token"])


# ── Listing ──────────────────────────────────────────────────────────────────

def test_listing_marks_the_current_session(client):
    tokens = _login(client)
    body = client.get("/auth/sessions", headers=_headers(tokens["access_token"])).json()
    current = [s for s in body["items"] if s["current"]]
    assert len(current) == 1
    assert current[0]["sid"] == _sid(tokens["access_token"])


def test_listing_excludes_revoked_sessions(client):
    first = _login(client)
    second = _login(client)
    sessions = client.get("/auth/sessions", headers=_headers(second["access_token"])).json()
    target = next(s for s in sessions["items"] if s["sid"] == _sid(first["access_token"]))
    client.delete(f"/auth/sessions/{target['id']}", headers=_headers(second["access_token"]))

    body = client.get("/auth/sessions", headers=_headers(second["access_token"])).json()
    assert all(s["sid"] != _sid(first["access_token"]) for s in body["items"])


# ── Revoke everything except this one ────────────────────────────────────────

def test_revoke_others_keeps_the_current_session(client):
    first = _login(client)
    second = _login(client)

    resp = client.delete("/auth/sessions", headers=_headers(second["access_token"]))
    assert resp.status_code == 200, resp.text

    assert client.get("/users/me", headers=_headers(second["access_token"])).status_code == 200
    assert client.get("/users/me", headers=_headers(first["access_token"])).status_code == 401


# ── Another user's sessions, for incident response ───────────────────────────

def test_an_admin_can_revoke_another_users_session(client, session_factory, auth_headers):
    from backend.auth import hash_password

    with session_factory() as db:
        victim = db.query(models.User).filter(models.User.username == "ir_victim").first()
        if victim is None:
            victim = models.User(
                username="ir_victim",
                password_hash=hash_password("victim1234"),
                role="editor",
                is_active=True,
                failed_attempts=0,
                locked_until=None,
            )
            db.add(victim)
        else:
            victim.password_hash = hash_password("victim1234")
            victim.is_active = True
            victim.failed_attempts = 0
            victim.locked_until = None
        db.commit()
        victim_id = victim.id

    stolen = _login(client, "ir_victim", "victim1234")
    assert client.get("/users/me", headers=_headers(stolen["access_token"])).status_code == 200

    listed = client.get(f"/users/{victim_id}/sessions", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    target = next(s for s in listed.json()["items"] if s["sid"] == _sid(stolen["access_token"]))

    revoked = client.delete(f"/users/{victim_id}/sessions/{target['id']}", headers=auth_headers)
    assert revoked.status_code == 200, revoked.text

    assert client.get("/users/me", headers=_headers(stolen["access_token"])).status_code == 401


def test_a_non_admin_cannot_read_another_users_sessions(client, editor_headers, session_factory):
    with session_factory() as db:
        admin = (
            db.query(models.User)
            .filter(models.User.username == os.environ["ADMIN_USERNAME"])
            .first()
        )
        admin_id = admin.id

    resp = client.get(f"/users/{admin_id}/sessions", headers=editor_headers)
    assert resp.status_code == 403


def test_a_user_cannot_revoke_a_session_that_is_not_theirs(client, editor_headers):
    victim = _login(client)
    owner_view = client.get("/auth/sessions", headers=_headers(victim["access_token"])).json()
    target = owner_view["items"][0]["id"]

    resp = client.delete(f"/auth/sessions/{target}", headers=editor_headers)
    assert resp.status_code == 404
    assert client.get("/users/me", headers=_headers(victim["access_token"])).status_code == 200


# ── Evidence ─────────────────────────────────────────────────────────────────

def test_revocation_is_recorded_in_the_audit_log(client, session_factory, auth_headers):
    first = _login(client)
    second = _login(client)
    sessions = client.get("/auth/sessions", headers=_headers(second["access_token"])).json()
    target = next(s for s in sessions["items"] if s["sid"] == _sid(first["access_token"]))
    client.delete(f"/auth/sessions/{target['id']}", headers=_headers(second["access_token"]))

    with session_factory() as db:
        rows = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.endpoint.like("/auth/sessions%"))
            .all()
        )
        assert any(r.action == "DELETE" for r in rows)


def test_a_revoked_session_cannot_open_a_websocket(client):
    """A socket resolving the user by username alone would outlive the
    revocation and make the plan's containment step untrue."""
    first = _login(client)
    second = _login(client)
    sessions = client.get("/auth/sessions", headers=_headers(second["access_token"])).json()
    target = next(s for s in sessions["items"] if s["sid"] == _sid(first["access_token"]))
    client.delete(f"/auth/sessions/{target['id']}", headers=_headers(second["access_token"]))

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"/ws/system?token={first['access_token']}"),
    ):
        pass


def test_a_live_session_can_open_a_websocket(client):
    """Control for the test above: it must fail for the right reason."""
    tokens = _login(client)
    with client.websocket_connect(f"/ws/system?token={tokens['access_token']}") as ws:
        assert ws is not None
