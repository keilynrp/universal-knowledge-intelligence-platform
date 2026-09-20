"""Provider-neutral persistence and health evaluation for backup assurance."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, func, not_, or_
from sqlalchemy.orm import Session

from backend.models import BackupAssuranceEvent

BACKUP_RPO_HOURS = 24
BACKUP_CRITICAL_AFTER_HOURS = 26
PROVIDER_REACHABILITY_MAX_AGE_MINUTES = 15

# B4 (#320). The two call sites used to read the reachability assertion straight
# from the environment, but a running container's environment cannot change, so
# nothing could keep a 15-minute-fresh signal current without restarting the
# backend every few minutes. A probe colocated with production (systemd timer or
# Dokploy schedule) instead writes a heartbeat document that this process reads
# on every evaluation. The application still holds no provider credential: the
# document carries a boolean and a timestamp, nothing else.
REACHABILITY_FILE_ENV = "UKIP_BACKUP_PROVIDER_REACHABILITY_FILE"
# The document is two fields. Anything larger is not one of ours; refuse it
# instead of reading an arbitrary file into memory.
REACHABILITY_FILE_MAX_BYTES = 4096


class _ReachabilityFileError(Exception):
    """Internal: carries the non-secret source label to report."""

    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.source = source


def _load_reachability_file(path: str) -> tuple[str, str | None]:
    """Read the heartbeat document, or raise with the source label to report."""
    document_path = Path(path)
    try:
        size = document_path.stat().st_size
    except FileNotFoundError as exc:
        raise _ReachabilityFileError("missing_reachability_file") from exc
    except OSError as exc:
        raise _ReachabilityFileError("invalid_reachability_file") from exc

    if size > REACHABILITY_FILE_MAX_BYTES:
        raise _ReachabilityFileError("invalid_reachability_file")

    try:
        document = json.loads(document_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # removed between stat() and read()
        raise _ReachabilityFileError("missing_reachability_file") from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise _ReachabilityFileError("invalid_reachability_file") from exc

    if not isinstance(document, dict):
        raise _ReachabilityFileError("invalid_reachability_file")
    reachable = document.get("reachable")
    if not isinstance(reachable, bool):
        raise _ReachabilityFileError("invalid_reachability_file")
    observed_at = document.get("observed_at")
    if observed_at is not None and not isinstance(observed_at, str):
        raise _ReachabilityFileError("invalid_reachability_file")

    return ("1" if reachable else "0", observed_at)


def resolve_provider_reachability(
    *,
    now: datetime,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Evaluate the reachability signal from whichever channel is configured.

    With ``UKIP_BACKUP_PROVIDER_REACHABILITY_FILE`` set, the heartbeat document
    is the only source: falling back to the environment when the probe's file
    is missing would turn a dead probe into a green signal, which is the exact
    failure this channel exists to prevent. Without it, the environment
    variables behave exactly as before.
    """
    environment = os.environ if env is None else env
    path = (environment.get(REACHABILITY_FILE_ENV) or "").strip()
    if path:
        try:
            reported_reachable, observed_at = _load_reachability_file(path)
        except _ReachabilityFileError as exc:
            return {"reachable": False, "source": exc.source}
        return evaluate_provider_reachability(
            reported_reachable=reported_reachable,
            observed_at=observed_at,
            now=now,
            origin="file",
        )
    return evaluate_provider_reachability(
        reported_reachable=environment.get("UKIP_BACKUP_PROVIDER_REACHABLE"),
        observed_at=environment.get("UKIP_BACKUP_PROVIDER_REACHABLE_AT"),
        now=now,
    )

# What a backup event covers. `database` governs the overall freshness
# verdict; `volume` is reported alongside it but cannot stand in for it.
VALID_SCOPES = ("database", "volume")
DEFAULT_SCOPE = "database"


def _legacy_volume_expression():
    """The SQL half of `classify_legacy_scope`, for rows whose scope is NULL.

    Kept next to the Python rule, and pinned to it by a test, because the two
    decide the same question in different places.
    """
    provider = func.lower(func.coalesce(BackupAssuranceEvent.provider, ""))
    backup_id = func.lower(func.coalesce(BackupAssuranceEvent.backup_id, ""))
    return or_(provider.like("%volume%"), backup_id.like("%.tar"))


