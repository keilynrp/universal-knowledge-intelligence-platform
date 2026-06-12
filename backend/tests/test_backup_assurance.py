import json
from datetime import datetime, timedelta, timezone

import pytest

from backend import models
from backend.backup_assurance import (
    evaluate_backup_freshness,
    latest_completed_backup,
    record_event,
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


def test_record_backup_event_persists_non_secret_metadata(db_session):
    event = _record_backup(db_session)

    assert event.id is not None
    persisted = db_session.query(models.BackupAssuranceEvent).one()
    assert persisted.backup_id == "backup-20260612-001"
    assert json.loads(persisted.evidence_json) == {"provider_state": "completed"}
    assert persisted.started_at == datetime(2026, 6, 12, 11, 55)
    assert persisted.completed_at == datetime(2026, 6, 12, 12)


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
