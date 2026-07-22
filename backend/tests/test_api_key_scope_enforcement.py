"""
End-to-end enforcement of API key scopes.

Spec: openspec/changes/enforce-api-key-scopes/specs/api-key-scope-enforcement/spec.md
  - "API key scopes are authorization-bearing"
  - "Scope restricts but never elevates privilege"
  - "Enforcement is gated by a rollout flag with a warn mode"
  - "Scope enforcement covers every API key entry point"

Test technique
--------------
Most cases target ``POST /annotations`` with an empty body. The scope check runs
*before* the handler, so the response distinguishes the two outcomes cleanly and
without depending on what the endpoint does:

    403  -> the scope check denied the request
    422  -> the scope check passed; body validation rejected it

That keeps these tests about authorization rather than about annotations.
"""
from __future__ import annotations

import json

import pytest

from backend import models

ENFORCE_FLAG = "UKIP_API_KEY_SCOPES_ENFORCED"


@pytest.fixture()
def enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENFORCE_FLAG, "1")


@pytest.fixture()
def warn_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENFORCE_FLAG, "0")


def _make_key(client, headers, scopes: list[str], name: str = "scope-test") -> str:
    response = client.post(
        "/api-keys",
        json={"name": name, "scopes": scopes},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["key"]


def _bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


# ── Core denial / admission ───────────────────────────────────────────────────

class TestScopeIsAuthorizationBearing:
    def test_read_key_is_denied_a_mutation(self, client, auth_headers, enforced):
        key = _make_key(client, auth_headers, ["read"])
        response = client.post("/annotations", json={}, headers=_bearer(key))
        assert response.status_code == 403

    def test_denial_names_the_required_scope(self, client, auth_headers, enforced):
        key = _make_key(client, auth_headers, ["read"])
        response = client.post("/annotations", json={}, headers=_bearer(key))
        assert "write" in response.json()["detail"]

    def test_write_key_passes_the_scope_check(self, client, auth_headers, enforced):
        key = _make_key(client, auth_headers, ["write"])
        response = client.post("/annotations", json={}, headers=_bearer(key))
        assert response.status_code == 422  # reached validation, so scope passed

    def test_read_key_may_read(self, client, auth_headers, enforced):
        key = _make_key(client, auth_headers, ["read"])
        response = client.get("/annotations", headers=_bearer(key))
        assert response.status_code == 200

    def test_write_key_may_read(self, client, auth_headers, enforced):
        """Hierarchy: write implies read."""
        key = _make_key(client, auth_headers, ["write"])
        response = client.get("/annotations", headers=_bearer(key))
        assert response.status_code == 200


class TestAdminSurfaces:
    def test_write_key_is_denied_an_admin_surface(self, client, auth_headers, enforced):
        key = _make_key(client, auth_headers, ["write"])
        response = client.get("/users", headers=_bearer(key))
        assert response.status_code == 403

    def test_admin_key_reaches_an_admin_surface(self, client, auth_headers, enforced):
        key = _make_key(client, auth_headers, ["admin"])
        response = client.get("/users", headers=_bearer(key))
        assert response.status_code == 200

    def test_write_key_cannot_mint_a_new_key(self, client, auth_headers, enforced):
        """Privilege escalation: a write key must not create an admin key."""
        key = _make_key(client, auth_headers, ["write"])
        response = client.post(
            "/api-keys",
            json={"name": "escalation", "scopes": ["admin"]},
            headers=_bearer(key),
        )
        assert response.status_code == 403

    def test_read_key_may_read_its_own_profile(self, client, auth_headers, enforced):
        """/users is admin-gated, but /users/me is self-service."""
        key = _make_key(client, auth_headers, ["read"])
        response = client.get("/users/me", headers=_bearer(key))
        assert response.status_code == 200


class TestReadOverrides:
    def test_read_key_may_call_a_query_post(self, client, auth_headers, enforced):
        key = _make_key(client, auth_headers, ["read"])
        response = client.post("/nlq/query", json={}, headers=_bearer(key))
        assert response.status_code != 403

    def test_override_matching_uses_the_route_template(
        self, client, auth_headers, enforced
    ):
        """A parameterized override must match by template, not by concrete URL.

        If template resolution regressed, this route would fall through to the
        method rule, be classified `write`, and 403.
        """
        key = _make_key(client, auth_headers, ["read"])
        response = client.post(
            "/harmonization/preview/1", json={}, headers=_bearer(key)
        )
        assert response.status_code != 403


# ── Privilege invariants ──────────────────────────────────────────────────────

class TestScopeNeverElevates:
    def test_admin_scope_does_not_grant_a_viewer_admin_access(
        self, client, viewer_headers, enforced
    ):
        key = _make_key(client, viewer_headers, ["admin"], name="viewer-admin-key")
        response = client.get("/users", headers=_bearer(key))
        assert response.status_code == 403

    def test_that_denial_comes_from_rbac_not_scope(
        self, client, viewer_headers, warn_only
    ):
        """With enforcement off the scope check cannot be the cause — still 403."""
        key = _make_key(client, viewer_headers, ["admin"], name="viewer-admin-key-2")
        response = client.get("/users", headers=_bearer(key))
        assert response.status_code == 403

    def test_read_key_of_a_super_admin_is_still_restricted(
        self, client, auth_headers, enforced
    ):
        key = _make_key(client, auth_headers, ["read"])
        response = client.post("/annotations", json={}, headers=_bearer(key))
        assert response.status_code == 403


class TestJwtIsUnaffected:
    def test_jwt_mutation_is_not_scope_checked(self, client, auth_headers, enforced):
        response = client.post("/annotations", json={}, headers=auth_headers)
        assert response.status_code == 422

    def test_jwt_admin_surface_is_not_scope_checked(
        self, client, auth_headers, enforced
    ):
        response = client.get("/users", headers=auth_headers)
        assert response.status_code == 200


# ── Warn mode ─────────────────────────────────────────────────────────────────

def _violations(db) -> list[models.AuditLog]:
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.action == "api_key.scope_violation")
        .all()
    )


