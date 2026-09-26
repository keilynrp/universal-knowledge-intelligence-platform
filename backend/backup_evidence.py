"""Ingest backup evidence that the production host records, without a credential.

Issue #370, openspec change ``automate-backup-evidence``. Freshness is measured
against recorded evidence, and recording was manual, so ``backup_freshness``
went critical every day nobody recorded the cycle, while the backups
themselves were fine.

A recorder on the production host (``scripts/ukip-backup-evidence-recorder.sh``)
streams the newest object of each scope once, computes SHA-256 over the stored
bytes, runs ``gzip -t`` on dumps, and writes one JSON document per backup into
the signals directory this container mounts read-only. The reachability probe
uses the same channel. This module reads those documents and records them as
``backup`` events. No application credential exists for any of it: the trust
boundary is root on the host, which already holds the database.

Every document is untrusted input. :func:`parse_evidence_document` accepts
exactly the schema below and rejects everything else with a reason, never an
exception, so one bad file cannot stop the ops monitor that calls
:func:`ingest_backup_evidence`.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.backup_assurance import VALID_SCOPES, record_event, scope_filter
from backend.models import BackupAssuranceEvent

logger = logging.getLogger(__name__)

EVIDENCE_DIR_ENV = "UKIP_BACKUP_EVIDENCE_DIR"
DEFAULT_EVIDENCE_DIR = "/run/ukip-signals/backup-evidence"
ENVIRONMENT_ENV = "UKIP_BACKUP_ENVIRONMENT"

RECORDER_OPERATOR = "system:backup-recorder"
EVIDENCE_METHOD = "sha256-stream+gzip-t"

#: A document is eleven short fields. Anything larger is not one of ours; it is
#: refused before being read into memory.
MAX_DOCUMENT_BYTES = 8192
#: The recorder prunes its own documents after the same window.
MAX_EVIDENCE_AGE = timedelta(days=14)
#: Clock skew tolerated between the host that wrote a document and this one.
FUTURE_TOLERANCE = timedelta(minutes=5)

_KEYS = frozenset({
    "schema_version", "recorder", "observed_at", "environment", "scope",
    "backup_id", "completed_at", "size_bytes", "sha256", "gzip_ok", "provider",
})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class EvidenceDocument:
    recorder: str
    observed_at: datetime
    environment: str
    scope: str
    backup_id: str
    completed_at: datetime
    size_bytes: int
    sha256: str
    gzip_ok: bool | None
    provider: str


@dataclass(frozen=True)
class Rejection:
    reason: str


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _short_text(value: object, limit: int) -> str | None:
    if isinstance(value, str) and 0 < len(value.strip()) <= limit:
        return value.strip()
    return None


def parse_evidence_document(
    raw: bytes, *, environment: str, now: datetime
) -> EvidenceDocument | Rejection:
    """The document if it is exactly one of ours, or the reason it is not."""
    if len(raw) > MAX_DOCUMENT_BYTES:
        return Rejection("oversized")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return Rejection("malformed_json")
    if not isinstance(document, dict):
        return Rejection("not_an_object")
    keys = set(document)
    if keys - _KEYS:
        return Rejection("unknown_keys")
    if _KEYS - keys:
        return Rejection("missing_keys")
    if document["schema_version"] != 1 or isinstance(document["schema_version"], bool):
        return Rejection("unsupported_schema_version")
    if document["environment"] != environment:
        return Rejection("other_environment")
    scope = document["scope"]
    if scope not in VALID_SCOPES:
        return Rejection("unknown_scope")
    backup_id = _short_text(document["backup_id"], 200)
    if backup_id is None or backup_id.startswith("/") or ".." in backup_id.split("/"):
        return Rejection("invalid_backup_id")
    size = document["size_bytes"]
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        return Rejection("invalid_size")
    digest = document["sha256"]
    if not isinstance(digest, str) or not _SHA256.match(digest):
        return Rejection("invalid_sha256")
    gzip_ok = document["gzip_ok"]
    if scope == "database" and not isinstance(gzip_ok, bool):
        return Rejection("gzip_result_required_for_database")
    if scope != "database" and gzip_ok is not None:
        return Rejection("gzip_result_only_for_database")
    completed_at = _timestamp(document["completed_at"])
    observed_at = _timestamp(document["observed_at"])
    if completed_at is None or observed_at is None:
        return Rejection("invalid_timestamp")
    if completed_at > now + FUTURE_TOLERANCE or observed_at > now + FUTURE_TOLERANCE:
        return Rejection("timestamp_in_future")
    if completed_at < now - MAX_EVIDENCE_AGE:
        return Rejection("too_old")
    recorder = _short_text(document["recorder"], 80)
    provider = _short_text(document["provider"], 80)
    if recorder is None or provider is None:
        return Rejection("invalid_recorder_or_provider")
    return EvidenceDocument(
        recorder=recorder,
        observed_at=observed_at,
        environment=environment,
        scope=scope,
        backup_id=backup_id,
        completed_at=completed_at,
        size_bytes=size,
        sha256=digest,
        gzip_ok=gzip_ok,
        provider=provider,
    )


def same_backup(recorded: str | None, observed: str) -> bool:
    """Whether two backup ids name the same object.

    The recorder writes the key relative to the backup prefix. Manual cycles may
    have recorded the key with a leading path (the evidence notes cite
    ``ukip-dbukip-eqmmhw/pg/…sql.gz``), and which form the recorded events carry
    cannot be seen from the repository. So a suffix on a path boundary counts
    as the same backup. Object names carry a millisecond timestamp, so this
    cannot conflate two backups of one scope.
    """
    if not recorded:
        return False
    return (
        recorded == observed
        or recorded.endswith("/" + observed)
        or observed.endswith("/" + recorded)
    )


def _already_recorded(db: Session, document: EvidenceDocument) -> bool:
    name = document.backup_id.rsplit("/", 1)[-1]
    candidates = (
        db.query(BackupAssuranceEvent.backup_id)
        .filter(
            BackupAssuranceEvent.event_type == "backup",
            BackupAssuranceEvent.environment == document.environment,
            scope_filter(document.scope),
            BackupAssuranceEvent.backup_id.like(f"%{name}"),
        )
        .all()
    )
    return any(same_backup(row.backup_id, document.backup_id) for row in candidates)


def _evidence_files(directory: Path) -> list[Path]:
    """Regular ``*.json`` files directly in *directory*; symlinks are never followed."""
    try:
        entries = sorted(directory.iterdir())
    except FileNotFoundError:
        return []
    return [
        entry for entry in entries
        if entry.suffix == ".json" and entry.is_file() and not entry.is_symlink()
    ]


def _read_bounded(path: Path) -> bytes:
    with path.open("rb") as handle:
        return handle.read(MAX_DOCUMENT_BYTES + 1)


def ingest_backup_evidence(
    db: Session,
    *,
    directory: Path | None = None,
    environment: str | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Record every valid, not-yet-recorded evidence document. Never raises for a document.

    Returns counts, so the caller and the tests can see what happened without
    parsing logs.
    """
    directory = directory or Path(os.environ.get(EVIDENCE_DIR_ENV) or DEFAULT_EVIDENCE_DIR)
    environment = environment or os.environ.get(ENVIRONMENT_ENV, "production")
    now = now or datetime.now(timezone.utc)
    counts = {"recorded": 0, "already_recorded": 0, "rejected": 0}

    for path in _evidence_files(directory):
        try:
            raw = _read_bounded(path)
        except OSError:
            logger.warning("[backup-evidence] %s rejected: unreadable", path.name)
            counts["rejected"] += 1
            continue
        parsed = parse_evidence_document(raw, environment=environment, now=now)
        if isinstance(parsed, Rejection):
            logger.warning("[backup-evidence] %s rejected: %s", path.name, parsed.reason)
            counts["rejected"] += 1
            continue
        if _already_recorded(db, parsed):
            counts["already_recorded"] += 1
            continue
        record_event(
            db,
            event_type="backup",
            status="failed" if parsed.gzip_ok is False else "completed",
            scope=parsed.scope,
            environment=parsed.environment,
            provider=parsed.provider,
            backup_id=parsed.backup_id,
            # The object's timestamp is all the provider exposes; the manual
            # cycles record the same value for both.
            started_at=parsed.completed_at,
            completed_at=parsed.completed_at,
            size_bytes=parsed.size_bytes,
            integrity_ref=f"sha256:{parsed.sha256}",
            operator=RECORDER_OPERATOR,
            evidence={
                "method": EVIDENCE_METHOD,
                "source": "host-signal",
                "recorder": parsed.recorder,
                "observed_at": parsed.observed_at.isoformat(),
                "gzip_ok": parsed.gzip_ok,
                "document": path.name,
            },
        )
        db.commit()
        counts["recorded"] += 1
        logger.info(
            "[backup-evidence] recorded %s backup %s from %s",
            parsed.scope, parsed.backup_id, path.name,
        )
    return counts
