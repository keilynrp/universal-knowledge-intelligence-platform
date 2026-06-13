import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger, create_mock_engine, delete, text, update
from sqlalchemy.exc import DBAPIError

from backend import models
from backend.backup_assurance import (
    evaluate_backup_freshness,
    failure_reason_from_event,
    latest_completed_backup,
    record_event,
)


def _backend_test_fixtures():
    expected = Path(__file__).with_name("conftest.py").resolve()
    for module in sys.modules.values():
        module_file = getattr(module, "__file__", None)
        if module_file and Path(module_file).resolve() == expected:
            return module
    raise AssertionError("backend/tests/conftest.py is not loaded")


def test_postgres_create_all_registers_append_only_function_and_triggers():
    statements = []
    engine = create_mock_engine(
        "postgresql+psycopg2://",
        lambda sql, *_args, **_kwargs: statements.append(str(sql)),
    )

    models.BackupAssuranceEvent.__table__.create(engine)

    rendered = "\n".join(statements)
    assert "CREATE FUNCTION reject_backup_assurance_event_mutation" in rendered
    assert rendered.count("CREATE TRIGGER trg_backup_assurance_events_no_") == 2
    assert "BEFORE UPDATE ON backup_assurance_events" in rendered
    assert "BEFORE DELETE ON backup_assurance_events" in rendered


def test_postgres_test_cleanup_drops_deletes_and_recreates_triggers(monkeypatch):
    test_fixtures = _backend_test_fixtures()
    statements = []

    class RecordingSession:
        def execute(self, statement):
            rendered = " ".join(str(statement).split())
            statements.append(rendered)
            if rendered == "DELETE FROM backup_assurance_events":
                return None

    monkeypatch.setattr(test_fixtures, "_IS_POSTGRES", True)
    test_fixtures._delete_test_table(
        RecordingSession(),
        "backup_assurance_events",
    )

    assert statements == [
        "DROP TRIGGER IF EXISTS trg_backup_assurance_events_no_update "
        "ON backup_assurance_events",
        "DROP TRIGGER IF EXISTS trg_backup_assurance_events_no_delete "
        "ON backup_assurance_events",
        "DELETE FROM backup_assurance_events",
        "CREATE TRIGGER trg_backup_assurance_events_no_update "
        "BEFORE UPDATE ON backup_assurance_events FOR EACH ROW "
        "EXECUTE FUNCTION reject_backup_assurance_event_mutation()",
        "CREATE TRIGGER trg_backup_assurance_events_no_delete "
        "BEFORE DELETE ON backup_assurance_events FOR EACH ROW "
        "EXECUTE FUNCTION reject_backup_assurance_event_mutation()",
    ]


def test_postgres_test_cleanup_does_not_swallow_delete_failure(monkeypatch):
    test_fixtures = _backend_test_fixtures()

    class FailingSession:
        def execute(self, statement):
            if str(statement) == "DELETE FROM backup_assurance_events":
                raise RuntimeError("cleanup failed")

    monkeypatch.setattr(test_fixtures, "_IS_POSTGRES", True)

    with pytest.raises(RuntimeError, match="cleanup failed"):
        test_fixtures._delete_test_table(
            FailingSession(),
            "backup_assurance_events",
        )


def _record_backup(db_session, **overrides):
    now = datetime(2026, 6, 12, 12, tzinfo=timezone.utc)
    values = {
        "event_type": "backup",
        "status": "completed",
        "environment": "production",
        "provider": "dokploy",
        "backup_id": "backup-20260612-001",
        "started_at": now - timedelta(minutes=5),
        "completed_at": now,
        "release": "sha-abc123",
        "alembic_revision": "e5f6a7b8c0d1",
        "size_bytes": 1024,
        "integrity_ref": "sha256:abc",
        "encrypted": True,
        "storage_region": "mx-central",
        "retention_class": "daily",
        "operator": "ops@example.test",
        "evidence": {"provider_state": "completed"},
    }
    values.update(overrides)
    return record_event(db_session, **values)


def _persist_backup(db_session, **overrides):
    event = _record_backup(db_session, **overrides)
    db_session.commit()
    return event


def test_record_backup_event_persists_non_secret_metadata(db_session):
    event = _record_backup(db_session)

    assert event.id is not None
    persisted = db_session.query(models.BackupAssuranceEvent).one()
    assert persisted.backup_id == "backup-20260612-001"
    assert json.loads(persisted.evidence_json) == {"provider_state": "completed"}
    assert persisted.started_at == datetime(2026, 6, 12, 11, 55)
    assert persisted.completed_at == datetime(2026, 6, 12, 12)