class TestWarnMode:
    def test_warn_mode_does_not_block(self, client, auth_headers, warn_only):
        key = _make_key(client, auth_headers, ["read"])
        response = client.post("/annotations", json={}, headers=_bearer(key))
        assert response.status_code == 422  # proceeded to validation

    def test_warn_mode_records_the_violation(
        self, client, auth_headers, warn_only, db
    ):
        before = len(_violations(db))
        key = _make_key(client, auth_headers, ["read"], name="warn-record")
        client.post("/annotations", json={}, headers=_bearer(key))
        after = _violations(db)
        assert len(after) == before + 1

        details = json.loads(after[-1].details)
        assert details["required"] == "write"
        assert details["granted"] == ["read"]
        assert details["enforced"] is False
        assert details["key_prefix"] == key[:16]

    def test_violation_record_omits_the_credential(
        self, client, auth_headers, warn_only, db
    ):
        key = _make_key(client, auth_headers, ["read"], name="warn-secret")
        client.post("/annotations", json={}, headers=_bearer(key))
        record = _violations(db)[-1]

        serialized = f"{record.details} {record.endpoint} {record.method}"
        assert key not in serialized
        assert key[16:] not in serialized  # the random remainder must never appear

    def test_satisfied_requests_record_nothing(
        self, client, auth_headers, warn_only, db
    ):
        before = len(_violations(db))
        key = _make_key(client, auth_headers, ["write"], name="warn-clean")
        client.post("/annotations", json={}, headers=_bearer(key))
        assert len(_violations(db)) == before

    def test_enforced_denial_is_also_recorded(
        self, client, auth_headers, enforced, db
    ):
        before = len(_violations(db))
        key = _make_key(client, auth_headers, ["read"], name="enforced-record")
        client.post("/annotations", json={}, headers=_bearer(key))
        after = _violations(db)
        assert len(after) == before + 1
        assert json.loads(after[-1].details)["enforced"] is True


class TestFlagDefault:
    def test_default_is_warn_mode(self, client, auth_headers, monkeypatch):
        """An unset flag must not break live integrations on deploy."""
        monkeypatch.delenv(ENFORCE_FLAG, raising=False)
        key = _make_key(client, auth_headers, ["read"], name="default-mode")
        response = client.post("/annotations", json={}, headers=_bearer(key))
        assert response.status_code == 422

    def test_health_reports_effective_state(self, client, enforced):
        response = client.get("/health")
        assert response.status_code == 200
        features = response.json()["features"]
        assert features["api_key_scopes_enforced"] is True


# ── Optional-auth dependency ──────────────────────────────────────────────────

class TestOptionalAuthPath:
    """No write-classified endpoint currently uses optional auth, so the
    dependency is exercised directly rather than through a route."""

    @pytest.mark.asyncio
    async def test_optional_auth_denies_rather_than_downgrades(
        self, client, auth_headers, enforced, db_session
    ):
        from fastapi import HTTPException
        from starlette.datastructures import Headers
        from starlette.requests import Request

        from backend.auth import get_current_user_optional

        key = _make_key(client, auth_headers, ["read"], name="optional-auth")
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/annotations",
                "headers": Headers({}).raw,
                "query_string": b"",
            }
        )

        with pytest.raises(HTTPException) as denied:
            await get_current_user_optional(
                request=request, token=key, db=db_session
            )
        assert denied.value.status_code == 403
