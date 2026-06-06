import json
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend import models
from backend.db_revision import migration_drift
from backend.notifications.alert_sender import dispatch_event
from backend.routers import scheduled_imports, scheduled_reports


logger = logging.getLogger(__name__)

OPS_ALERT_EVENT = "ops.check_failed"


def _startup_side_effects_enabled() -> bool:
    return os.environ.get("UKIP_SKIP_STARTUP_SIDE_EFFECTS", "0") != "1"


def _serialize_dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _make_check(check_id: str, status: str, summary: str, details: dict) -> dict:
    return {
        "id": check_id,
        "status": status,
        "summary": summary,
        "details": details,
    }


def _aggregate_status(checks: list[dict]) -> tuple[str, dict[str, int]]:
    counts = {"ok": 0, "warning": 0, "critical": 0, "skipped": 0}
    for check in checks:
        counts[check["status"]] = counts.get(check["status"], 0) + 1

    if counts["critical"] > 0:
        return "critical", counts
    if counts["warning"] > 0:
        return "degraded", counts
    return "ok", counts


def _db_check(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return _make_check(
            "database",
            "ok",
            "Database connectivity probe succeeded.",
            {},
        )
    except Exception as exc:
        logger.exception("ops_check_database_failed")
        return _make_check(
            "database",
            "critical",
            "Database connectivity probe failed.",
            {"error": str(exc)},
        )


def _scheduler_check(
    *,
    db: Session,
    now: datetime,
    scheduler_name: str,
    runtime_status: dict,
    model,
    overdue_tolerance_seconds: int,
) -> dict:
    if not _startup_side_effects_enabled():
        return _make_check(
            scheduler_name,
            "skipped",
            "Scheduler checks skipped because startup side effects are disabled.",
            {"startup_side_effects_enabled": False},
        )

    overdue_before = now - timedelta(seconds=overdue_tolerance_seconds)
    recent_error_after = now - timedelta(hours=24)
    overdue_count = db.query(model).filter(
        model.is_active == True,  # noqa: E712
        model.next_run_at.isnot(None),
        model.next_run_at < overdue_before,
        model.last_status != "running",
    ).count()
    recent_error_count = db.query(model).filter(
        model.is_active == True,  # noqa: E712
        model.last_status == "error",
        model.last_run_at.isnot(None),
        model.last_run_at >= recent_error_after,
    ).count()

    details = {
        "thread_alive": runtime_status["alive"],
        "poll_seconds": runtime_status["poll_seconds"],
        "stale_after_seconds": runtime_status["stale_after_seconds"],
        "last_heartbeat_at": runtime_status["last_heartbeat_at"],
        "last_heartbeat_age_seconds": runtime_status["last_heartbeat_age_seconds"],
        "last_success_at": runtime_status["last_success_at"],
        "last_loop_error": runtime_status["last_loop_error"],
        "last_loop_error_at": runtime_status["last_loop_error_at"],
        "overdue_schedules": overdue_count,
        "recent_error_schedules": recent_error_count,
    }

    if not runtime_status["alive"]:
        return _make_check(
            scheduler_name,
            "critical",
            "Scheduler thread is not alive.",
            details,
        )

    heartbeat_age = runtime_status["last_heartbeat_age_seconds"]
    if heartbeat_age is not None and heartbeat_age > runtime_status["stale_after_seconds"]:
        return _make_check(
            scheduler_name,
            "critical",
            "Scheduler heartbeat is stale.",
            details,
        )

    if recent_error_count > 0 or overdue_count > 0 or runtime_status["last_loop_error"]:
        issues = []
        if overdue_count > 0:
            issues.append(f"{overdue_count} overdue schedules")
        if recent_error_count > 0:
            issues.append(f"{recent_error_count} schedules failed in the last 24h")
        if runtime_status["last_loop_error"]:
            issues.append("last loop raised an exception")
        return _make_check(
            scheduler_name,
            "warning",
            "Scheduler is alive but needs attention: " + ", ".join(issues) + ".",
            details,
        )

    return _make_check(
        scheduler_name,
        "ok",
        "Scheduler heartbeat and queue look healthy.",
        details,
    )


def _migrations_check() -> dict:
    """Detect schema drift: is the DB behind the latest Alembic migration?

    Mitigates the fail-open entrypoint (a failed `alembic upgrade head` keeps
    the service up but leaves the schema stale). A stale schema is reported as
    ``critical`` so the ops-check alert fan-out (ops.check_failed) fires.

    Skipped when startup side effects are disabled (unit tests run against a
    create_all() SQLite schema with no alembic_version table).
    """
    if not _startup_side_effects_enabled():
        return _make_check(
            "migrations",
            "skipped",
            "Migration drift check skipped because startup side effects are disabled.",
            {"startup_side_effects_enabled": False},
        )

    from backend import database

    drift = migration_drift(database.engine)
    details = {
        "current": drift["current"],
        "heads": drift["heads"],
        "error": drift["error"],
    }
    if drift["error"]:
        return _make_check(
            "migrations",
            "critical",
            "Could not determine the database schema migration state.",
            details,
        )
    if drift["is_stale"]:
        return _make_check(
            "migrations",
            "critical",
            "Database schema is behind the latest migration — drift detected.",
            details,
        )
    return _make_check(
        "migrations",
        "ok",
        "Database schema is at the latest migration head.",
        details,
    )


def _alert_channel_check(db: Session) -> dict:
    active_channels = db.query(models.AlertChannel).filter(
        models.AlertChannel.is_active == True,  # noqa: E712
    ).all()

    subscribed = 0
    invalid_payloads = 0
    for channel in active_channels:
        try:
            events = json.loads(channel.events or "[]")
        except Exception:
            invalid_payloads += 1
            events = []
        if OPS_ALERT_EVENT in events:
            subscribed += 1

    details = {
        "active_channels": len(active_channels),
        "ops_alert_channels": subscribed,
        "channels_with_invalid_event_payload": invalid_payloads,
        "event": OPS_ALERT_EVENT,
    }

    if subscribed == 0:
        return _make_check(
            "ops_alerting",
            "warning",
            "No active alert channels are subscribed to ops.check_failed.",
            details,
        )

    if invalid_payloads > 0:
        return _make_check(
            "ops_alerting",
            "warning",
            "Operational alerting exists, but some channel event payloads could not be parsed.",
            details,
        )

    return _make_check(
        "ops_alerting",
        "ok",
        "Operational alerting baseline is configured.",
        details,
    )


def _recommended_actions(checks: list[dict]) -> list[str]:
    actions: list[str] = []
    for check in checks:
        if check["id"] == "database" and check["status"] == "critical":
            actions.append("Restore database connectivity before trusting other operational signals.")
        if check["id"] == "migrations" and check["status"] == "critical":
            actions.append(
                "Apply pending migrations: run the ukip-migrate ops service "
                "(docker compose --profile ops run --rm ukip-migrate) or `alembic upgrade head`."
            )
        if check["id"] in {"scheduled_imports", "scheduled_reports"} and check["status"] == "critical":
            actions.append(f"Restart the application or inspect the {check['id']} scheduler thread and logs.")
        if check["id"] in {"scheduled_imports", "scheduled_reports"} and check["status"] == "warning":
            actions.append(f"Review overdue or failed jobs for {check['id']} and inspect recent scheduler logs.")
        if check["id"] == "ops_alerting" and check["status"] == "warning":
            actions.append("Create at least one active Alert Channel subscribed to ops.check_failed.")

    # Preserve order while dropping duplicates
    seen = set()
    deduped = []
    for action in actions:
        if action not in seen:
            deduped.append(action)
            seen.add(action)
    return deduped


def run_operational_checks(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    checks = [
        _db_check(db),
        _migrations_check(),
        _scheduler_check(
            db=db,
            now=now,
            scheduler_name="scheduled_imports",
            runtime_status=scheduled_imports.get_scheduler_status(now=now),
            model=models.ScheduledImport,
            overdue_tolerance_seconds=scheduled_imports.SCHEDULER_POLL_SECONDS * 3,
        ),
        _scheduler_check(
            db=db,
            now=now,
            scheduler_name="scheduled_reports",
            runtime_status=scheduled_reports.get_scheduler_status(now=now),
            model=models.ScheduledReport,
            overdue_tolerance_seconds=scheduled_reports.SCHEDULER_POLL_SECONDS * 3,
        ),
        _alert_channel_check(db),
    ]
    status, summary = _aggregate_status(checks)
    return {
        "status": status,
        "service": "ukip-backend",
        "checked_at": _serialize_dt(now),
        "checks": checks,
        "summary": summary,
        "recommended_actions": _recommended_actions(checks),
    }


def dispatch_operational_alert_if_needed(db: Session, report: dict) -> dict:
    if report["status"] == "ok":
        return {
            "attempted": False,
            "event": OPS_ALERT_EVENT,
            "reason": "status_ok",
        }

    failing_checks = [
        check["id"]
        for check in report["checks"]
        if check["status"] in {"warning", "critical"}
    ]

    dispatch_event(
        db,
        OPS_ALERT_EVENT,
        f"Operational checks detected a {report['status']} runtime state",
        {
            "status": report["status"],
            "checked_at": report["checked_at"],
            "critical_checks": report["summary"]["critical"],
            "warning_checks": report["summary"]["warning"],
            "failing_checks": ", ".join(failing_checks),
        },
    )
    return {
        "attempted": True,
        "event": OPS_ALERT_EVENT,
        "reason": "dispatched",
    }
