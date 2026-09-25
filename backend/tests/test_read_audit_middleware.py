"""Reads that matter leave an audit row; ordinary browsing does not (#375).

End to end through the real app and ``AuditMiddleware``. The rule itself is
tested exhaustively in ``test_read_audit_rules.py``; these tests hold what an
incident responder relies on: that the rows exist, name the session or key,
and carry no query values.
"""
import json

from backend import models
from backend.auth import _decode_token


def _rows(session_factory, endpoint: str, action: str | None = None) -> list[models.AuditLog]:
    with session_factory() as db:
        q = db.query(models.AuditLog).filter(models.AuditLog.endpoint == endpoint)
        if action:
            q = q.filter(models.AuditLog.action == action)
        rows = q.order_by(models.AuditLog.id).all()
        for row in rows:
            db.expunge(row)
        return rows


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_an_export_records_its_own_execution(client, auth_token, session_factory):
    """The tabletop's blind spot: downloading the audit log left no trace."""
    resp = client.get("/audit-log/export", headers=_bearer(auth_token))
    assert resp.status_code == 200

    [row] = _rows(session_factory, "/audit-log/export", "EXPORT")
    assert row.session_id == _decode_token(auth_token)["sid"]
    assert row.method == "GET" and row.status_code == 200


def test_a_pagination_sweep_is_recorded_page_by_page(client, auth_token, session_factory):
    for skip in (100, 200, 300):
        client.get(f"/entities?skip={skip}&limit=100", headers=_bearer(auth_token))

    rows = _rows(session_factory, "/entities", "READ")
    assert [json.loads(r.details)["skip"] for r in rows] == [100, 200, 300]
    assert {r.session_id for r in rows} == {_decode_token(auth_token)["sid"]}


def test_ordinary_browsing_is_not_recorded(client, auth_token, session_factory):
    client.get("/entities?limit=500", headers=_bearer(auth_token))
    client.get("/entities", headers=_bearer(auth_token))
    client.get("/users/me", headers=_bearer(auth_token))

    assert _rows(session_factory, "/entities") == []
    assert _rows(session_factory, "/users/me") == []


def test_every_api_key_read_is_recorded(client, auth_headers, session_factory):
    created = client.post("/api-keys", json={"name": "read-audit", "scopes": ["read"]}, headers=auth_headers).json()

    client.get("/users/me", headers=_bearer(created["key"]))

    [row] = _rows(session_factory, "/users/me", "READ")
    assert row.api_key_id == created["id"]
    assert row.session_id is None


def test_an_anonymous_read_is_not_recorded(client, session_factory):
    resp = client.get("/entities?skip=100")

    assert resp.status_code == 401
    assert _rows(session_factory, "/entities") == []


def test_query_values_never_reach_the_row(client, auth_token, session_factory):
    client.get("/entities", params={"q": "jane doe", "skip": "50"}, headers=_bearer(auth_token))

    [row] = _rows(session_factory, "/entities", "READ")
    assert json.loads(row.details) == {"query_keys": ["q", "skip"], "skip": 50}
    stored = " ".join(str(value) for value in vars(row).values())
    assert "jane" not in stored


def test_the_route_template_is_stored_not_the_concrete_path(client, auth_headers, session_factory):
    """A path segment can carry what a query string would; the id has its own column."""
    created = client.post("/api-keys", json={"name": "template", "scopes": ["read"]}, headers=auth_headers).json()

    client.get("/entities/999999", headers=_bearer(created["key"]))

    [row] = _rows(session_factory, "/entities/{entity_id}", "READ")
    assert row.entity_id == 999999
    assert _rows(session_factory, "/entities/999999") == []


def test_a_role_denied_read_of_the_audit_log_is_recorded(client, editor_headers, session_factory):
    """An authenticated credential reaching for the evidence is itself evidence."""
    resp = client.get("/audit-log", headers=editor_headers)
    assert resp.status_code == 403

    rows = _rows(session_factory, "/audit-log", "READ")
    assert rows and rows[-1].status_code == 403 and rows[-1].user_id is not None


def test_mutations_are_audited_exactly_as_before(client, auth_token, session_factory):
    client.patch("/users/me/profile", json={"bio": "x"}, headers=_bearer(auth_token))

    rows = _rows(session_factory, "/users/me/profile")
    assert [r.action for r in rows] == ["UPDATE"]
    assert rows[0].details is None
