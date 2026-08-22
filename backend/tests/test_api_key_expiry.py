"""Regression tests for API key expiry — issue #215.

An API key created with `expires_days` returned 500 from every endpoint, while a
key without an expiry worked. `ApiKey.expires_at` is a naive column, but
`create_api_key` wrote an aware datetime and `verify_api_key` compared it against
an aware `datetime.now(timezone.utc)` — naive < aware raises TypeError, which
surfaces as a 500.

Both halves are guarded here: the value that gets persisted must be naive, and
verification must handle future, past, and absent expiries without raising.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend import models
from backend.routers.api_keys import verify_api_key

pytestmark = pytest.mark.postgres


def _create_key(client, auth_headers, **overrides) -> dict:
    payload = {"name": "test-key", "scopes": ["read"]}
    payload.update(overrides)
    resp = client.post("/api-keys", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _cleanup(session_factory, key_id: int) -> None:
    with session_factory() as db:
        db.query(models.ApiKey).filter(models.ApiKey.id == key_id).delete()
        db.commit()


# ── The persisted value ──────────────────────────────────────────────────────


class TestExpiryIsStoredNaive:
    """Fixing only the comparison would leave an aware value in a naive column,
    so the write side is pinned too.

    Honest limitation: these two assertions pass against the *unfixed* code as
    well, because SQLite drops tzinfo on storage — only Postgres would expose an
    aware write. They document the convention; they do not detect the #215
    regression. The tests below do that, and they demonstrably failed before the
    fix with `TypeError: can't compare offset-naive and offset-aware datetimes`.
    """

    def test_expires_at_is_persisted_without_tzinfo(self, client, auth_headers, session_factory):
        created = _create_key(client, auth_headers, name="naive-write", expires_days=30)
        try:
            with session_factory() as db:
                record = db.get(models.ApiKey, created["id"])
                assert record.expires_at is not None
                assert record.expires_at.tzinfo is None, (
                    "expires_at must match the repository's naive-UTC convention"
                )
        finally:
            _cleanup(session_factory, created["id"])

    def test_expiry_lands_roughly_the_requested_number_of_days_out(
        self, client, auth_headers, session_factory
    ):
        created = _create_key(client, auth_headers, name="naive-offset", expires_days=7)
        try:
            with session_factory() as db:
                record = db.get(models.ApiKey, created["id"])
                delta = record.expires_at - datetime.now(timezone.utc).replace(tzinfo=None)
                assert timedelta(days=6, hours=23) < delta < timedelta(days=7, minutes=1)
        finally:
            _cleanup(session_factory, created["id"])


# ── Verification ─────────────────────────────────────────────────────────────


class TestVerifyApiKeyHandlesExpiry:
    def test_future_expiry_verifies(self, client, auth_headers, session_factory):
        created = _create_key(client, auth_headers, name="future", expires_days=30)
        try:
            with session_factory() as db:
                record = verify_api_key(created["key"], db)
                # Read attributes inside the session: the instance detaches on exit.
                assert record is not None, "a key that has not expired must verify"
                assert record.id == created["id"]
        finally:
            _cleanup(session_factory, created["id"])

    def test_past_expiry_is_rejected_not_raised(self, client, auth_headers, session_factory):
        created = _create_key(client, auth_headers, name="past", expires_days=1)
        try:
            with session_factory() as db:
                record = db.get(models.ApiKey, created["id"])
                record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
                db.commit()
            with session_factory() as db:
                assert verify_api_key(created["key"], db) is None
        finally:
            _cleanup(session_factory, created["id"])

    def test_absent_expiry_verifies(self, client, auth_headers, session_factory):
        created = _create_key(client, auth_headers, name="no-expiry")
        try:
            with session_factory() as db:
                record = verify_api_key(created["key"], db)
                assert record is not None
        finally:
            _cleanup(session_factory, created["id"])


# ── End to end through the auth dependency ───────────────────────────────────


class TestAuthenticatedRequestWithExpiringKey:
    """The production symptom: 500 on every endpoint, for the acceptance path
    only. Rejection already worked."""

    @pytest.mark.parametrize("expires_days", [1, 30, 365])
    def test_request_with_expiring_key_succeeds(
        self, client, auth_headers, session_factory, expires_days
    ):
        created = _create_key(client, auth_headers, name=f"e2e-{expires_days}", expires_days=expires_days)
        try:
            resp = client.get("/domains", headers={"Authorization": f"Bearer {created['key']}"})
            assert resp.status_code == 200, (
                f"expiring key must authenticate, got {resp.status_code}: {resp.text[:200]}"
            )
        finally:
            _cleanup(session_factory, created["id"])

    def test_expired_key_gets_401_never_500(self, client, auth_headers, session_factory):
        created = _create_key(client, auth_headers, name="e2e-expired", expires_days=1)
        try:
            with session_factory() as db:
                record = db.get(models.ApiKey, created["id"])
                record.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
                db.commit()
            resp = client.get("/domains", headers={"Authorization": f"Bearer {created['key']}"})
            assert resp.status_code == 401, f"expected 401, got {resp.status_code}"
        finally:
            _cleanup(session_factory, created["id"])
