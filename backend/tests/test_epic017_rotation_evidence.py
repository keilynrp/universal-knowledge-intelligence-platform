# backend/tests/test_epic017_rotation_evidence.py
from datetime import datetime, timezone

from backend import models


def test_secret_rotation_event_row_roundtrip(db_session):
    ev = models.SecretRotationEvent(
        secret_name="ENCRYPTION_KEY",
        rotated_at=datetime.now(timezone.utc),
        operator="ops-script",
        rows_reencrypted=7,
        old_key_fingerprint="sha256:abc123def456",
        new_key_fingerprint="sha256:0011223344ff",
        notes="test",
    )
    db_session.add(ev)
    db_session.commit()
    fetched = db_session.query(models.SecretRotationEvent).filter_by(
        secret_name="ENCRYPTION_KEY"
    ).one()
    assert fetched.rows_reencrypted == 7
    assert fetched.new_key_fingerprint.startswith("sha256:")


def test_last_rotation_at_returns_newest(db_session):
    from backend import secret_rotation as sr
    from datetime import datetime, timezone, timedelta
    older = models.SecretRotationEvent(secret_name="ENCRYPTION_KEY", operator="x",
        rotated_at=datetime.now(timezone.utc) - timedelta(days=10))
    newer = models.SecretRotationEvent(secret_name="ENCRYPTION_KEY", operator="x",
        rotated_at=datetime.now(timezone.utc))
    db_session.add_all([older, newer]); db_session.commit()
    assert sr.last_rotation_at(db_session, "ENCRYPTION_KEY") == newer.rotated_at


def test_encrypted_columns_registry_is_complete():
    from backend import secret_rotation as sr
    names = {(m.__name__, col) for m, col in sr.ENCRYPTED_COLUMNS}
    assert names == {
        ("AIIntegration", "api_key"),
        ("StoreConnection", "api_key"),
        ("StoreConnection", "api_secret"),
        ("StoreConnection", "access_token"),
    }
