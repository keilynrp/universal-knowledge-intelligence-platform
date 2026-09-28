"""The SSO callback hands the browser a single-use code, never a token (#408).

It used to redirect to ``/login?token=<access>&refresh=<refresh>``, which put a
7-day refresh token in browser history, in ``Referer``, and in any proxy access
log on the way: the reason ``central-log-retention`` cannot turn on the Traefik
access log until this ships. The callback now stores only the hash of a
short-lived code, and the session and its tokens are created when the browser
exchanges that code with a ``POST``.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

from backend import models
from backend.routers import auth_users
from backend.routers.auth_users import _sso_code_hash

pytestmark = pytest.mark.security


@pytest.fixture()
def sso_user(auth_token, db_session):
    """The test admin, reached through SSO by its email, with SSO switched on."""
    user = (
        db_session.query(models.User)
        .filter(models.User.username == os.environ["ADMIN_USERNAME"])
        .first()
    )
    if not user.email:
        user.email = "testadmin@example.com"
    settings = auth_users.get_or_create_auth_settings(db_session)
    previous = (settings.sso_enabled, settings.sso_allowed_domains)
    settings.sso_enabled = True
    settings.sso_allowed_domains = ""
    db_session.commit()
    yield user
    settings.sso_enabled, settings.sso_allowed_domains = previous
    user.is_active = True
    db_session.commit()


def _callback(client, email):
    provider = AsyncMock(return_value={"userinfo": {"email": email}})
    with patch.object(auth_users.oauth.sso, "authorize_access_token", provider):
        return client.get("/sso/callback", follow_redirects=False)


def _code_from(response) -> str:
    query = parse_qs(urlsplit(response.headers["location"]).query)
    return query["sso_code"][0]


def _sessions_of(db_session, user) -> int:
    db_session.expire_all()
    return db_session.query(models.UserSession).filter_by(user_id=user.id).count()


class TestCallback:
    def test_redirect_carries_a_code_and_no_token(self, client, sso_user):
        response = _callback(client, sso_user.email)

        assert response.status_code in (302, 307)
        location = response.headers["location"]
        query = parse_qs(urlsplit(location).query)
        assert set(query) == {"sso_code"}
        # A JWT starts with a base64url-encoded '{"', which is "eyJ".
        assert "eyJ" not in location
        assert "token" not in location
        assert "refresh" not in location

    def test_no_session_exists_until_the_code_is_exchanged(self, client, sso_user, db_session):
        before = _sessions_of(db_session, sso_user)

        _callback(client, sso_user.email)

        assert _sessions_of(db_session, sso_user) == before

    def test_only_the_hash_of_the_code_is_stored(self, client, sso_user, db_session):
        code = _code_from(_callback(client, sso_user.email))

        db_session.expire_all()
        stored = db_session.query(models.SsoLoginCode).filter_by(user_id=sso_user.id).all()
        assert [row.code_hash for row in stored] == [_sso_code_hash(code)]
        assert all(code not in row.code_hash for row in stored)


class TestExchange:
    def test_a_code_yields_a_working_token_pair(self, client, sso_user, db_session):
        before = _sessions_of(db_session, sso_user)
        code = _code_from(_callback(client, sso_user.email))

        response = client.post("/sso/exchange", json={"code": code})

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["refresh_token"]
        me = client.get("/users/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert me.status_code == 200
        assert me.json()["username"] == sso_user.username
        assert _sessions_of(db_session, sso_user) == before + 1

    def test_a_code_works_once(self, client, sso_user):
        code = _code_from(_callback(client, sso_user.email))
        assert client.post("/sso/exchange", json={"code": code}).status_code == 200

        replay = client.post("/sso/exchange", json={"code": code})

        assert replay.status_code == 400
        assert "access_token" not in replay.json()

    def test_an_expired_code_yields_nothing(self, client, sso_user, db_session):
        code = "expired-sso-code-for-test-0123456789abcdef"
        db_session.add(models.SsoLoginCode(
            user_id=sso_user.id,
            code_hash=_sso_code_hash(code),
            expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).replace(tzinfo=None),
        ))
        db_session.commit()

        response = client.post("/sso/exchange", json={"code": code})

        assert response.status_code == 400

    def test_an_unknown_code_yields_nothing(self, client, sso_user):
        response = client.post(
            "/sso/exchange", json={"code": "never-issued-code-0123456789abcdef0123"}
        )

        assert response.status_code == 400

    def test_a_user_deactivated_after_the_callback_gets_nothing(
        self, client, sso_user, db_session
    ):
        code = _code_from(_callback(client, sso_user.email))
        sso_user.is_active = False
        db_session.commit()

        response = client.post("/sso/exchange", json={"code": code})

        assert response.status_code == 400
        assert "access_token" not in response.json()
