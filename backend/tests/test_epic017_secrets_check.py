# backend/tests/test_epic017_secrets_check.py
import importlib
from datetime import datetime, timezone, timedelta

import pytest

from backend import models


def _check(db):
    import backend.ops_checks as ops
    importlib.reload(ops)
    return ops._secrets_check(db)


def test_critical_when_jwt_default_key(db_session, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)   # falls back to insecure default
    monkeypatch.setenv("ENCRYPTION_KEY", "x" * 44)
    import backend.auth as auth; importlib.reload(auth)
    result = _check(db_session)
    assert result["status"] == "critical"


def test_warning_when_rotation_stale(db_session, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "real-secret")
    import backend.auth as auth; importlib.reload(auth)
    old = models.SecretRotationEvent(
        secret_name="ENCRYPTION_KEY", operator="x",
        rotated_at=datetime.now(timezone.utc) - timedelta(days=200))
    db_session.add(old); db_session.commit()
    result = _check(db_session)
    assert result["status"] == "warning"


def test_warning_when_retiring_keys_present(db_session, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "real-secret")
    monkeypatch.setenv("JWT_SECRET_KEYS_RETIRING", "old-secret")
    import backend.auth as auth; importlib.reload(auth)
    db_session.add(models.SecretRotationEvent(
        secret_name="ENCRYPTION_KEY", operator="x", rotated_at=datetime.now(timezone.utc)))
    db_session.commit()
    result = _check(db_session)
    assert result["status"] == "warning"


@pytest.fixture(autouse=True)
def _restore_modules_after_reload():
    """Reload backend.auth and backend.ops_checks back to canonical env state.

    These tests monkeypatch JWT/ENCRYPTION env vars and importlib.reload(auth);
    monkeypatch restores os.environ on teardown but not the imported modules, so
    we reload afterward to avoid leaking mutated SECRET_KEY into other modules.
    """
    yield
    importlib.reload(importlib.import_module("backend.auth"))
    importlib.reload(importlib.import_module("backend.ops_checks"))
