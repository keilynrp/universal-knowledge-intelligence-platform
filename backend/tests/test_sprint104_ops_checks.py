from backend import ops_checks


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
        "secrets",
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

    alerting_check = next(check for check in body["checks"] if check["id"] == "ops_alerting")
    assert alerting_check["status"] == "warning"
    # The EPIC-017 `secrets` check returns `ok` under the test env (JWT_SECRET_KEY
    # != insecure default, ENCRYPTION_KEY set, no rotation events, no retiring keys),
    # so it adds no warning/skipped — the counts below stay valid.
    assert body["summary"]["warning"] == 1
    assert body["summary"]["skipped"] == 3


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
