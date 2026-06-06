import importlib

from cryptography.fernet import Fernet


def _reload_encryption(monkeypatch, primary=None, retiring=None):
    if primary is None:
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    else:
        monkeypatch.setenv("ENCRYPTION_KEY", primary)
    if retiring is None:
        monkeypatch.delenv("ENCRYPTION_KEYS_RETIRING", raising=False)
    else:
        monkeypatch.setenv("ENCRYPTION_KEYS_RETIRING", retiring)
    import backend.encryption as enc
    return importlib.reload(enc)


def test_decrypts_value_from_retiring_key(monkeypatch):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    enc_old = _reload_encryption(monkeypatch, primary=old)
    token = enc_old.encrypt("secret-value")
    enc_new = _reload_encryption(monkeypatch, primary=new, retiring=old)
    assert enc_new.decrypt(token) == "secret-value"


def test_malformed_retiring_key_is_skipped_not_raised(monkeypatch):
    primary = Fernet.generate_key().decode()
    enc = _reload_encryption(monkeypatch, primary=primary, retiring="not-a-valid-key")
    assert enc.encrypt("x") and enc.decrypt(enc.encrypt("x")) == "x"


def test_is_encrypted_with_primary(monkeypatch):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    enc_old = _reload_encryption(monkeypatch, primary=old)
    token_old = enc_old.encrypt("v")
    enc_new = _reload_encryption(monkeypatch, primary=new, retiring=old)
    token_new = enc_new.encrypt("v")
    assert enc_new.is_encrypted_with_primary(token_new) is True
    assert enc_new.is_encrypted_with_primary(token_old) is False


def test_key_fingerprint_is_truncated_and_never_raw(monkeypatch):
    key = Fernet.generate_key().decode()
    enc = _reload_encryption(monkeypatch, primary=key)
    fp = enc.key_fingerprint(key)
    assert fp.startswith("sha256:")
    assert key not in fp
    assert len(fp) <= len("sha256:") + 12
