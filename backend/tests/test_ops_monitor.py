"""Scheduled detection (#368): alert policy, one evaluation, config, start, self-check."""
from datetime import datetime, timedelta, timezone

import pytest

from backend import ops_checks, ops_monitor
from backend.ops_monitor import Observation, alert_kind

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 21, 3, 0, tzinfo=timezone.utc)
REMIND = timedelta(hours=6)
BACKUP = frozenset({"backup_freshness"})
BOTH = frozenset({"backup_freshness", "secrets"})


@pytest.fixture(autouse=True)
def _fresh_monitor(monkeypatch):
    monkeypatch.setattr(ops_monitor, "_last", None)
    monkeypatch.setattr(ops_monitor, "_thread", None)
    for key in list(ops_monitor._state):
        monkeypatch.setitem(ops_monitor._state, key, None)
    for name in (
        "UKIP_OPS_MONITOR_ENABLED",
        "UKIP_OPS_MONITOR_INTERVAL_SECONDS",
        "UKIP_OPS_MONITOR_REMIND_HOURS",
    ):
        monkeypatch.delenv(name, raising=False)


def _seen(status, failing=BACKUP, hours_ago=1.0):
    return Observation(status, failing, NOW - timedelta(hours=hours_ago))


# ── alert policy ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("previous", "status", "failing", "expected"),
    [
        (None, "ok", frozenset(), None),
        # First look after a (re)start while unhealthy: say so once.
        (None, "degraded", BACKUP, "degraded"),
        (_seen("ok", frozenset()), "critical", BACKUP, "degraded"),
        (_seen("degraded"), "critical", BACKUP, "escalated"),
        (_seen("degraded"), "degraded", BOTH, "changed"),
        (_seen("critical", BOTH), "critical", BACKUP, "changed"),
        (_seen("degraded", hours_ago=1), "degraded", BACKUP, None),
        (_seen("degraded", hours_ago=6), "degraded", BACKUP, "reminder"),
        (_seen("critical"), "ok", frozenset(), "recovered"),
        (_seen("ok", frozenset()), "ok", frozenset(), None),
    ],
)
def test_alert_policy(previous, status, failing, expected):
    assert alert_kind(previous, status, failing, NOW, REMIND) == expected


def test_de_escalation_with_the_same_failing_checks_does_not_alert():
    # critical -> degraded is an improvement; it is announced by "recovered"
    # once everything is ok, not on every step down.
    assert alert_kind(_seen("critical"), "degraded", BACKUP, NOW, REMIND) is None


def test_a_never_alerted_unhealthy_state_is_reminded():
    previous = Observation("degraded", BACKUP, None)
    assert alert_kind(previous, "degraded", BACKUP, NOW, REMIND) == "reminder"


# ── one evaluation ───────────────────────────────────────────────────────────


def _report(status, failing=()):
    checks = [{"id": name, "status": "warning"} for name in failing]
    checks.append({"id": "database", "status": "ok"})
    return {
        "status": status,
        "checked_at": NOW.isoformat(),
        "checks": checks,
        "summary": {"warning": len(failing), "critical": 0},
    }


def test_run_once_alerts_on_change_stays_quiet_then_announces_recovery():
    sent = []

    def dispatch(_db, event, message, details):
        sent.append((event, message, details))

    reports = iter(
        [
            _report("degraded", ["backup_freshness"]),
            _report("degraded", ["backup_freshness"]),
            _report("ok"),
        ]
    )

    kinds = [
        ops_monitor.run_once(
            None,
            now=NOW + timedelta(minutes=5 * i),
            remind_after=REMIND,
            run_checks=lambda _db: next(reports),
            dispatch=dispatch,
        )
        for i in range(3)
    ]

    assert kinds == ["degraded", None, "recovered"]
    assert [event for event, _, _ in sent] == [ops_checks.OPS_ALERT_EVENT] * 2
    assert sent[0][2]["kind"] == "degraded"
    assert sent[0][2]["failing_checks"] == "backup_freshness"
    assert "backup_freshness" in sent[0][1]
    assert sent[1][2]["kind"] == "recovered"
    status = ops_monitor.get_status(now=NOW)
    assert status["last_alert_kind"] == "recovered"
    assert status["last_status"] == "ok"