def test_record_backup_event_supports_sizes_above_two_gibibytes(db_session):
    size_bytes = 3 * 1024**3
    event = _record_backup(db_session, size_bytes=size_bytes)

    assert isinstance(
        models.BackupAssuranceEvent.__table__.c.size_bytes.type,
        BigInteger,
    )
    assert event.size_bytes == size_bytes


def test_record_event_does_not_commit_callers_transaction(db_session):
    unrelated = models.SecretRotationEvent(
        secret_name="JWT_SECRET_KEY",
        operator="ops@example.test",
    )
    db_session.add(unrelated)

    event = _record_backup(db_session)
    assert event.id is not None
    assert unrelated.id is not None

    db_session.rollback()

    assert db_session.get(models.BackupAssuranceEvent, event.id) is None
    assert db_session.get(models.SecretRotationEvent, unrelated.id) is None


def test_record_event_persists_all_datetimes_as_utc_naive(db_session):
    source_timezone = timezone(timedelta(hours=-6))
    event = _record_backup(
        db_session,
        started_at=datetime(2026, 6, 12, 5, 30, tzinfo=source_timezone),
        completed_at=datetime(2026, 6, 12, 6, tzinfo=source_timezone),
    )

    assert event.started_at == datetime(2026, 6, 12, 11, 30)
    assert event.completed_at == datetime(2026, 6, 12, 12)
    assert event.started_at.tzinfo is None
    assert event.completed_at.tzinfo is None
    assert event.created_at.tzinfo is None
    assert models.utc_now_naive().tzinfo is None


def test_record_restore_drill_keeps_expected_and_achieved_objectives(db_session):
    now = datetime(2026, 6, 12, 12, tzinfo=timezone.utc)
    event = record_event(
        db_session,
        event_type="restore_drill",
        status="passed",
        environment="drill",
        provider="dokploy",
        backup_id="backup-20260612-001",
        started_at=now - timedelta(hours=2),
        completed_at=now,
        operator="ops@example.test",
        expected_rpo_hours=24,
        expected_rto_hours=4,
        achieved_rpo_hours=18,
        achieved_rto_hours=2,
        evidence={"tenant_isolation": "passed"},
    )

    assert event.achieved_rpo_hours == 18
    assert event.achieved_rto_hours == 2


@pytest.mark.parametrize("event_type", ["snapshot", "", None])
def test_record_event_rejects_invalid_event_type(db_session, event_type):
    with pytest.raises(ValueError, match="event_type"):
        _record_backup(db_session, event_type=event_type)


@pytest.mark.parametrize("status", ["started", "pending", "", None])
def test_record_event_rejects_non_terminal_status(db_session, status):
    with pytest.raises(ValueError, match="status"):
        _record_backup(db_session, status=status)


@pytest.mark.parametrize(
    ("event_type", "status"),
    [
        ("backup", "completed"),
        ("backup", "failed"),
        ("restore_drill", "passed"),
        ("restore_drill", "passed_with_risk"),
        ("restore_drill", "failed"),
    ],
)
def test_record_event_accepts_only_valid_type_status_combinations(
    db_session,
    event_type,
    status,
):
    event = _record_backup(db_session, event_type=event_type, status=status)

    assert event.event_type == event_type
    assert event.status == status


@pytest.mark.parametrize(
    ("event_type", "status"),
    [
        ("backup", "passed"),
        ("backup", "passed_with_risk"),
        ("restore_drill", "completed"),
    ],
)
def test_record_event_rejects_cross_type_terminal_statuses(
    db_session,
    event_type,
    status,
):
    with pytest.raises(ValueError, match="status.*event_type"):
        _record_backup(db_session, event_type=event_type, status=status)


@pytest.mark.parametrize(
    "evidence",
    [
        {"database_url": "postgresql://example"},
        {"nested": {"AccessToken": "abc"}},
        {"items": [{"connection_STRING": "secret"}]},
    ],
)
def test_record_event_rejects_secret_like_evidence_recursively(db_session, evidence):
    with pytest.raises(ValueError, match="secret-like"):
        _record_backup(db_session, evidence=evidence)


def test_record_event_serializes_evidence_with_sorted_keys(db_session):
    event = _record_backup(
        db_session,
        evidence={"zeta": 1, "nested": {"beta": 2, "alpha": 1}, "alpha": 0},
    )

    assert event.evidence_json == (
        '{"alpha": 0, "nested": {"alpha": 1, "beta": 2}, "zeta": 1}'
    )


