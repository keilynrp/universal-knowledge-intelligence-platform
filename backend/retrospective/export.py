"""Warehouse export for the retrospective layer (Phase 5).

Produces versioned, tenant-scoped, BigQuery-compatible datasets plus an auditable
manifest from the append-only history — without requiring a configured warehouse
(historical-warehouse-export-contract spec). The layer keeps working with no
warehouse: ``export_readiness`` reports ``not_configured`` and read/write paths
are unaffected.

Design:
- **Schemas (5.1)** — BigQuery-safe scalar/timestamp/date/JSON columns with an
  explicit partition column (``recorded_date``) and clustering columns.
- **Manifest (5.2)** — versioned, with row counts, partition range, checksum,
  tenant scope, and a sanitized status (never stores credentials).
- **Jobs (5.3/5.4)** — deterministic + idempotent by (dataset, version, org
  scope, partition range): re-running yields the same rows (deduped by stable id)
  and the same checksum.
- **Validation (5.5)** — row counts, schema drift, and tenant isolation.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from .. import models


# ── 5.1 BigQuery-compatible schemas ─────────────────────────────────────────

@dataclass(frozen=True)
class Column:
    name: str
    type: str  # STRING | INT64 | FLOAT64 | BOOL | TIMESTAMP | DATE | JSON
    mode: str = "NULLABLE"


EVENT_EXPORT_SCHEMA: tuple[Column, ...] = (
    Column("event_id", "STRING", "REQUIRED"),
    Column("event_type", "STRING", "REQUIRED"),
    Column("schema_version", "INT64", "REQUIRED"),
    Column("org_id", "INT64"),
    Column("domain_object_type", "STRING", "REQUIRED"),
    Column("domain_object_id", "STRING", "REQUIRED"),
    Column("occurred_at", "TIMESTAMP", "REQUIRED"),
    Column("recorded_at", "TIMESTAMP", "REQUIRED"),
    Column("recorded_date", "DATE", "REQUIRED"),  # partition column
    Column("source", "STRING", "REQUIRED"),
    Column("actor_type", "STRING", "REQUIRED"),
    Column("actor_id", "STRING"),
    Column("correlation_id", "STRING"),
    Column("payload", "JSON", "REQUIRED"),
    Column("lineage", "JSON"),
)

SNAPSHOT_EXPORT_SCHEMA: tuple[Column, ...] = (
    Column("snapshot_id", "STRING", "REQUIRED"),
    Column("snapshot_type", "STRING", "REQUIRED"),
    Column("schema_version", "INT64", "REQUIRED"),
    Column("org_id", "INT64"),
    Column("subject_type", "STRING", "REQUIRED"),
    Column("subject_id", "STRING", "REQUIRED"),
    Column("valid_at", "TIMESTAMP", "REQUIRED"),
    Column("recorded_at", "TIMESTAMP", "REQUIRED"),
    Column("recorded_date", "DATE", "REQUIRED"),  # partition column
    Column("payload", "JSON", "REQUIRED"),
    Column("lineage", "JSON"),
)

EVENT_PARTITION_FIELD = "recorded_date"
EVENT_CLUSTERING_FIELDS = ("event_type", "org_id", "schema_version")
SNAPSHOT_PARTITION_FIELD = "recorded_date"
SNAPSHOT_CLUSTERING_FIELDS = ("snapshot_type", "org_id", "schema_version")


# ── 5.2 Manifest ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExportManifest:
    export_id: str
    dataset_name: str
    dataset_version: str
    schema_version: int
    org_scope: Optional[int]
    started_at: datetime
    finished_at: datetime
    row_counts: int
    partition_range: Optional[tuple[str, str]]
    source_query: str
    checksum: str
    status: str  # completed | empty | not_configured | failed
    error_code: Optional[str] = None


@dataclass(frozen=True)
class ExportResult:
    manifest: ExportManifest
    rows: list[dict] = field(default_factory=list)


# ── Row projection (warehouse-safe records) ─────────────────────────────────

def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _project_event(row: models.RetrospectiveEvent) -> dict:
    return {
        "event_id": row.event_id,
        "event_type": row.event_type,
        "schema_version": row.schema_version,
        "org_id": row.org_id,
        "domain_object_type": row.domain_object_type,
        "domain_object_id": row.domain_object_id,
        "occurred_at": _iso(row.occurred_at),
        "recorded_at": _iso(row.recorded_at),
        "recorded_date": row.recorded_at.date().isoformat(),
        "source": row.source,
        "actor_type": row.actor_type,
        "actor_id": row.actor_id,
        "correlation_id": row.correlation_id,
        "payload": row.payload,          # already-bounded JSON string
        "lineage": row.lineage,
    }


def _project_snapshot(row: models.RetrospectiveSnapshot) -> dict:
    return {
        "snapshot_id": row.snapshot_id,
        "snapshot_type": row.snapshot_type,
        "schema_version": row.schema_version,
        "org_id": row.org_id,
        "subject_type": row.subject_type,
        "subject_id": row.subject_id,
        "valid_at": _iso(row.valid_at),
        "recorded_at": _iso(row.recorded_at),
        "recorded_date": row.recorded_at.date().isoformat(),
        "payload": row.payload,
        "lineage": row.lineage,
    }


def _checksum(rows: list[dict], id_field: str) -> str:
    """Deterministic checksum over rows sorted by stable id (order-independent)."""
    canonical = json.dumps(
        sorted(rows, key=lambda r: r[id_field]), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _partition_range(rows: list[dict]) -> Optional[tuple[str, str]]:
    if not rows:
        return None
    dates = [r["recorded_date"] for r in rows]
    return (min(dates), max(dates))


# ── Warehouse configuration (export stays optional) ─────────────────────────

def warehouse_configured() -> bool:
    """True only when a warehouse sink is configured. Default OFF."""
    return bool(os.environ.get("UKIP_WAREHOUSE_DATASET", "").strip())


def export_readiness() -> dict:
    """Readiness status for the warehouse export capability."""
    configured = warehouse_configured()
    return {
        "status": "configured" if configured else "not_configured",
        "dataset": os.environ.get("UKIP_WAREHOUSE_DATASET") or None,
    }


# ── 5.3 / 5.4 Idempotent export jobs ────────────────────────────────────────

def _scoped(query, model, org_scope: Optional[int]):
    return query.filter(
        model.org_id.is_(None) if org_scope is None else model.org_id == org_scope
    )


def export_events(
    db: Session,
    *,
    org_scope: Optional[int],
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    dataset_version: str = "v1",
) -> ExportResult:
    """Export historical events for a tenant scope and window (task 5.3)."""
    return _run_export(
        db,
        model=models.RetrospectiveEvent,
        project=_project_event,
        id_field="event_id",
        dataset_name="retrospective_events",
        org_scope=org_scope,
        since=since,
        until=until,
        dataset_version=dataset_version,
        time_col=models.RetrospectiveEvent.recorded_at,
    )


def export_snapshots(
    db: Session,
    *,
    org_scope: Optional[int],
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    dataset_version: str = "v1",
) -> ExportResult:
    """Export snapshots / analytical marts for a tenant scope and window (task 5.4)."""
    return _run_export(
        db,
        model=models.RetrospectiveSnapshot,
        project=_project_snapshot,
        id_field="snapshot_id",
        dataset_name="retrospective_snapshots",
        org_scope=org_scope,
        since=since,
        until=until,
        dataset_version=dataset_version,
        time_col=models.RetrospectiveSnapshot.recorded_at,
    )


def _run_export(
    db, *, model, project, id_field, dataset_name, org_scope, since, until,
    dataset_version, time_col,
) -> ExportResult:
    started = datetime.now().replace(microsecond=0)
    q = _scoped(db.query(model), model, org_scope)
    if since is not None:
        q = q.filter(time_col >= since)
    if until is not None:
        q = q.filter(time_col <= until)
    # Deterministic ordering by stable id → idempotent re-runs.
    rows = [project(r) for r in q.order_by(model.id.asc()).all()]
    # Dedup by stable id (defensive; ids are unique).
    seen: dict[str, dict] = {r[id_field]: r for r in rows}
    rows = [seen[k] for k in sorted(seen)]

    finished = datetime.now().replace(microsecond=0)
    source_query = (
        f"{model.__tablename__} WHERE org_scope="
        f"{'platform' if org_scope is None else org_scope}"
    )
    manifest = ExportManifest(
        export_id=uuid.uuid4().hex,
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        schema_version=1,
        org_scope=org_scope,
        started_at=started,
        finished_at=finished,
        row_counts=len(rows),
        partition_range=_partition_range(rows),
        source_query=source_query,
        checksum=_checksum(rows, id_field),
        status="completed" if rows else "empty",
    )
    return ExportResult(manifest=manifest, rows=rows)


# ── 5.5 Export validation ───────────────────────────────────────────────────

@dataclass(frozen=True)
class ValidationReport:
    ok: bool
    row_count_ok: bool
    tenant_ok: bool
    schema_ok: bool
    errors: list[str] = field(default_factory=list)


def validate_export(
    result: ExportResult, schema: tuple[Column, ...], *, org_scope: Optional[int]
) -> ValidationReport:
    """Validate an export: row counts, schema drift, and tenant isolation (5.5)."""
    errors: list[str] = []

    row_count_ok = result.manifest.row_counts == len(result.rows)
    if not row_count_ok:
        errors.append(
            f"row_count mismatch: manifest={result.manifest.row_counts} actual={len(result.rows)}"
        )

    required = {c.name for c in schema if c.mode == "REQUIRED"}
    allowed = {c.name for c in schema}
    schema_ok = True
    for r in result.rows:
        missing = required - r.keys()
        extra = r.keys() - allowed
        if missing or extra:
            schema_ok = False
            errors.append(f"schema drift: missing={sorted(missing)} extra={sorted(extra)}")
            break

    tenant_ok = True
    if org_scope is not None:
        offenders = [r for r in result.rows if r.get("org_id") != org_scope]
        if offenders:
            tenant_ok = False
            errors.append(f"tenant isolation: {len(offenders)} row(s) not in org_scope {org_scope}")

    return ValidationReport(
        ok=row_count_ok and tenant_ok and schema_ok,
        row_count_ok=row_count_ok, tenant_ok=tenant_ok, schema_ok=schema_ok,
        errors=errors,
    )