def test_run_once_logs_alerts_even_without_a_channel(caplog):
    with caplog.at_level("WARNING", logger="backend.ops_monitor"):
        ops_monitor.run_once(
            None,
            now=NOW,
            remind_after=REMIND,
            run_checks=lambda _db: _report("degraded", ["secrets"]),
            dispatch=lambda *args: None,
        )
    assert "degraded" in caplog.text and "secrets" in caplog.text


# ── configuration and start ──────────────────────────────────────────────────


def test_config_defaults():
    config = ops_monitor.load_config()
    assert config.enabled is True
    assert config.interval_seconds == 300
    assert config.remind_after == timedelta(hours=6)


@pytest.mark.parametrize(
    ("interval", "remind", "expected_interval", "expected_remind"),
    [
        ("10", "0", 60, 6.0),  # clamped / non-positive falls back
        ("oops", "x", 300, 6.0),  # invalid falls back to the defaults
        ("900", "1.5", 900, 1.5),
    ],
)
def test_config_is_validated(monkeypatch, interval, remind, expected_interval, expected_remind):
    monkeypatch.setenv("UKIP_OPS_MONITOR_INTERVAL_SECONDS", interval)
    monkeypatch.setenv("UKIP_OPS_MONITOR_REMIND_HOURS", remind)
    config = ops_monitor.load_config()
    assert config.interval_seconds == expected_interval
    assert config.remind_after == timedelta(hours=expected_remind)


def test_disabled_monitor_does_not_start(monkeypatch):
    monkeypatch.setenv("UKIP_OPS_MONITOR_ENABLED", "0")
    assert ops_monitor.start_monitor() is False
    assert ops_monitor._thread is None


def test_start_monitor_starts_one_thread(monkeypatch):
    monkeypatch.setattr(ops_monitor, "_loop", lambda config: None)
    assert ops_monitor.start_monitor() is True
    ops_monitor._thread.join(timeout=5)
    assert ops_monitor._thread.name == "ops-monitor"
    assert ops_monitor.get_status()["started_at"] is not None


# ── the detector reports on itself ───────────────────────────────────────────


def _status(**overrides):
    base = {
        "enabled": True,
        "alive": True,
        "interval_seconds": 300,
        "stale_after_seconds": 900,
        "last_heartbeat_age_seconds": 10.0,
        "last_loop_error": None,
    }
    return {**base, **overrides}


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "ok"),
        ({"enabled": False}, "warning"),
        ({"alive": False}, "critical"),
        ({"last_heartbeat_age_seconds": 901.0}, "critical"),
        ({"last_loop_error": "ops_monitor_loop_error"}, "warning"),
        ({"last_heartbeat_age_seconds": None}, "ok"),  # started, first tick pending
    ],
)
def test_scheduled_detection_check(monkeypatch, overrides, expected):
    monkeypatch.setattr(ops_checks, "_startup_side_effects_enabled", lambda: True)
    monkeypatch.setattr(ops_monitor, "get_status", lambda now=None: _status(**overrides))
    check = ops_checks._scheduled_detection_check(NOW)
    assert check["id"] == "scheduled_detection"
    assert check["status"] == expected


def test_scheduled_detection_check_is_skipped_without_startup_side_effects(monkeypatch):
    monkeypatch.setattr(ops_checks, "_startup_side_effects_enabled", lambda: False)
    assert ops_checks._scheduled_detection_check(NOW)["status"] == "skipped"


def test_unhealthy_detection_recommends_restoring_it():
    actions = ops_checks._recommended_actions(
        [{"id": "scheduled_detection", "status": "critical"}]
    )
    assert any("scheduled detection" in action.lower() for action in actions)


def test_run_once_reads_the_real_report(db_session):
    """Against the real checks, not a fake report: the shape the monitor relies on exists."""
    sent = []
    kind = ops_monitor.run_once(
        db_session,
        now=NOW,
        remind_after=REMIND,
        dispatch=lambda _db, event, message, details: sent.append(details),
    )
    report = ops_checks.run_operational_checks(db_session)
    assert report["status"] in {"ok", "degraded", "critical"}
    if report["status"] == "ok":
        assert kind is None and sent == []
    else:
        # Under tests no alert channel exists, so ops_alerting is a warning.
        assert kind == "degraded"
        assert "ops_alerting" in sent[0]["failing_checks"]