def test_persisted_backup_event_rejects_orm_update(db_session):
    event = _persist_backup(db_session)
    event_id = event.id
    event.provider = "changed-provider"

    with pytest.raises(RuntimeError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    persisted = db_session.get(models.BackupAssuranceEvent, event_id)
    assert persisted.provider == "dokploy"


def test_persisted_backup_event_rejects_orm_delete(db_session):
    event = _persist_backup(db_session)
    event_id = event.id
    db_session.delete(event)

    with pytest.raises(RuntimeError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    assert db_session.get(models.BackupAssuranceEvent, event_id) is not None


def test_persisted_backup_event_rejects_query_bulk_update(db_session):
    event = _persist_backup(db_session)
    event_id = event.id

    with pytest.raises(RuntimeError, match="append-only"):
        (
            db_session.query(models.BackupAssuranceEvent)
            .filter(models.BackupAssuranceEvent.id == event_id)
            .update({"provider": "changed-provider"})
        )
    db_session.rollback()

    persisted = db_session.get(models.BackupAssuranceEvent, event_id)
    assert persisted.provider == "dokploy"


def test_persisted_backup_event_rejects_query_bulk_delete(db_session):
    event = _persist_backup(db_session)
    event_id = event.id

    with pytest.raises(RuntimeError, match="append-only"):
        (
            db_session.query(models.BackupAssuranceEvent)
            .filter(models.BackupAssuranceEvent.id == event_id)
            .delete()
        )
    db_session.rollback()

    assert db_session.get(models.BackupAssuranceEvent, event_id) is not None


def test_persisted_backup_event_rejects_core_update(db_session):
    event = _record_backup(db_session)

    with pytest.raises(RuntimeError, match="append-only"):
        db_session.execute(
            update(models.BackupAssuranceEvent.__table__)
            .where(models.BackupAssuranceEvent.id == event.id)
            .values(provider="changed-provider")
        )
    db_session.rollback()


def test_persisted_backup_event_rejects_core_delete(db_session):
    event = _record_backup(db_session)

    with pytest.raises(RuntimeError, match="append-only"):
        db_session.execute(
            delete(models.BackupAssuranceEvent.__table__).where(
                models.BackupAssuranceEvent.id == event.id
            )
        )
    db_session.rollback()


def test_persisted_backup_event_rejects_text_update(db_session):
    event = _record_backup(db_session)

    with pytest.raises(DBAPIError, match="append-only"):
        db_session.execute(
            text(
                "UPDATE backup_assurance_events "
                "SET provider = 'changed-provider' WHERE id = :event_id"
            ),
            {"event_id": event.id},
        )
    db_session.rollback()


def test_persisted_backup_event_rejects_text_delete(db_session):
    event = _record_backup(db_session)

    with pytest.raises(DBAPIError, match="append-only"):
        db_session.execute(
            text("DELETE FROM backup_assurance_events WHERE id = :event_id"),
            {"event_id": event.id},
        )
    db_session.rollback()


@pytest.mark.parametrize(
    "statement",
    [
        update(models.BackupAssuranceEvent.__table__).values(provider="changed"),
        delete(models.BackupAssuranceEvent.__table__),
        text("UPDATE backup_assurance_events SET provider = 'changed'"),
        text("DELETE FROM backup_assurance_events"),
    ],
)
def test_application_engine_rejects_core_and_text_mutation(db_session, statement):
    _persist_backup(db_session)

    with db_session.get_bind().connect() as connection:
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(statement)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE /* append-only bypass */ backup_assurance_events "
        "SET provider = 'changed'",
        "DELETE /* append-only bypass */ FROM backup_assurance_events",
    ],
)
def test_commented_text_sql_cannot_bypass_append_only_triggers(
    db_session,
    statement,
):
    _persist_backup(db_session)

    with pytest.raises(DBAPIError, match="append-only"):
        db_session.execute(text(statement))
    db_session.rollback()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE backup_assurance_events SET provider = 'changed'",
        "DELETE FROM backup_assurance_events",
    ],
)
def test_exec_driver_sql_cannot_bypass_append_only_triggers(
    db_session,
    statement,
):
    _persist_backup(db_session)

    with db_session.get_bind().connect() as connection:
        with pytest.raises(DBAPIError, match="append-only"):
            connection.exec_driver_sql(statement)


