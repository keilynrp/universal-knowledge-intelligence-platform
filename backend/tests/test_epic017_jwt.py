# backend/tests/test_epic017_jwt.py
import importlib
from datetime import timedelta

import pytest
from jose import jwt


def _reload_auth(monkeypatch, primary, retiring=None):
    monkeypatch.setenv("JWT_SECRET_KEY", primary)
    if retiring is None:
        monkeypatch.delenv("JWT_SECRET_KEYS_RETIRING", raising=False)
    else:
        monkeypatch.setenv("JWT_SECRET_KEYS_RETIRING", retiring)
    import backend.auth as auth
    return importlib.reload(auth)


def test_token_signed_with_retiring_key_still_verifies(monkeypatch):
    old = "old-secret-key-0123456789"
    new = "new-secret-key-9876543210"
    auth_old = _reload_auth(monkeypatch, primary=old)
    token = auth_old.create_access_token("alice", "admin")
    auth_new = _reload_auth(monkeypatch, primary=new, retiring=old)
    payload = auth_new._decode_token(token)
    assert payload["sub"] == "alice"


def test_token_signed_with_unknown_key_is_rejected(monkeypatch):
    auth_new = _reload_auth(monkeypatch, primary="primary-key-aaa", retiring="retiring-key-bbb")
    forged = jwt.encode({"sub": "mallory"}, "unknown-key-zzz", algorithm="HS256")
    with pytest.raises(Exception):
        auth_new._decode_token(forged)


def test_signing_uses_primary_only(monkeypatch):
    new = "new-secret-key-9876543210"
    old = "old-secret-key-0123456789"
    auth_new = _reload_auth(monkeypatch, primary=new, retiring=old)
    token = auth_new.create_access_token("bob", "viewer")
    # Decodes under the primary directly
    assert jwt.decode(token, new, algorithms=["HS256"])["sub"] == "bob"


@pytest.fixture(autouse=True)
def _restore_auth_after_reload():
    """Restore backend.auth's module globals after each reload-based test here.

    These tests monkeypatch JWT env vars and importlib.reload(backend.auth),
    which mutates module-level SECRET_KEY/RETIRING_SECRET_KEYS. monkeypatch
    restores os.environ on teardown but does not re-import the module, so we
    reload once more afterward to pick the canonical test key back up and avoid
    leaking state into other test modules.
    """
    yield
    importlib.reload(importlib.import_module("backend.auth"))
