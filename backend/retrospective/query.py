"""Read-only retrospective query service (Phase 4).

Reconstructs point-in-time state, compares current-vs-prior, and derives bounded
time-series / cohort marts from the append-only events and snapshots. Never
writes to operational OR retrospective tables (read-only by contract, ADR-006).

Null / provenance semantics (task 4.5, spec "unknown differs from unavailable"):
- **missing_history** — no snapshot exists at/before the requested time. The
  caller must NOT fall back to current operational state.
- **unavailable** — a snapshot exists but the field is absent from its payload
  (never captured at that time).
- **unknown** — the field is present in the payload but explicitly null.
- **present** — the field is present with a concrete value.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from .. import models


# ── Value provenance (task 4.5) ─────────────────────────────────────────────

VALUE_PRESENT = "present"
VALUE_UNKNOWN = "unknown"
VALUE_UNAVAILABLE = "unavailable"


def explain_value(payload: dict, field_name: str) -> str:
    """Classify a field's provenance within a snapshot payload."""
    if field_name not in payload:
        return VALUE_UNAVAILABLE
    return VALUE_UNKNOWN if payload[field_name] is None else VALUE_PRESENT


# ── Point-in-time lookup (task 4.1) ─────────────────────────────────────────

@dataclass(frozen=True)
class SnapshotResult:
    """Typed point-in-time lookup result — never silently current state."""

    found: bool
    snapshot_type: str
    subject_id: str
    valid_at: Optional[datetime] = None
    recorded_at: Optional[datetime] = None
    payload: Optional[dict] = None
    missing_reason: Optional[str] = None  # "no_history" when found is False


def _scoped_snapshots(db: Session, org_id: Optional[int], snapshot_type: str, subject_id: str):
    q = db.query(models.RetrospectiveSnapshot).filter(
        models.RetrospectiveSnapshot.snapshot_type == snapshot_type,
        models.RetrospectiveSnapshot.subject_id == subject_id,
    )
    return q.filter(
        models.RetrospectiveSnapshot.org_id.is_(None)
        if org_id is None
        else models.RetrospectiveSnapshot.org_id == org_id
    )


def point_in_time_snapshot(
    db: Session,
    *,
    org_id: Optional[int],
    snapshot_type: str,
    subject_id: str,
    as_of: datetime,
) -> SnapshotResult:
    """Return the latest snapshot valid at or before ``as_of``.

    Returns a typed missing-history result (``found=False``,
    ``missing_reason="no_history"``) when nothing exists at/before ``as_of`` —
    the caller must not fall back to current operational state.
    """
    row = (
        _scoped_snapshots(db, org_id, snapshot_type, subject_id)
        .filter(models.RetrospectiveSnapshot.valid_at <= as_of)
        .order_by(models.RetrospectiveSnapshot.valid_at.desc())
        .first()
    )
    if row is None:
        return SnapshotResult(
            found=False, snapshot_type=snapshot_type, subject_id=subject_id,
            missing_reason="no_history",
        )
    return SnapshotResult(
        found=True, snapshot_type=snapshot_type, subject_id=subject_id,
        valid_at=row.valid_at, recorded_at=row.recorded_at,
        payload=json.loads(row.payload),
    )


# ── Current-vs-prior comparison (task 4.2) ──────────────────────────────────

@dataclass(frozen=True)
class ComparisonResult:
    found_prior: bool
    subject_id: str
    snapshot_type: str
    as_of: datetime
    current: dict = field(default_factory=dict)
    prior: Optional[dict] = None
    prior_valid_at: Optional[datetime] = None
    changed_fields: dict = field(default_factory=dict)  # field -> {prior, current, provenance}
    missing_reason: Optional[str] = None


def compare_to_snapshot(
    db: Session,
    *,
    org_id: Optional[int],
    snapshot_type: str,
    subject_id: str,
    as_of: datetime,
    current: dict,
) -> ComparisonResult:
    """Compare the caller-supplied current state with the prior snapshot at ``as_of``.

    Read-only: the current values are supplied by the caller (derived from
    operational state elsewhere); this service never reads or writes operational
    tables. ``changed_fields`` maps each differing field to its prior/current
    values and the prior value's provenance.
    """
    prior_result = point_in_time_snapshot(
        db, org_id=org_id, snapshot_type=snapshot_type, subject_id=subject_id, as_of=as_of
    )
    if not prior_result.found:
        return ComparisonResult(
            found_prior=False, subject_id=subject_id, snapshot_type=snapshot_type,
            as_of=as_of, current=current, missing_reason=prior_result.missing_reason,
        )
    prior = prior_result.payload or {}
    changed: dict = {}
    for key in sorted(set(current) | set(prior)):
        cur_val = current.get(key)
        prior_val = prior.get(key)
        if cur_val != prior_val:
            changed[key] = {
                "prior": prior_val,
                "current": cur_val,
                "prior_provenance": explain_value(prior, key),
            }
    return ComparisonResult(
        found_prior=True, subject_id=subject_id, snapshot_type=snapshot_type,
        as_of=as_of, current=current, prior=prior,
        prior_valid_at=prior_result.valid_at, changed_fields=changed,
    )


# ── Time-series & cohorts (task 4.3) ────────────────────────────────────────

def snapshot_time_series(
    db: Session,
    *,
    org_id: Optional[int],
    snapshot_type: str,
    subject_id: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    """Ordered snapshot payloads for a subject, oldest first (bounded by window)."""
    q = _scoped_snapshots(db, org_id, snapshot_type, subject_id)
    if since is not None:
        q = q.filter(models.RetrospectiveSnapshot.valid_at >= since)
    if until is not None:
        q = q.filter(models.RetrospectiveSnapshot.valid_at <= until)
    rows = q.order_by(models.RetrospectiveSnapshot.valid_at.asc()).all()
    return [
        {"valid_at": r.valid_at, "payload": json.loads(r.payload)} for r in rows
    ]


def cohort_by_first_event(
    db: Session,
    *,
    org_id: Optional[int],
    event_type: str,
    since: datetime,
    until: datetime,
) -> list[str]:
    """Subjects whose FIRST event of ``event_type`` occurred within [since, until].

    Membership is based on historical event timestamps (``occurred_at``), so later
    changes to current operational state never change cohort membership.
    """
    q = db.query(models.RetrospectiveEvent).filter(
        models.RetrospectiveEvent.event_type == event_type
    )
    q = q.filter(
        models.RetrospectiveEvent.org_id.is_(None)
        if org_id is None
        else models.RetrospectiveEvent.org_id == org_id
    )
    first_seen: dict[str, datetime] = {}
    for ev in q.order_by(models.RetrospectiveEvent.occurred_at.asc()).all():
        first_seen.setdefault(ev.domain_object_id, ev.occurred_at)
    return sorted(
        subj for subj, first in first_seen.items() if since <= first <= until
    )
