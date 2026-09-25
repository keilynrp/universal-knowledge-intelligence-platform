"""Audit rows name the principal authentication accepted, and only that.

Phase 3 of the openspec change ``attribute-and-audit-reads`` (#375, #376). The
audit middleware used to name the actor by decoding the bearer token as a JWT.
Reading the code for the proposal showed two consequences:

- a mutation made with an API key was audited with no actor at all, because a
  ``ukip_`` key is not a JWT;
- a request whose session had been revoked (#381) was refused, and its row
  still named the user, because decoding checks the signature, not the session.

Rows now carry what authentication accepted: user, plus the session or the API
key. A refused request names nobody. The key id survives the key.
"""
import os
from datetime import datetime, timezone

from backend import models
from backend.auth import _decode_token

PATH = "/users/me/profile"


def _last_row(session_factory, path: str = PATH) -> models.AuditLog:
    with session_factory() as db:
        row = (
            db.query(models.AuditLog)
            .filter(models.AuditLog.endpoint == path)
            .order_by(models.AuditLog.id.desc())
            .first()
        )
        assert row is not None, f"no audit row for {path}"
        db.expunge(row)
        return row


def _admin(session_factory) -> models.User:
    with session_factory() as db:
        user = db.query(models.User).filter(models.User.username == os.environ["ADMIN_USERNAME"]).one()
        db.expunge(user)
        return user


def _write_key(client, auth_headers) -> tuple[str, int]:
    created = client.post("/api-keys", json={"name": "audit-principal", "scopes": ["write"]}, headers=auth_headers)
    assert created.status_code == 201, created.text
    return created.json()["key"], created.json()["id"]


def test_a_jwt_mutation_names_user_and_session(client, auth_token, session_factory):
    resp = client.patch(PATH, json={"bio": "jwt"}, headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200, resp.text

    row = _last_row(session_factory)
    admin = _admin(session_factory)
    assert (row.user_id, row.username) == (admin.id, admin.username)
    assert row.session_id == _decode_token(auth_token)["sid"]
    assert row.api_key_id is None


def test_an_api_key_mutation_is_attributed(client, auth_headers, session_factory):
    """Before this change the row had no user at all."""
    key, key_id = _write_key(client, auth_headers)

    resp = client.patch(PATH, json={"bio": "key"}, headers={"Authorization": f"Bearer {key}"})
    assert resp.status_code == 200, resp.text

    row = _last_row(session_factory)
    admin = _admin(session_factory)
    assert (row.user_id, row.username, row.api_key_id) == (admin.id, admin.username, key_id)
    assert row.session_id is None


def test_a_revoked_token_lends_no_identity(client, auth_token, session_factory):
    """Refused is refused: the row must not read as the user having acted."""
    sid = _decode_token(auth_token)["sid"]
    with session_factory() as db:
        db.query(models.UserSession).filter(models.UserSession.sid == sid).one().revoked_at = datetime.now(timezone.utc)
        db.commit()

    resp = client.patch(PATH, json={"bio": "revoked"}, headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 401

    row = _last_row(session_factory)
    assert row.status_code == 401
    assert (row.user_id, row.username, row.session_id, row.api_key_id) == (None, None, None, None)


def test_deleting_a_key_leaves_its_evidence(client, auth_headers, session_factory):
    key, key_id = _write_key(client, auth_headers)
    client.patch(PATH, json={"bio": "before delete"}, headers={"Authorization": f"Bearer {key}"})
    row_id = _last_row(session_factory).id

    with session_factory() as db:
        db.delete(db.get(models.ApiKey, key_id))
        db.commit()

    with session_factory() as db:
        row = db.get(models.AuditLog, row_id)
        assert row is not None and row.api_key_id == key_id


def test_the_audit_log_api_returns_the_principal(client, auth_headers, auth_token, session_factory):
    client.patch(PATH, json={"bio": "listed"}, headers={"Authorization": f"Bearer {auth_token}"})

    items = client.get("/audit-log?limit=5", headers=auth_headers).json()["items"]
    mine = next(item for item in items if item["endpoint"] == PATH)
    assert mine["session_id"] == _decode_token(auth_token)["sid"]
    assert "api_key_id" in mine
