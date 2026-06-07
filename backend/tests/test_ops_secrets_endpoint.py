from datetime import datetime, timezone, timedelta

from backend import models, secret_rotation as sr


def _seed_event(db, secret_name="ENCRYPTION_KEY", operator="alice", rows=3, when=None):
    ev = models.SecretRotationEvent(
        secret_name=secret_name,
        operator=operator,
        rows_reencrypted=rows,
        old_key_fingerprint="sha256:aaaaaaaaaaaa",
        new_key_fingerprint="sha256:bbbbbbbbbbbb",
        notes="test",
        rotated_at=when or datetime.now(timezone.utc),
    )
    db.add(ev)
    db.commit()
    return ev


def test_list_rotation_events_newest_first_and_limit(db_session):
    _seed_event(db_session, operator="old", when=datetime.now(timezone.utc) - timedelta(days=5))
    _seed_event(db_session, operator="new", when=datetime.now(timezone.utc))

    events = sr.list_rotation_events(db_session, limit=20)
    assert [e.operator for e in events] == ["new", "old"]

    limited = sr.list_rotation_events(db_session, limit=1)
    assert len(limited) == 1
    assert limited[0].operator == "new"
