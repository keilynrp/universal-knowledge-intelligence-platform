from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from backend import models
from backend.routers import backup_ops
from backend.routers.backup_ops import backup_event_ordering


def _payload(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "event_type": "backup",
        "status": "completed",
        "environment": "production",
        "provider": "dokploy",
        "backup_id": "backup-001",
        "started_at": (now - timedelta(minutes=5)).isoformat(),
        "completed_at": now.isoformat(),
        "release": "sha-abc",
        "alembic_revision": "head-1",
        "size_bytes": 2048,
        "integrity_ref": "etag:abc",
        "encrypted": True,
        "storage_region": "mx-central",
        "retention_class": "daily",
        "operator": "ops@example.test",
        "evidence": {"provider_state": "completed"},
    }
    payload.update(overrides)
    return payload


def test_backup_events_require_admin(client, viewer_headers):
    response = client.post(
        "/ops/backups/events",
        headers=viewer_headers,
        json=_payload(),
    )

    assert response.status_code == 403


def test_admin_can_record_backup_metadata(client, auth_headers, db_session):
    response = client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=_payload(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["backup_id"] == "backup-001"
    assert body["evidence"] == {"provider_state": "completed"}

    from backend import models

    persisted = db_session.query(models.BackupAssuranceEvent).one()
    assert persisted.backup_id == "backup-001"


def test_secret_like_evidence_keys_are_rejected(client, auth_headers):
    response = client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=_payload(evidence={"nested": {"access_token": "do-not-store"}}),
    )

    assert response.status_code == 422


def test_invalid_event_status_combination_is_rejected(client, auth_headers):
    response = client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=_payload(status="passed"),
    )

    assert response.status_code == 422


def test_backup_events_are_returned_newest_first(client, auth_headers):
    older = _payload(
        backup_id="backup-older",
        completed_at="2026-06-12T10:05:00Z",
    )
    newer = _payload(
        backup_id="backup-newer",
        completed_at="2026-06-12T11:05:00Z",
    )
    assert client.post("/ops/backups/events", headers=auth_headers, json=older).status_code == 201
    assert client.post("/ops/backups/events", headers=auth_headers, json=newer).status_code == 201

    response = client.get(
        "/ops/backups?environment=production",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert [item["backup_id"] for item in response.json()] == [
        "backup-newer",
        "backup-older",
    ]


def test_backup_events_put_incomplete_events_after_completed_events(
    client,
    auth_headers,
):
    incomplete = _payload(
        backup_id="backup-incomplete",
        completed_at=None,
    )
    completed = _payload(
        backup_id="backup-completed",
        completed_at="2026-06-12T11:05:00Z",
    )
    assert client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=incomplete,
    ).status_code == 201
    assert client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=completed,
    ).status_code == 201

    response = client.get(
        "/ops/backups?environment=production",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert [item["backup_id"] for item in response.json()] == [
        "backup-completed",
        "backup-incomplete",
    ]


def test_backup_event_ordering_compiles_to_postgres_nulls_last():
    statement = select(models.BackupAssuranceEvent).order_by(
        *backup_event_ordering()
    )

    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "completed_at DESC NULLS LAST" in sql
    assert "created_at DESC" in sql
    assert "id DESC" in sql


def test_backup_status_uses_current_utc_as_evidence_collection_time(
    client,
    auth_headers,
    monkeypatch,
):
    evaluated_at = datetime(2026, 6, 13, 2, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(backup_ops, "utc_now", lambda: evaluated_at)
    assert client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=_payload(environment="production"),
    ).status_code == 201

    response = client.get(
        "/ops/backups/status?environment=production",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["environment"] == "production"
    assert body["status"] == "ok"
    assert body["rpo_hours"] == 24
    assert body["critical_after_hours"] == 26
    assert body["latest_backup"]["backup_id"] == "backup-001"
    assert body["evidence_collected_at"] == "2026-06-13T02:30:00Z"
    assert body["last_failure_at"] is None
    assert body["last_failure_reason"] is None


def test_backup_status_collects_evidence_time_even_without_backups(
    client,
    auth_headers,
    monkeypatch,
):
    evaluated_at = datetime(2026, 6, 13, 3, 45, tzinfo=timezone.utc)
    monkeypatch.setattr(backup_ops, "utc_now", lambda: evaluated_at)

    response = client.get(
        "/ops/backups/status?environment=empty-environment",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "critical"
    assert body["latest_backup"] is None
    assert body["evidence_collected_at"] == "2026-06-13T03:45:00Z"


def test_backup_status_includes_latest_failure_metadata(client, auth_headers):
    failed = _payload(
        status="failed",
        backup_id="backup-failed",
        completed_at="2026-06-12T11:05:00Z",
        evidence={
            "provider_state": "failed",
            "failure_reason": "upload timeout",
        },
    )
    completed = _payload(
        backup_id="backup-completed",
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    assert client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=failed,
    ).status_code == 201
    assert client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=completed,
    ).status_code == 201

    response = client.get(
        "/ops/backups/status?environment=production",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evidence_collected_at"] is not None
    assert body["last_failure_at"] == "2026-06-12T11:05:00"
    assert body["last_failure_reason"] == "upload timeout"


def test_backup_status_uses_failure_completion_time_not_delayed_ingestion(
    client,
    auth_headers,
):
    chronologically_newer = _payload(
        status="failed",
        backup_id="failed-newer",
        completed_at="2026-06-12T12:05:00Z",
        evidence={"failure_reason": "newer failure"},
    )
    delayed_older = _payload(
        status="failed",
        backup_id="failed-older-delayed",
        completed_at="2026-06-12T10:05:00Z",
        evidence={"failure_reason": "older delayed failure"},
    )
    assert client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=chronologically_newer,
    ).status_code == 201
    assert client.post(
        "/ops/backups/events",
        headers=auth_headers,
        json=delayed_older,
    ).status_code == 201

    response = client.get(
        "/ops/backups/status?environment=production",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["last_failure_at"] == "2026-06-12T12:05:00"
    assert body["last_failure_reason"] == "newer failure"