def test_freshness_is_ok_at_24_hours():
    now = datetime(2026, 6, 12, 12, tzinfo=timezone.utc)
    result = evaluate_backup_freshness(
        latest_completed_at=now - timedelta(hours=24),
        now=now,
        size_bytes=100,
        integrity_ref="etag:abc",
        provider_reachable=True,
    )

    assert result["status"] == "ok"
    assert result["age_hours"] == 24
    assert result["reason_codes"] == []


def test_freshness_warns_between_24_and_26_hours():
    now = datetime(2026, 6, 12, 12, tzinfo=timezone.utc)
    result = evaluate_backup_freshness(
        latest_completed_at=now - timedelta(hours=25),
        now=now,
        size_bytes=100,
        integrity_ref="etag:abc",
        provider_reachable=True,
    )

    assert result["status"] == "warning"
    assert result["reason_codes"] == ["backup_approaching_critical_threshold"]


@pytest.mark.parametrize(
    ("latest_completed_at", "size_bytes", "integrity_ref", "provider_reachable", "reason"),
    [
        (None, 100, "etag:abc", True, "backup_missing"),
        (
            datetime(2026, 6, 11, 9, tzinfo=timezone.utc),
            100,
            "etag:abc",
            True,
            "backup_stale",
        ),
        (
            datetime(2026, 6, 12, 12, tzinfo=timezone.utc),
            0,
            "etag:abc",
            True,
            "backup_empty",
        ),
        (
            datetime(2026, 6, 12, 12, tzinfo=timezone.utc),
            100,
            None,
            True,
            "integrity_missing",
        ),
        (
            datetime(2026, 6, 12, 12, tzinfo=timezone.utc),
            100,
            "etag:abc",
            False,
            "provider_unreachable",
        ),
    ],
)
def test_freshness_is_critical_when_stale_or_invalid(
    latest_completed_at,
    size_bytes,
    integrity_ref,
    provider_reachable,
    reason,
):
    now = datetime(2026, 6, 12, 12, tzinfo=timezone.utc)
    result = evaluate_backup_freshness(
        latest_completed_at=latest_completed_at,
        now=now,
        size_bytes=size_bytes,
        integrity_ref=integrity_ref,
        provider_reachable=provider_reachable,
    )

    assert result["status"] == "critical"
    assert reason in result["reason_codes"]
    assert result["rpo_hours"] == 24
    assert result["critical_after_hours"] == 26


def test_latest_completed_backup_filters_environment_type_and_status(db_session):
    old = _record_backup(
        db_session,
        backup_id="old",
        completed_at=datetime(2026, 6, 12, 10, tzinfo=timezone.utc),
    )
    latest = _record_backup(
        db_session,
        backup_id="latest",
        completed_at=datetime(2026, 6, 12, 11, tzinfo=timezone.utc),
    )
    _record_backup(
        db_session,
        backup_id="failed",
        status="failed",
        completed_at=datetime(2026, 6, 12, 12, tzinfo=timezone.utc),
    )
    _record_backup(
        db_session,
        backup_id="staging",
        environment="staging",
        completed_at=datetime(2026, 6, 12, 12, tzinfo=timezone.utc),
    )
    record_event(
        db_session,
        event_type="restore_drill",
        status="passed",
        environment="production",
        provider="dokploy",
        backup_id="drill",
        started_at=datetime(2026, 6, 12, 11, tzinfo=timezone.utc),
        completed_at=datetime(2026, 6, 12, 12, tzinfo=timezone.utc),
        operator="ops@example.test",
    )

    result = latest_completed_backup(db_session, "production")

    assert old.id < latest.id
    assert result.id == latest.id


def test_latest_completed_backup_uses_id_as_tie_breaker(db_session):
    completed_at = datetime(2026, 6, 12, 12, tzinfo=timezone.utc)
    first = _record_backup(db_session, backup_id="first", completed_at=completed_at)
    second = _record_backup(db_session, backup_id="second", completed_at=completed_at)

    result = latest_completed_backup(db_session, "production")

    assert first.id < second.id
    assert result.id == second.id


def test_latest_completed_backup_ignores_events_without_completion_time(db_session):
    _record_backup(db_session, backup_id="incomplete-metadata", completed_at=None)

    result = latest_completed_backup(db_session, "production")

    assert result is None


def test_failure_reason_from_event_tolerates_invalid_evidence_json():
    event = SimpleNamespace(evidence_json="{not-json")

    assert failure_reason_from_event(event) is None