def scope_filter(scope: str):
    """Match events of *scope*, including pre-column rows with a NULL scope."""
    if scope not in VALID_SCOPES:
        raise ValueError(f"Unsupported scope: {scope!r}")
    legacy_volume = _legacy_volume_expression()
    if scope == "volume":
        return or_(
            BackupAssuranceEvent.scope == "volume",
            and_(BackupAssuranceEvent.scope.is_(None), legacy_volume),
        )
    return or_(
        BackupAssuranceEvent.scope == DEFAULT_SCOPE,
        and_(BackupAssuranceEvent.scope.is_(None), not_(legacy_volume)),
    )


def classify_legacy_scope(*, provider: str | None, backup_id: str | None) -> str:
    """Infer the scope of a row written before the column existed.

    Production holds three such rows: two PostgreSQL dumps and one volume
    archive. Treating all of them as `database` would mislabel the archive as
    the object that governs freshness — the exact defect this change fixes — so
    the scope is derived from what each row already recorded about itself. The
    rows themselves are never rewritten: the table is append-only.
    """
    haystack = f"{provider or ''} {backup_id or ''}".casefold()
    if "volume" in haystack or haystack.rstrip().endswith(".tar"):
        return "volume"
    return DEFAULT_SCOPE


_VALID_EVENT_STATUSES = {
    "backup": {"completed", "failed"},
    "restore_drill": {"passed", "passed_with_risk", "failed"},
}
_SECRET_KEY_MARKERS = {
    "secret",
    "password",
    "token",
    "credential",
    "database_url",
    "connection_string",
}


def evaluate_provider_reachability(
    *,
    reported_reachable: str | None,
    observed_at: str | None,
    now: datetime,
    origin: str = "environment",
) -> dict[str, Any]:
    """Decide whether *reported_reachable* is a usable assertion right now.

    *origin* only labels the reported source, so a stale heartbeat file is
    distinguishable from a stale environment variable in /ops output. The rules
    themselves — an assertion must say "1", carry a UTC timestamp, and be no
    older than PROVIDER_REACHABILITY_MAX_AGE_MINUTES — are the same for both.
    """
    if reported_reachable != "1":
        return {
            "reachable": False,
            "source": (
                "explicit_unreachable"
                if reported_reachable is not None
                else "unknown_default"
            ),
        }
    if not observed_at:
        return {
            "reachable": False,
            "source": f"{origin}_assertion_missing_timestamp",
        }
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("timezone required")
    except (TypeError, ValueError):
        return {
            "reachable": False,
            "source": f"invalid_{origin}_assertion",
        }

    observed_utc = observed.astimezone(timezone.utc)
    now_utc = now.astimezone(timezone.utc)
    age = now_utc - observed_utc
    if age < -timedelta(minutes=5):
        return {
            "reachable": False,
            "source": f"future_{origin}_assertion",
        }
    if age > timedelta(minutes=PROVIDER_REACHABILITY_MAX_AGE_MINUTES):
        return {
            "reachable": False,
            "source": f"stale_{origin}_assertion",
        }
    return {
        "reachable": True,
        "source": f"timestamped_{origin}_assertion",
    }


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).casefold()
            if any(marker in normalized_key for marker in _SECRET_KEY_MARKERS):
                return True
            if _contains_secret_key(nested_value):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_secret_key(item) for item in value)
    return False


def record_event(
    db: Session,
    *,
    event_type: str,
    status: str,
    environment: str,
    provider: str,
    started_at: datetime,
    operator: str,
    backup_id: str | None = None,
    completed_at: datetime | None = None,
    release: str | None = None,
    alembic_revision: str | None = None,
    size_bytes: int | None = None,
    integrity_ref: str | None = None,
    encrypted: bool | None = None,
    storage_region: str | None = None,
    retention_class: str | None = None,
    expected_rpo_hours: float | None = None,
    expected_rto_hours: float | None = None,
    achieved_rpo_hours: float | None = None,
    achieved_rto_hours: float | None = None,
    evidence: dict[str, Any] | None = None,
    scope: str | None = None,
) -> BackupAssuranceEvent:
    scope = DEFAULT_SCOPE if scope is None else scope
    if scope not in VALID_SCOPES:
        raise ValueError(f"Unsupported scope: {scope!r}")
    if event_type not in _VALID_EVENT_STATUSES:
        raise ValueError(f"Unsupported event_type: {event_type!r}")
    if status not in _VALID_EVENT_STATUSES[event_type]:
        raise ValueError(
            f"Unsupported status {status!r} for event_type {event_type!r}"
        )
    if evidence is not None and _contains_secret_key(evidence):
        raise ValueError("Evidence contains a secret-like key")

    event = BackupAssuranceEvent(
        event_type=event_type,
        status=status,
        scope=scope,
        environment=environment,
        provider=provider,
        backup_id=backup_id,
        started_at=_utc_naive(started_at),
        completed_at=_utc_naive(completed_at),
        release=release,
        alembic_revision=alembic_revision,
        size_bytes=size_bytes,
        integrity_ref=integrity_ref,
        encrypted=encrypted,
        storage_region=storage_region,
        retention_class=retention_class,
        operator=operator,
        expected_rpo_hours=expected_rpo_hours,
        expected_rto_hours=expected_rto_hours,
        achieved_rpo_hours=achieved_rpo_hours,
        achieved_rto_hours=achieved_rto_hours,
        evidence_json=json.dumps(evidence, sort_keys=True) if evidence is not None else None,
    )
    db.add(event)
    db.flush()
    db.refresh(event)
    return event


