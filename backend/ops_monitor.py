"""Scheduled detection: evaluate the operational checks without anyone asking (#368).

Until this existed, ``run_operational_checks`` only ran when someone opened
``GET /ops/checks`` or pressed "run now", and only the latter could alert. A
production degradation at 03:00 was discovered whenever a person next looked.

A daemon thread evaluates the checks every ``UKIP_OPS_MONITOR_INTERVAL_SECONDS``
and sends ``ops.check_failed`` on a state change, not on every tick:

* ``degraded``   — healthy (or just started) → degraded/critical
* ``escalated``  — degraded → critical
* ``changed``    — still unhealthy, but a different set of checks is failing
* ``reminder``   — unchanged and unhealthy for ``UKIP_OPS_MONITOR_REMIND_HOURS``
* ``recovered``  — unhealthy → ok, so an alert is never left open silently

Every alert is also logged at WARNING, so it reaches the container log when no
alert channel is subscribed (which ``ops_alerting`` reports on its own).

State lives in memory. A restart while unhealthy therefore alerts once more;
that is deliberate — a deploy that does not fix the problem should say so.
Production runs one uvicorn process, like the other in-process schedulers.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SECONDS = 300
MIN_INTERVAL_SECONDS = 60
DEFAULT_REMIND_HOURS = 6.0
_UNHEALTHY = {"degraded", "critical"}


@dataclass(frozen=True)
class MonitorConfig:
    enabled: bool
    interval_seconds: int
    remind_after: timedelta


@dataclass(frozen=True)
class Observation:
    status: str
    failing: frozenset[str]
    alerted_at: datetime | None


def _int_env(name: str, default: int, minimum: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        logger.warning("%s=%r is not an integer; using %s", name, raw, default)
        return default
    return max(value, minimum)


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        value = float(raw) if raw else default
    except ValueError:
        logger.warning("%s=%r is not a number; using %s", name, raw, default)
        return default
    return value if value > 0 else default


def load_config() -> MonitorConfig:
    return MonitorConfig(
        enabled=os.environ.get("UKIP_OPS_MONITOR_ENABLED", "1").strip() != "0",
        interval_seconds=_int_env(
            "UKIP_OPS_MONITOR_INTERVAL_SECONDS",
            DEFAULT_INTERVAL_SECONDS,
            MIN_INTERVAL_SECONDS,
        ),
        remind_after=timedelta(
            hours=_float_env("UKIP_OPS_MONITOR_REMIND_HOURS", DEFAULT_REMIND_HOURS)
        ),
    )


def alert_kind(
    previous: Observation | None,
    status: str,
    failing: frozenset[str],
    now: datetime,
    remind_after: timedelta,
) -> str | None:
    """Which alert, if any, this observation calls for. Pure, so the policy is testable."""
    unhealthy = status in _UNHEALTHY
    was_unhealthy = previous is not None and previous.status in _UNHEALTHY
    if not unhealthy:
        return "recovered" if was_unhealthy else None
    if not was_unhealthy:
        return "degraded"
    if status == "critical" and previous.status != "critical":
        return "escalated"
    if failing != previous.failing:
        return "changed"
    if previous.alerted_at is None or now - previous.alerted_at >= remind_after:
        return "reminder"
    return None


EVALUATION_FAILED = "ops_checks_evaluation"


def _failed_evaluation_report(exc: Exception, now: datetime) -> dict:
    """What an evaluation that raised is reported as: critical, not silence.

    Some checks query the database without their own guard, so the outage they
    exist to catch can make ``run_operational_checks`` raise. Treating that as
    "no data" would hide the incident and, later, its recovery.
    """
    return {
        "status": "critical",
        "checked_at": now.isoformat(),
        "checks": [
            {
                "id": EVALUATION_FAILED,
                "status": "critical",
                "summary": f"Operational checks could not be evaluated: {type(exc).__name__}",
                "details": {},
            }
        ],
        "summary": {"critical": 1, "warning": 0},
    }


# Log and alert text is built only from this fixed vocabulary, never from the
# report's payload: the secrets check derives its status from key material, and
# nothing that flows from it should reach a log line verbatim.
KNOWN_CHECKS = (
    "database",
    "migrations",
    "scheduled_imports",
    "scheduled_reports",
    "ops_alerting",
    "scheduled_detection",
    "secrets",
    "backup_freshness",
    EVALUATION_FAILED,
)
_CHECK_LABELS = {name: name for name in KNOWN_CHECKS}
_STATUS_LABELS = {"ok": "ok", "degraded": "degraded", "critical": "critical"}


def _labels(failing: frozenset[str]) -> str:
    return (
        ", ".join(sorted(_CHECK_LABELS.get(name, "other") for name in failing))
        or "none"
    )


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, "unknown")


def _failing_checks(report: dict) -> frozenset[str]:
    return frozenset(
        c["id"] for c in report["checks"] if c["status"] in {"warning", "critical"}
    )


def _message(kind: str, report: dict, failing: frozenset[str]) -> str:
    if kind == "recovered":
        return "Operational checks recovered: all checks are ok again"
    return f"Operational checks {kind}: status {_status_label(report['status'])} ({_labels(failing)})"


# ── runtime state, exposed to the `scheduled_detection` check ────────────────

_thread: threading.Thread | None = None
_lock = threading.Lock()
_state: dict[str, Any] = {
    "started_at": None,
    "last_heartbeat_at": None,
    "last_run_at": None,
    "last_status": None,
    "last_alert_kind": None,
    "last_alert_at": None,
    "last_loop_error": None,
    "last_loop_error_at": None,
}
_memory: dict[str, Observation | None] = {"last": None}


def _update(**updates: Any) -> None:
    with _lock:
        _state.update(updates)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def get_status(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    config = load_config()
    with _lock:
        snapshot = dict(_state)
    heartbeat = snapshot["last_heartbeat_at"]
    return {
        "enabled": config.enabled,
        "alive": _thread is not None and _thread.is_alive(),
        "interval_seconds": config.interval_seconds,
        "stale_after_seconds": config.interval_seconds * 3,
        "remind_after_hours": config.remind_after.total_seconds() / 3600,
        "last_heartbeat_age_seconds": (
            round((now - heartbeat).total_seconds(), 2) if heartbeat else None
        ),
        **{
            key: _iso(value) if isinstance(value, datetime) else value
            for key, value in snapshot.items()
        },
    }


def run_once(
    db,
    *,
    now: datetime | None = None,
    remind_after: timedelta | None = None,
    run_checks: Callable[[Any], dict] | None = None,
    dispatch: Callable[..., None] | None = None,
) -> str | None:
    """Evaluate the checks once and alert if the state calls for it. Returns the alert kind."""
    from backend import ops_checks

    now = now or datetime.now(timezone.utc)
    remind_after = remind_after or load_config().remind_after
    try:
        report = (run_checks or ops_checks.run_operational_checks)(db)
    except Exception as exc:  # becomes a critical observation, and is logged
        logger.exception("[ops-monitor] operational checks raised")
        try:
            db.rollback()
        except Exception:  # noqa: BLE001, S110 — the session may already be unusable
            pass
        report = _failed_evaluation_report(exc, now)
    failing = _failing_checks(report)
    previous = _memory["last"]
    kind = alert_kind(previous, report["status"], failing, now, remind_after)

    if kind is not None:
        message = _message(kind, report, failing)
        log = logger.info if kind == "recovered" else logger.warning
        log("[ops-monitor] %s", message)
        (dispatch or ops_checks.dispatch_event)(
            db,
            ops_checks.OPS_ALERT_EVENT,
            message,
            {
                "kind": kind,
                "status": _status_label(report["status"]),
                "checked_at": report["checked_at"],
                "failing_checks": _labels(failing),
                "critical_checks": report["summary"].get("critical", 0),
                "warning_checks": report["summary"].get("warning", 0),
            },
        )
        _update(last_alert_kind=kind, last_alert_at=now)

    alerted_at = (
        now if kind is not None else (previous.alerted_at if previous else None)
    )
    _memory["last"] = Observation(report["status"], failing, alerted_at)
    _update(last_run_at=now, last_status=report["status"])
    return kind


def _loop(config: MonitorConfig) -> None:
    from backend import database

    # Let the other schedulers publish a first heartbeat before judging them.
    time.sleep(min(config.interval_seconds, MIN_INTERVAL_SECONDS))
    while True:
        _update(last_heartbeat_at=datetime.now(timezone.utc))
        try:
            with database.SessionLocal() as db:
                run_once(db, remind_after=config.remind_after)
            _update(
                last_heartbeat_at=datetime.now(timezone.utc),
                last_loop_error=None,
                last_loop_error_at=None,
            )
        except Exception:
            logger.exception("[ops-monitor] evaluation failed")
            _update(
                last_loop_error="ops_monitor_loop_error",
                last_loop_error_at=datetime.now(timezone.utc),
            )
        time.sleep(config.interval_seconds)


def start_monitor() -> bool:
    """Start the detection thread once. Returns whether it is running."""
    global _thread
    config = load_config()
    if not config.enabled:
        logger.warning(
            "[ops-monitor] disabled (UKIP_OPS_MONITOR_ENABLED=0): no scheduled detection"
        )
        return False
    if _thread is not None and _thread.is_alive():
        return True
    _thread = threading.Thread(
        target=_loop, args=(config,), daemon=True, name="ops-monitor"
    )
    _thread.start()
    _update(started_at=datetime.now(timezone.utc))
    logger.info(
        "[ops-monitor] started: every %ss, reminders after %s",
        config.interval_seconds,
        config.remind_after,
    )
    return True
