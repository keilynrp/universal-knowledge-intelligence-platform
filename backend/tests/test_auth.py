"""
Tests for backend/auth.py — JWT creation, validation, and login endpoint.
"""
import os
import pytest
from datetime import timedelta
from jose import jwt

# Ensure env vars are set before import (conftest.py handles this,
# but be explicit for isolated runs)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_USERNAME", "testadmin")
os.environ.setdefault("ADMIN_PASSWORD", "testpassword")

from backend.auth import (
    authenticate_user,
    create_access_token,
    SECRET_KEY,
    ALGORITHM,
    verify_password,
)
from backend import models



# ── Unit: token creation ─────────────────────────────────────────────────────

def test_create_access_token_contains_subject():
    token = create_access_token(subject="testadmin", role="super_admin")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "testadmin"


def test_create_access_token_has_expiry():
    token = create_access_token(subject="testadmin", role="super_admin")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert "exp" in payload


def test_create_access_token_custom_expiry():
    token = create_access_token(subject="testadmin", role="super_admin", expires_delta=timedelta(minutes=1))
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "testadmin"


# ── Unit: authentication logic ───────────────────────────────────────────────

def test_authenticate_user_correct_credentials(session_factory):
    with session_factory() as db:
        assert authenticate_user(db, os.environ["ADMIN_USERNAME"], os.environ["ADMIN_PASSWORD"]) is not None


def test_authenticate_user_wrong_password(session_factory):
    with session_factory() as db:
        assert authenticate_user(db, "testadmin", "wrongpassword") is None


def test_authenticate_user_wrong_username(session_factory):
    with session_factory() as db:
        assert authenticate_user(db, "notauser", os.environ["ADMIN_PASSWORD"]) is None


def test_authenticate_user_empty_credentials(session_factory):
    with session_factory() as db:
        assert authenticate_user(db, "", "") is None


# ── Integration: /auth/token endpoint ───────────────────────────────────────

def test_login_success(client):
    response = client.post(
        "/auth/token",
        data={"username": os.environ["ADMIN_USERNAME"], "password": os.environ["ADMIN_PASSWORD"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password(client):
    response = client.post(
        "/auth/token",
        data={"username": "testadmin", "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


def test_login_wrong_username(client):
    response = client.post(
        "/auth/token",
        data={"username": "nobody", "password": os.environ["ADMIN_PASSWORD"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 401


def test_login_missing_fields(client):
    response = client.post("/auth/token", data={})
    assert response.status_code == 422  # Unprocessable entity


def test_password_reset_request_reports_unavailable_without_smtp(client):
    response = client.post("/auth/password-reset/request", json={"email": "testadmin@example.com"})

    assert response.status_code == 200
    assert response.json()["sent"] is False
    assert response.json()["reason"] == "smtp_not_configured"


def test_password_reset_request_creates_token_and_sends_email(client, db_session, monkeypatch):
    user = (
        db_session.query(models.User)
        .filter(models.User.username == os.environ["ADMIN_USERNAME"])
        .first()
    )
    user.email = "TestAdmin@Example.com"
    db_session.merge(models.NotificationSettings(
        id=1,
        enabled=True,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="mailer@example.com",
        smtp_password="secret",
        from_email="noreply@example.com",
    ))
    db_session.commit()
    sent = {}

    def fake_send(settings, to_address, subject, body):
        sent["to"] = to_address
        sent["subject"] = subject
        sent["body"] = body
        return True

    monkeypatch.setattr("backend.routers.auth_users.send_plain_email", fake_send)

    response = client.post("/auth/password-reset/request", json={"email": "testadmin@example.com"})

    assert response.status_code == 200
    assert response.json()["sent"] is True
    assert sent["to"] == "testadmin@example.com"
    assert "/login?reset_token=" in sent["body"]
    assert db_session.query(models.PasswordResetToken).filter_by(user_id=user.id).count() == 1


def test_password_reset_confirm_updates_password(client, db_session):
    user = (
        db_session.query(models.User)
        .filter(models.User.username == os.environ["ADMIN_USERNAME"])
        .first()
    )
    raw_token = "reset-token-for-test-12345678901234567890"
    from backend.routers.auth_users import _password_reset_token_hash
    from datetime import datetime, timedelta, timezone

    db_session.add(models.PasswordResetToken(
        user_id=user.id,
        token_hash=_password_reset_token_hash(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    ))
    db_session.commit()

    response = client.post(
        "/auth/password-reset/confirm",
        json={"token": raw_token, "new_password": "newpassword123"},
    )

    assert response.status_code == 200
    db_session.refresh(user)
    assert verify_password("newpassword123", user.password_hash) is True
    used_token = (
        db_session.query(models.PasswordResetToken)
        .filter_by(token_hash=_password_reset_token_hash(raw_token))
        .first()
    )
    assert used_token.used_at is not None