def evaluate_backup_freshness(
    *,
    latest_completed_at: datetime | None,
    now: datetime,
    size_bytes: int | None,
    integrity_ref: str | None,
    provider_reachable: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    age_hours: float | None = None

    if latest_completed_at is None:
        reasons.append("backup_missing")
    else:
        completed_utc = _utc_naive(latest_completed_at)
        now_utc = _utc_naive(now)
        age_hours = (now_utc - completed_utc).total_seconds() / 3600
        if age_hours < 0:
            reasons.append("backup_from_future")
        if age_hours > BACKUP_CRITICAL_AFTER_HOURS:
            reasons.append("backup_stale")

    if size_bytes is None or size_bytes <= 0:
        reasons.append("backup_empty")
    if not integrity_ref:
        reasons.append("integrity_missing")
    if not provider_reachable:
        reasons.append("provider_unreachable")

    if reasons:
        status = "critical"
    elif age_hours is not None and age_hours > BACKUP_RPO_HOURS:
        status = "warning"
        reasons.append("backup_approaching_critical_threshold")
    else:
        status = "ok"

    return {
        "status": status,
        "age_hours": age_hours,
        "rpo_hours": BACKUP_RPO_HOURS,
        "critical_after_hours": BACKUP_CRITICAL_AFTER_HOURS,
        "reason_codes": reasons,
    }


def latest_completed_backup(
    db: Session,
    environment: str,
    scope: str = DEFAULT_SCOPE,
) -> BackupAssuranceEvent | None:
    """The newest completed backup *of that scope*.

    Scoped deliberately: the volume job runs minutes after the database job, so
    an unscoped query reports the volume archive as the latest backup and lets a
    10 KB tar of an empty directory hold the freshness signal green while the
    database goes unbacked (#320).
    """
    return (
        db.query(BackupAssuranceEvent)
        .filter(
            BackupAssuranceEvent.event_type == "backup",
            BackupAssuranceEvent.status == "completed",
            BackupAssuranceEvent.environment == environment,
            scope_filter(scope),
            BackupAssuranceEvent.completed_at.is_not(None),
        )
        .order_by(
            BackupAssuranceEvent.completed_at.desc(),
            BackupAssuranceEvent.id.desc(),
        )
        .first()
    )


def latest_failed_backup(
    db: Session,
    environment: str,
) -> BackupAssuranceEvent | None:
    return (
        db.query(BackupAssuranceEvent)
        .filter(
            BackupAssuranceEvent.event_type == "backup",
            BackupAssuranceEvent.status == "failed",
            BackupAssuranceEvent.environment == environment,
        )
        .order_by(*failed_backup_ordering())
        .first()
    )


def failed_backup_ordering():
    return (
        BackupAssuranceEvent.completed_at.desc().nullslast(),
        BackupAssuranceEvent.created_at.desc(),
        BackupAssuranceEvent.id.desc(),
    )


def parse_event_evidence(
    event: BackupAssuranceEvent | None,
) -> dict[str, Any] | None:
    if event is None or not event.evidence_json:
        return None
    try:
        evidence = json.loads(event.evidence_json)
    except (TypeError, ValueError):
        return None
    return evidence if isinstance(evidence, dict) else None


def failure_reason_from_event(
    event: BackupAssuranceEvent | None,
) -> str | None:
    evidence = parse_event_evidence(event)
    if evidence is None:
        return None
    reason = evidence.get("failure_reason")
    return reason if isinstance(reason, str) and reason.strip() else None
