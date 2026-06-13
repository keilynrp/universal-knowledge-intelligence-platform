from datetime import datetime, timedelta, timezone

from backend import ops_checks
from backend.backup_assurance import record_event


def _create_ops_alert_channel(db_session):
    from backend import models

    channel = models.AlertChannel(
        name="Ops Alerts",
        type="webhook",
        webhook_url="https://example.test/hooks/ops",
        events='["ops.check_failed"]',
        is_active=True,
        total_fired=0,
    )
    db_session.add(channel)
    db_session.commit()
    return channel


def test_ops_checks_returns_repeatable_summary(client, auth_headers):
    response = client.get("/ops/checks", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["service"] == "ukip-backend"
    assert body["status"] == "degraded"
    assert "checked_at" in body
    assert "summary" in body
    check_ids = {check["id"] for check in body["checks"]}
    assert check_ids == {
        "database", "migrations", "scheduled_imports", "scheduled_reports", "ops_alerting",
        "secrets", "backup_freshness",
    }

    database_check = next(check for check in body["checks"] if check["id"] == "database")
    assert database_check["status"] == "ok"

    # Migration drift check is skipped under tests (startup side effects disabled).
    migrations_check = next(check for check in body["checks"] if check["id"] == "migrations")
    assert migrations_check["status"] == "skipped"

    import_check = next(check for check in body["checks"] if check["id"] == "scheduled_imports")
    report_check = next(check for check in body["checks"] if check["id"] == "scheduled_reports")
    assert import_check["status"] == "skipped"
    assert report_check["status"] == "skipped"
    backup_check = next(check for check in body["checks"] if check["id"] == "backup_freshness")
    assert backup_check["status"] == "skipped"

    alerting_check = next(check for check in body["checks"] if check["id"] == "ops_alerting")
    assert alerting_check["status"] == "warning"
    # The EPIC-017 `secrets` check returns `ok` under the test env (JWT_SECRET_KEY
    # != insecure default, ENCRYPTION_KEY set, no rotation events, no retiring keys),
    # so it adds no warning/skipped — the counts below stay valid.
    assert body["summary"]["warning"] == 1
    assert body["summary"]["skipped"] == 4


def test_ops_checks_turn_ok_when_ops_alert_channel_exists(client, auth_headers, db_session):
    _create_ops_alert_channel(db_session)

    response = client.get("/ops/checks", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    alerting_check = next(check for check in body["checks"] if check["id"] == "ops_alerting")
    assert alerting_check["status"] == "ok"
    assert alerting_check["details"]["ops_alert_channels"] == 1


def test_ops_checks_notify_dispatches_failure_event_when_requested(client, auth_headers, monkeypatch):
    captured = {}

    def _fake_dispatch_event(db_session, event, message, details):
        captured["event"] = event
        captured["message"] = message
        captured["details"] = details

    monkeypatch.setattr(ops_checks, "dispatch_event", _fake_dispatch_event)

    response = client.post("/ops/checks/run?notify=true", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "degraded"
    assert body["notification"]["attempted"] is True
    assert captured["event"] == "ops.check_failed"
    assert "degraded" in captured["message"]
    assert "checked_at" in captured["details"]


def test_ops_checks_requires_admin(client, viewer_headers):
    response = client.get("/ops/checks", headers=viewer_headers)
    assert response.status_code == 403


def test_alert_catalogue_exposes_ops_check_failed_event(client, auth_headers):
    response = client.get("/alert-channels/events", headers=auth_headers)
    assert response.status_code == 200
    event_ids = {event["id"] for event in response.json()}
    assert "ops.check_failed" in event_ids


def _persist_backup(db_session, *, completed_at: datetime):
    event = record_event(
        db_session,
        event_type="backup",
        status="completed",
        environment="production",
        provider="dokploy",
        backup_id="backup-ops-check",
        started_at=completed_at - timedelta(minutes=5),
        completed_at=completed_at,
        size_bytes=2048,
        integrity_ref="etag:abc",
        encrypted=True,
        operator="ops@example.test",
        evidence={"provider_state": "completed"},
    )
    db_session.commit()
    return event


def test_backup_freshness_is_critical_without_production_backup(
    db_session,
    monkeypatch,
):
    monkeypatch.setenv("UKIP_BACKUP_MONITOR_ENABLED", "1")
    monkeypatch.setenv("UKIP_BACKUP_ENVIRONMENT", "production")
    monkeypatch.setenv("UKIP_BACKUP_PROVIDER_REACHABLE", "1")

    report = ops_checks.run_operational_checks(db_session)

    check = next(item for item in report["checks"] if item["id"] == "backup_freshness")
    assert check["status"] == "critical"
    assert "backup_missing" in check["details"]["reason_codes"]
    assert any(
        "BACKUP_RESTORE_RUNBOOK.md" in action
        for action in report["recommended_actions"]
    )


def test_backup_freshness_defaults_provider_reachability_to_unknown(
    db_session,
    monkeypatch,
):
    monkeypatch.setenv("UKIP_BACKUP_MONITOR_ENABLED", "1")
    monkeypatch.delenv("UKIP_BACKUP_PROVIDER_REACHABLE", raising=False)
    _persist_backup(
        db_session,
        completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    report = ops_checks.run_operational_checks(db_session)

    check = next(item for item in report["checks"] if item["id"] == "backup_freshness")
    assert check["status"] == "critical"
    assert check["details"]["provider_reachable"] is False
    assert check["details"]["provider_reachability_source"] == "unknown_default"


def test_backup_freshness_labels_explicit_provider_reachability(
    db_session,
    monkeypatch,
):
    monkeypatch.setenv("UKIP_BACKUP_MONITOR_ENABLED", "1")
    monkeypatch.setenv("UKIP_BACKUP_PROVIDER_REACHABLE", "1")
    _persist_backup(
        db_session,
        completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    report = ops_checks.run_operational_checks(db_session)

    check = next(item for item in report["checks"] if item["id"] == "backup_freshness")
    assert check["status"] == "ok"
    assert check["details"]["provider_reachability_source"] == "environment_assertion"


def test_backup_freshness_query_failure_returns_critical_check(
    db_session,
    monkeypatch,
):
    monkeypatch.setenv("UKIP_BACKUP_MONITOR_ENABLED", "1")

    def _query_failure(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(ops_checks, "latest_completed_backup", _query_failure)

    report = ops_checks.run_operational_checks(db_session)

    check = next(item for item in report["checks"] if item["id"] == "backup_freshness")
    assert check["status"] == "critical"
    assert check["details"]["reason_codes"] == ["backup_query_failed"]
    assert "database unavailable" in check["details"]["error"]


def test_backup_freshness_disabled_does_not_query_latest_backup(
    db_session,
    monkeypatch,
):
    monkeypatch.setenv("UKIP_BACKUP_MONITOR_ENABLED", "0")

    def _unexpected_query(*_args, **_kwargs):
        raise AssertionError("latest_completed_backup must not be called")

    monkeypatch.setattr(ops_checks, "latest_completed_backup", _unexpected_query)

    report = ops_checks.run_operational_checks(db_session)

    check = next(item for item in report["checks"] if item["id"] == "backup_freshness")
    assert check["status"] == "skipped"


def test_backup_freshness_warns_at_25_hours(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_BACKUP_MONITOR_ENABLED", "1")
    monkeypatch.setenv("UKIP_BACKUP_ENVIRONMENT", "production")
    monkeypatch.setenv("UKIP_BACKUP_PROVIDER_REACHABLE", "1")
    _persist_backup(
        db_session,
        completed_at=datetime.now(timezone.utc) - timedelta(hours=25),
    )

    report = ops_checks.run_operational_checks(db_session)

    check = next(item for item in report["checks"] if item["id"] == "backup_freshness")
    assert check["status"] == "warning"
    assert any(
        "26-hour critical threshold" in action
        for action in report["recommended_actions"]
    )


def test_backup_freshness_is_ok_for_fresh_valid_backup(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_BACKUP_MONITOR_ENABLED", "1")
    monkeypatch.setenv("UKIP_BACKUP_ENVIRONMENT", "production")
    monkeypatch.setenv("UKIP_BACKUP_PROVIDER_REACHABLE", "1")
    _persist_backup(
        db_session,
        completed_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    report = ops_checks.run_operational_checks(db_session)

    check = next(item for item in report["checks"] if item["id"] == "backup_freshness")
    assert check["status"] == "ok"
    assert check["details"]["latest_backup_id"] == "backup-ops-check"
