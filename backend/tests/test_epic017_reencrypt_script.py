# backend/tests/test_epic017_reencrypt_script.py
import importlib

from cryptography.fernet import Fernet

from backend import models


def test_reencrypts_only_non_primary_rows_and_records_evidence(db_session, monkeypatch):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()

    # Seed a row encrypted under the OLD key.
    monkeypatch.setenv("ENCRYPTION_KEY", old)
    monkeypatch.delenv("ENCRYPTION_KEYS_RETIRING", raising=False)
    import backend.encryption as enc
    importlib.reload(enc)
    integ = models.AIIntegration(provider_name="openai", model_name="gpt-4o",
                                 api_key=enc.encrypt("sk-secret"), is_active=True)
    db_session.add(integ); db_session.commit()

    # Rotate env: new primary, old retiring.
    monkeypatch.setenv("ENCRYPTION_KEY", new)
    monkeypatch.setenv("ENCRYPTION_KEYS_RETIRING", old)
    importlib.reload(enc)
    import backend.secret_rotation as sr; importlib.reload(sr)
    import backend.scripts.rotate_encryption as script; importlib.reload(script)

    result = script.run_reencryption(db_session, operator="test", dry_run=False)
    assert result["rows_reencrypted"] == 1

    # Value still decrypts and is now on the primary key.
    importlib.reload(enc)
    db_session.refresh(integ)
    assert enc.is_encrypted_with_primary(integ.api_key) is True
    assert enc.decrypt(integ.api_key) == "sk-secret"

    # Evidence row written.
    ev = db_session.query(models.SecretRotationEvent).filter_by(secret_name="ENCRYPTION_KEY").one()
    assert ev.rows_reencrypted == 1

    # Idempotent: second run re-encrypts 0 rows.
    importlib.reload(script)
    again = script.run_reencryption(db_session, operator="test", dry_run=False)
    assert again["rows_reencrypted"] == 0


def test_dry_run_writes_nothing(db_session, monkeypatch):
    old = Fernet.generate_key().decode(); new = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", old)
    import backend.encryption as enc; importlib.reload(enc)
    db_session.add(models.AIIntegration(provider_name="openai", model_name="gpt-4o",
                                        api_key=enc.encrypt("v"), is_active=True))
    db_session.commit()
    monkeypatch.setenv("ENCRYPTION_KEY", new); monkeypatch.setenv("ENCRYPTION_KEYS_RETIRING", old)
    importlib.reload(enc)
    import backend.scripts.rotate_encryption as script; importlib.reload(script)
    result = script.run_reencryption(db_session, operator="test", dry_run=True)
    assert result["rows_reencrypted"] == 1  # would re-encrypt 1
    assert db_session.query(models.SecretRotationEvent).count() == 0  # but wrote no evidence
