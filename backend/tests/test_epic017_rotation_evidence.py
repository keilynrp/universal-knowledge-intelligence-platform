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
