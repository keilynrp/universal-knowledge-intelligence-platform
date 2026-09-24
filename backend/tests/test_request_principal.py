"""Authentication records who a request acts as, and nothing when it refuses.

Phase 1 of the openspec change ``attribute-and-audit-reads`` (#375, #376). The
request log and the audit middleware will read the principal after the
response, instead of decoding the bearer token themselves. That only works if
two things hold, and these tests hold them:

1. A value the auth dependency sets on ``request.state`` is visible to a
   ``BaseHTTPMiddleware`` after ``call_next``. The design rests on this, and
   nothing in the app relied on it before.
2. Only an *accepted* credential leaves a principal. A revoked session, an
   expired token, an unknown key or an insufficient scope leave none, so a
   missing principal always means anonymous or refused.

The probe app uses the real dependencies against the test database. Only the
routes are fake.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from backend import models
from backend.auth import (
    _decode_token,
    create_access_token,
    get_current_user,
    get_current_user_optional,
)
from backend.database import get_db
from backend.principal import Principal, principal_of

ENFORCE_FLAG = "UKIP_API_KEY_SCOPES_ENFORCED"


class _Probe(BaseHTTPMiddleware):
    """Records what a middleware sees after the response, as the real ones will."""

    def __init__(self, app, seen: list):
        super().__init__(app)
        self.seen = seen

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        self.seen.append(principal_of(request))
        return response


@pytest.fixture()
def probe(session_factory):
    seen: list[Principal | None] = []
    app = FastAPI()

    @app.get("/probe")
    def read(_: Annotated[models.User, Depends(get_current_user)]):
        return {"ok": True}

    @app.post("/probe")
    def write(_: Annotated[models.User, Depends(get_current_user)]):
        return {"ok": True}

    @app.get("/probe/optional")
    def optional(user: Annotated[models.User | None, Depends(get_current_user_optional)]):
        return {"user": user.username if user else None}

    def _db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    # Two layers, like the real stack: both must see the same principal.
    app.add_middleware(_Probe, seen=seen)
    app.add_middleware(_Probe, seen=seen)
    return TestClient(app), seen


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_key(client, headers, scopes: list[str]) -> tuple[str, int]:
    resp = client.post("/api-keys", json={"name": "principal-test", "scopes": scopes}, headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["key"], body["id"]


def _admin_id(session_factory) -> int:
    with session_factory() as db:
        return db.query(models.User).filter(models.User.username == os.environ["ADMIN_USERNAME"]).one().id


# ── 1. The principal crosses into middleware ─────────────────────────────────

def test_a_jwt_request_leaves_user_and_session(probe, auth_token, session_factory):
    probe_client, seen = probe

    resp = probe_client.get("/probe", headers=_bearer(auth_token))

    assert resp.status_code == 200
    sid = _decode_token(auth_token)["sid"]
    expected = Principal(user_id=_admin_id(session_factory), session_id=sid)
    assert seen == [expected, expected], "both middleware layers must see the principal"


def test_an_api_key_request_leaves_user_and_key(probe, client, auth_headers, session_factory):
    probe_client, seen = probe
    key, key_id = _make_key(client, auth_headers, ["read"])

    resp = probe_client.get("/probe", headers=_bearer(key))

    assert resp.status_code == 200
    assert seen[-1] == Principal(user_id=_admin_id(session_factory), api_key_id=key_id)


def test_the_optional_dependency_records_it_too(probe, auth_token, session_factory):
    probe_client, seen = probe

    resp = probe_client.get("/probe/optional", headers=_bearer(auth_token))

    assert resp.json()["user"] is not None
    assert seen[-1] is not None and seen[-1].user_id == _admin_id(session_factory)


def test_an_anonymous_request_leaves_nothing(probe):
    probe_client, seen = probe

    resp = probe_client.get("/probe/optional")

    assert resp.json() == {"user": None}
    assert seen == [None, None]


# ── 2. A refused credential leaves nothing ───────────────────────────────────

def test_a_revoked_session_leaves_nothing(probe, auth_token, session_factory):
    probe_client, seen = probe
    sid = _decode_token(auth_token)["sid"]
    with session_factory() as db:
        row = db.query(models.UserSession).filter(models.UserSession.sid == sid).one()
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()

    assert probe_client.get("/probe", headers=_bearer(auth_token)).status_code == 401
    assert probe_client.get("/probe/optional", headers=_bearer(auth_token)).json() == {"user": None}
    assert seen == [None, None, None, None]


def test_an_expired_token_leaves_nothing(probe, auth_token):
    probe_client, seen = probe
    claims = _decode_token(auth_token)
    expired = create_access_token(
        claims["sub"], claims["role"], claims["sid"], expires_delta=timedelta(minutes=-1)
    )

    assert probe_client.get("/probe", headers=_bearer(expired)).status_code == 401
    assert seen == [None, None]


def test_an_unknown_key_leaves_nothing(probe):
    probe_client, seen = probe

    resp = probe_client.get("/probe", headers=_bearer("ukip_" + "0" * 40))

    assert resp.status_code == 401
    assert seen == [None, None]


def test_an_insufficient_scope_leaves_nothing(probe, client, auth_headers, monkeypatch):
    """A read key refused a write is refused, so it must not be attributed as acting."""
    monkeypatch.setenv(ENFORCE_FLAG, "1")
    probe_client, seen = probe
    key, _ = _make_key(client, auth_headers, ["read"])

    resp = probe_client.post("/probe", headers=_bearer(key))

    assert resp.status_code == 403
    assert seen == [None, None]


# ── The record itself ────────────────────────────────────────────────────────

def test_log_fields_omit_what_does_not_apply():
    """Absent, not null: a filter on api_key_id must never match a JWT request."""
    assert Principal(user_id=7, session_id="s").log_fields() == {"user_id": 7, "session_id": "s"}
    assert Principal(user_id=7, api_key_id=3).log_fields() == {"user_id": 7, "api_key_id": 3}
