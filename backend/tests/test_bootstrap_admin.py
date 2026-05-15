import pytest

from backend import models
from backend.auth import verify_password
from backend.bootstrap import ensure_bootstrap_super_admin, resolve_bootstrap_password_hash


@pytest.mark.usefixtures("db_session")
def test_bootstrap_creates_super_admin_when_missing(db_session, monkeypatch):
    existing_super_admin = (
        db_session.query(models.User)
        .filter(models.User.role == "super_admin")
        .all()
    )
    for user in existing_super_admin:
        db_session.delete(user)
    db_session.commit()

    monkeypatch.setenv("ADMIN_USERNAME", "superadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "supersecret123")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)

    ensure_bootstrap_super_admin(db_session)

    user = db_session.query(models.User).filter(models.User.username == "superadmin").first()
    assert user is not None
    assert user.role == "super_admin"
    assert user.is_active is True
    assert user.password_hash != "supersecret123"


@pytest.mark.usefixtures("db_session")
def test_bootstrap_repairs_missing_super_admin_role(db_session, monkeypatch):
    existing_super_admin = (
        db_session.query(models.User)
        .filter(models.User.role == "super_admin")
        .all()
    )
    for user in existing_super_admin:
        db_session.delete(user)
    db_session.commit()

    monkeypatch.setenv("ADMIN_USERNAME", "bootstrap_admin")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "prehashed-secret")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    db_session.add(models.User(
        username="bootstrap_admin",
        password_hash="old-hash",
        role="viewer",
        is_active=False,
    ))
    db_session.commit()

    ensure_bootstrap_super_admin(db_session)

    user = db_session.query(models.User).filter(models.User.username == "bootstrap_admin").first()
    assert user is not None
    assert user.role == "super_admin"
    assert user.is_active is True
    assert user.password_hash == "prehashed-secret"


@pytest.mark.usefixtures("db_session")
def test_bootstrap_is_noop_when_another_super_admin_exists(db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "secondary_admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "another-secret123")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)

    ensure_bootstrap_super_admin(db_session)

    user = db_session.query(models.User).filter(models.User.username == "secondary_admin").first()
    assert user is None


def test_resolve_bootstrap_password_hash_normalizes_compose_escaped_hash(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "$$2b$$12$$composeEscapedHashValue")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    assert resolve_bootstrap_password_hash() == "$2b$12$composeEscapedHashValue"


@pytest.mark.usefixtures("db_session")
def test_bootstrap_refreshes_password_for_existing_super_admin(db_session, monkeypatch):
    existing_super_admin = (
        db_session.query(models.User)
        .filter(models.User.role == "super_admin")
        .all()
    )
    for user in existing_super_admin:
        db_session.delete(user)
    db_session.commit()

    db_session.add(models.User(
        username="superadmin",
        password_hash="stale-hash",
        role="super_admin",
        is_active=True,
    ))
    db_session.commit()

    monkeypatch.setenv("ADMIN_USERNAME", "superadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "fresh-secret123")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)

    ensure_bootstrap_super_admin(db_session)

    user = db_session.query(models.User).filter(models.User.username == "superadmin").first()
    assert user is not None
    assert verify_password("fresh-secret123", user.password_hash) is True


@pytest.mark.usefixtures("db_session")
def test_bootstrap_preserves_existing_avatar(db_session, monkeypatch):
    existing_super_admin = (
        db_session.query(models.User)
        .filter(models.User.role == "super_admin")
        .all()
    )
    for user in existing_super_admin:
        db_session.delete(user)
    db_session.commit()

    avatar_url = "data:image/jpeg;base64,avatar-payload"
    db_session.add(models.User(
        username="superadmin",
        password_hash="stale-hash",
        role="super_admin",
        is_active=True,
        avatar_url=avatar_url,
        display_name="Existing Admin",
    ))
    db_session.commit()

    monkeypatch.setenv("ADMIN_USERNAME", "superadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "fresh-secret123")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "$$2b$$12$$ignoredWhenPlainPasswordExists")

    ensure_bootstrap_super_admin(db_session)

    user = db_session.query(models.User).filter(models.User.username == "superadmin").first()
    assert user is not None
    assert user.avatar_url == avatar_url
    assert user.display_name == "Existing Admin"
    assert verify_password("fresh-secret123", user.password_hash) is True
