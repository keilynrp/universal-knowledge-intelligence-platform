"""Outbound email takes its text from the catalog, in the resolved language.

Phase 7. This is the first string in the track that reaches someone **outside
the organisation**: everything migrated so far is read by logged-in operators,
while a password-reset email goes to whoever asked to recover an account.

The language question is at its hardest here. There is no session, no stored
preference, and the reader may open the mail on a different device than the one
that asked. The only signal is the `Accept-Language` of the request that
triggered it, plus an explicit parameter the frontend can pass because it knows
the UI language the user chose. That is exactly the chain `language_dependency`
already implements, so nothing new is invented for this case.
"""

import os

import pytest

from backend import models
from backend.i18n import catalog as catalog_module

pytestmark = pytest.mark.reporting


@pytest.fixture(autouse=True)
def _fresh_rate_limit():
    """Reset the limiter before each test in this file.

    `/auth/password-reset/request` allows 10/hour per IP, and every test here
    goes through it. Without this the file exhausts the quota and the *next*
    file to touch the endpoint fails with 429 — which is how it first showed up:
    `test_auth.py`'s long-standing reset test went red while passing in
    isolation. A test that breaks a neighbour is worse than one that fails.
    """
    from backend.routers.auth_users import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def smtp_ready(db_session):
    user = (
        db_session.query(models.User)
        .filter(models.User.username == os.environ["ADMIN_USERNAME"])
        .first()
    )
    user.email = "TestAdmin@Example.com"
    db_session.merge(
        models.NotificationSettings(
            id=1,
            enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="mailer@example.com",
            smtp_password="secret",
            from_email="noreply@example.com",
        )
    )
    db_session.commit()
    return user


@pytest.fixture()
def captured(monkeypatch):
    box: dict = {}

    def fake_send(settings, to_address, subject, body):
        box.update(to=to_address, subject=subject, body=body)
        return True

    monkeypatch.setattr("backend.routers.auth_users.send_plain_email", fake_send)
    return box


def _request_reset(client, captured, **kwargs):
    response = client.post(
        "/auth/password-reset/request", json={"email": "testadmin@example.com"}, **kwargs
    )
    assert response.status_code == 200, response.text
    assert response.json()["sent"] is True
    return captured


class TestSubjectResolvesPerLanguage:
    def test_spanish_is_served_in_spanish(self, client, smtp_ready, captured):
        box = _request_reset(client, captured, headers={"Accept-Language": "es"})

        assert "recupera tu contraseña" in box["subject"]

    def test_english_is_served_in_english(self, client, smtp_ready, captured):
        box = _request_reset(client, captured, headers={"Accept-Language": "en"})

        assert "reset your password" in box["subject"].lower()
        assert "contraseña" not in box["subject"]

    def test_no_signal_defaults_to_english(self, client, smtp_ready, captured):
        box = _request_reset(client, captured)

        assert "reset your password" in box["subject"].lower()

    def test_an_explicit_parameter_beats_the_header(self, client, smtp_ready, captured):
        """The frontend knows the UI language the user actually chose.

        `Accept-Language` is the browser's guess; a user who set the app to
        Spanish on an English-configured machine should still get Spanish.
        """
        response = client.post(
            "/auth/password-reset/request?language=es",
            json={"email": "testadmin@example.com"},
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        assert response.status_code == 200

        assert "recupera tu contraseña" in captured["subject"]

    def test_the_platform_name_is_interpolated_not_translated(
        self, client, smtp_ready, captured, monkeypatch
    ):
        monkeypatch.setenv("PLATFORM_NAME", "Acme Research")

        box = _request_reset(client, captured, headers={"Accept-Language": "es"})

        assert box["subject"].startswith("Acme Research")


class TestBodyResolvesPerLanguage:
    @pytest.mark.parametrize("language", ["en", "es"])
    def test_the_link_survives_in_both_languages(
        self, client, smtp_ready, captured, language
    ):
        box = _request_reset(client, captured, headers={"Accept-Language": language})

        assert "/login?reset_token=" in box["body"], (
            "the reset link must survive interpolation, or the mail is useless"
        )

    def test_english_body_carries_no_spanish(self, client, smtp_ready, captured):
        box = _request_reset(client, captured, headers={"Accept-Language": "en"})

        for marker in ("contraseña", "solicitud", "enlace", "correo"):
            assert marker not in box["body"].lower()


class TestTheTextComesFromTheCatalog:
    """Distinguishes migration from translation-in-place — as in phase 6."""

    def test_output_follows_the_catalog(self, client, smtp_ready, captured, monkeypatch):
        sentinel = "SENTINEL-EMAIL"
        real_keys = [
            key
            for key in catalog_module._load_catalog.__wrapped__("en")
            if key.startswith("email.")
        ]
        assert real_keys, "no email.* keys in the catalog"
        monkeypatch.setattr(
            catalog_module, "_load_catalog", lambda language: {k: sentinel for k in real_keys}
        )

        box = _request_reset(client, captured, headers={"Accept-Language": "en"})

        assert sentinel in box["subject"], "the subject still holds a literal"
        assert sentinel in box["body"], "the body still holds a literal"
