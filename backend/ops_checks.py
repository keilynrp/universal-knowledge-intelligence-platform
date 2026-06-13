import json
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend import models
from backend.backup_assurance import (
    evaluate_backup_freshness,
    evaluate_provider_reachability,
    latest_completed_backup,
)
from backend.db_revision import migration_drift
from backend.notifications.alert_sender import dispatch_event
from backend.routers import scheduled_imports, scheduled_reports


logger = logging.getLogger(__name__)

OPS_ALERT_EVENT = "ops.check_failed"


def _startup_side_effects_enabled() -> bool:
    return os.environ.get("UKIP_SKIP_STARTUP_SIDE_EFFECTS", "0") != "1"


def _serialize_dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
        if check["id"] == "secrets" and check["status"] == "critical":
            actions.append("Set JWT_SECRET_KEY and ENCRYPTION_KEY to strong unique values; see docs/operating/SECRETS_ROTATION_RUNBOOK.md.")
        if check["id"] == "secrets" and check["status"] == "warning":
            actions.append("Rotate stale secrets and/or run the re-encrypt script then drop retiring keys; see the secrets rotation runbook.")
        if check["id"] == "backup_freshness" and check["status"] == "warning":
            actions.append(
                "Verify the current backup job and confirm a successful recovery "
                "point before the 26-hour critical threshold."
            )
        if check["id"] == "backup_freshness" and check["status"] == "critical":
            actions.append(
                "Treat backup protection as unavailable: restore provider access "
                "or complete a valid backup, then follow BACKUP_RESTORE_RUNBOOK.md."
            )

    # Preserve order while dropping duplicates
    seen = set()
    deduped = []
    for action in actions:
        if action not in seen:
            deduped.append(action)
            seen.add(action)
    return deduped


def _secrets_check(db: Session) -> dict:
    """Secrets/credential rotation health (EPIC-017).

    critical: JWT using the insecure default key, or no encryption key configured.
    warning:  a tracked secret's last rotation is older than the cadence, or
              retiring keys are still configured (encryption or JWT).
    Reads the in-process module state (what the app actually uses), not os.environ.
    """
    from backend import auth, encryption, secret_rotation as sr

    jwt_default = auth.SECRET_KEY == auth._INSECURE_DEFAULT_KEY
    no_enc_key = not encryption.has_primary_key()
    enc_retiring = sr.encryption_retiring_keys_present()
    jwt_retiring = sr.jwt_retiring_keys_present()

    now = datetime.now(timezone.utc)
    max_age = timedelta(days=sr.SECRET_ROTATION_MAX_AGE_DAYS)
    stale = []
    for secret in ("ENCRYPTION_KEY", "JWT_SECRET_KEY"):
        last = sr.last_rotation_at(db, secret)
        if last is None:
            continue
        # DateTime columns come back tz-naive (SQLite/Postgres) — assume UTC.
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last) > max_age:
            stale.append(secret)

    details = {
        "jwt_insecure_default": jwt_default,
        "encryption_key_configured": not no_enc_key,
        "encryption_retiring_keys_present": enc_retiring,
        "jwt_retiring_keys_present": jwt_retiring,
        "stale_rotations": stale,
        "max_age_days": sr.SECRET_ROTATION_MAX_AGE_DAYS,
    }

    if jwt_default or no_enc_key:
        return _make_check("secrets", "critical",
            "Insecure secret configuration detected.", details)
    if stale or enc_retiring or jwt_retiring:
        return _make_check("secrets", "warning",
            "Secrets need attention (stale rotation or lingering retiring keys).", details)
    return _make_check("secrets", "ok", "Secret keys are non-default and rotations are current.", details)


def _backup_freshness_check(db: Session, *, now: datetime) -> dict:
    if os.environ.get("UKIP_BACKUP_MONITOR_ENABLED", "0") != "1":
        return _make_check(
            "backup_freshness",
            "skipped",
            "Backup freshness monitoring is disabled.",
            {"monitor_enabled": False},
        )

    environment = os.environ.get("UKIP_BACKUP_ENVIRONMENT", "production")
    reachability = evaluate_provider_reachability(
        reported_reachable=os.environ.get("UKIP_BACKUP_PROVIDER_REACHABLE"),
        observed_at=os.environ.get("UKIP_BACKUP_PROVIDER_REACHABLE_AT"),
        now=now,
    )
    provider_reachable = reachability["reachable"]
    try:
        latest = latest_completed_backup(db, environment)
    except Exception as exc:
        logger.exception("ops_check_backup_freshness_query_failed")
        return _make_check(
            "backup_freshness",
            "critical",
            "Backup freshness evidence could not be queried.",
            {
                "monitor_enabled": True,
                "environment": environment,
                "provider_reachable": provider_reachable,
                "provider_reachability_source": reachability["source"],
                "reason_codes": ["backup_query_failed"],
                "error": str(exc),
            },
        )
    result = evaluate_backup_freshness(
        latest_completed_at=latest.completed_at if latest else None,
        now=now,
        size_bytes=latest.size_bytes if latest else None,
        integrity_ref=latest.integrity_ref if latest else None,
        provider_reachable=provider_reachable,
    )
    details = {
        **result,
        "monitor_enabled": True,
        "environment": environment,
        "provider_reachable": provider_reachable,
        "provider_reachability_source": reachability["source"],
        "latest_backup_id": latest.backup_id if latest else None,
        "latest_completed_at": _serialize_dt(latest.completed_at) if latest else None,
    }
    summaries = {
        "ok": "The latest backup satisfies the configured recovery point objective.",
        "warning": "The latest backup is outside the RPO and approaching the critical threshold.",
        "critical": "Backup protection is unavailable, stale, or invalid.",
    }
    return _make_check(
        "backup_freshness",
        result["status"],
        summaries[result["status"]],
        details,
    )


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
        _secrets_check(db),
        _backup_freshness_check(db, now=now),
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
