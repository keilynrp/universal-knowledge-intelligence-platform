"""The request log says who made each request (#376).

The first tabletop saw about 600 authenticated reads from an unfamiliar address
in the container log and could not attribute them to the stolen credential:
every line had method, path, status and IP, and nobody. These tests read the
*formatted* line, the one that reaches the container log, not the record's
attributes: the formatter emits a fixed list of fields, so an identity passed
in `extra` but missing from that list would be recorded and never printed.

Three properties matter in an incident:

- an authenticated line names the user and the session (or the API key), so
  it can be tied to a session that #381 can revoke;
- an anonymous or refused line names nobody: absent fields, not placeholders,
  so a filter on `user_id` never matches a line that had no identity;
- no credential ever reaches the log.
"""
import json
import logging
import os
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend import models
from backend.auth import _decode_token, get_current_user
from backend.database import get_db
from backend.logging_utils import RequestLoggingMiddleware, StructuredFormatter

IDENTITY = {"user_id", "session_id", "api_key_id"}


class _Lines(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(StructuredFormatter())
        self.lines: list[str] = []

    def emit(self, record):
        self.lines.append(self.format(record))


@pytest.fixture()
def request_log():
    handler = _Lines()
    logger = logging.getLogger("ukip.request")
    logger.addHandler(handler)
    previous = logger.level
    logger.setLevel(logging.INFO)
    try:
        yield handler.lines
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)


def _last(lines: list[str], path: str) -> dict:
    matching = [json.loads(line) for line in lines if json.loads(line).get("path") == path]
    assert matching, f"no request log line for {path}"
    return matching[-1]


def _admin_id(session_factory) -> int:
    with session_factory() as db:
        return db.query(models.User).filter(models.User.username == os.environ["ADMIN_USERNAME"]).one().id


def test_a_jwt_request_names_user_and_session(client, auth_token, request_log, session_factory):
    client.get("/users/me", headers={"Authorization": f"Bearer {auth_token}"})

    line = _last(request_log, "/users/me")
    assert line["user_id"] == _admin_id(session_factory)
    assert line["session_id"] == _decode_token(auth_token)["sid"]
    assert "api_key_id" not in line


def test_an_api_key_request_names_user_and_key(client, auth_headers, request_log, session_factory):
    created = client.post("/api-keys", json={"name": "log-test", "scopes": ["read"]}, headers=auth_headers).json()

    client.get("/users/me", headers={"Authorization": f"Bearer {created['key']}"})

    line = _last(request_log, "/users/me")
    assert line["user_id"] == _admin_id(session_factory)
    assert line["api_key_id"] == created["id"]
    assert "session_id" not in line


def test_an_anonymous_request_names_nobody(client, request_log):
    client.get("/health")

    assert IDENTITY.isdisjoint(_last(request_log, "/health"))


def test_a_refused_request_names_nobody(client, request_log):
    resp = client.get("/users/me", headers={"Authorization": "Bearer not-a-token"})

    assert resp.status_code == 401
    assert IDENTITY.isdisjoint(_last(request_log, "/users/me"))


def test_no_credential_reaches_the_log(client, auth_token, auth_headers, request_log):
    key = client.post("/api-keys", json={"name": "leak-test", "scopes": ["read"]}, headers=auth_headers).json()["key"]

    client.get("/users/me?q=jane", headers={"Authorization": f"Bearer {auth_token}"})
    client.get("/users/me", headers={"Authorization": f"Bearer {key}"})

    everything = "\n".join(request_log)
    assert auth_token not in everything
    assert key not in everything
    assert key[:12] not in everything, "not even the key prefix"
    assert "jane" not in everything, "query values stay out; the path is logged without them"


def test_the_text_format_carries_it_too(client, auth_token, request_log, monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "text")

    client.get("/users/me", headers={"Authorization": f"Bearer {auth_token}"})

    line = [entry for entry in request_log if "path=/users/me" in entry][-1]
    assert f"session_id={_decode_token(auth_token)['sid']}" in line
    assert "user_id=" in line


def test_a_failed_request_is_attributed_as_well(auth_token, session_factory, request_log):
    """An unhandled exception after authentication still says who was acting."""
    app = FastAPI()

    @app.get("/boom")
    def boom(_: Annotated[models.User, Depends(get_current_user)]):
        raise RuntimeError("handler failure")

    def _db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    app.add_middleware(RequestLoggingMiddleware)

    TestClient(app, raise_server_exceptions=False).get("/boom", headers={"Authorization": f"Bearer {auth_token}"})

    failed = [json.loads(line) for line in request_log if json.loads(line).get("event") == "request_failed"]
    assert failed, "no request_failed line"
    assert failed[-1]["user_id"] == _admin_id(session_factory)
    assert failed[-1]["session_id"] == _decode_token(auth_token)["sid"]
