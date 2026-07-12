"""Point-in-time snapshot materialization for the retrospective layer (task 3.4).

Derives current state directly from operational tables and persists it as
append-only snapshots via the Phase 2 writer. Snapshots are reproducible: they
read operational state read-only and never mutate it.

Materialization is *deliberate* (invoked by a scheduler or admin action), so the
individual ``materialize_*`` functions are always callable. The ``materialize_all``
orchestrator is flag-gated (``UKIP_RETRO_EVENTS``) so a wired scheduler is a
no-op until the layer is deliberately enabled.

Idempotency: each snapshot is keyed by subject + the ``valid_at`` calendar day,
so re-running the same day dedups; a later day is a new, expected snapshot.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from . import writer
from .emit import retro_events_enabled

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now().replace(microsecond=0)


def _day_key(subject_id: str, valid_at: datetime) -> str:
    return f"{subject_id}:{valid_at.date().isoformat()}"


def _safe_snapshot(db: Session, **kwargs) -> bool:
    """Write one snapshot, best-effort. Returns True on success."""
    try:
        writer.record_snapshot(db, **kwargs)
        return True
    except Exception:  # noqa: BLE001 — one bad subject must not abort the batch
        logger.warning(
            "retrospective snapshot failed for %s/%s; continuing",
            kwargs.get("snapshot_type"),
            kwargs.get("subject_id"),
            exc_info=True,
        )
        return False


def materialize_journal_metric_snapshots(
    db: Session, org_id: Optional[int], valid_at: Optional[datetime] = None
) -> int:
    """One snapshot per journal that currently has a metric. Returns count written."""
    valid_at = valid_at or _now()
    rows = (
        db.query(models.JournalMetric)
        .filter(models.JournalMetric.org_id == org_id)
        .filter(models.JournalMetric.two_yr_mean_citedness.isnot(None))
        .all()
    )
    written = 0
    for r in rows:
        ok = _safe_snapshot(
            db,
            snapshot_type="journal_metric",
            org_id=org_id,
            subject_type="journal",
            subject_id=r.issn_l,
            valid_at=valid_at,
            idempotency_key=_day_key(r.issn_l, valid_at),
            payload={
                "nif": r.normalized_impact_factor,
                "nif_bayes": r.nif_bayes,
                "two_yr_mean_citedness": r.two_yr_mean_citedness,
                "works_2yr": r.works_2yr,
                "nif_field": r.nif_field,
            },
            lineage={"source_id": r.source_id} if r.source_id else None,
        )
        written += int(ok)
    return written


def materialize_enrichment_coverage_snapshot(
    db: Session, org_id: Optional[int], valid_at: Optional[datetime] = None
) -> int:
    """One aggregate coverage snapshot for the org. Returns count written (0/1)."""
    valid_at = valid_at or _now()
    counts = dict(
        db.query(models.RawEntity.enrichment_status, func.count(models.RawEntity.id))
        .filter(models.RawEntity.org_id == org_id)
        .group_by(models.RawEntity.enrichment_status)
        .all()
    )
    total = sum(counts.values())
    completed = counts.get("completed", 0)
    subject = str(org_id) if org_id is not None else "platform"
    ok = _safe_snapshot(
        db,
        snapshot_type="enrichment_coverage",
        org_id=org_id,
        subject_type="org",
        subject_id=subject,
        valid_at=valid_at,
        idempotency_key=_day_key(subject, valid_at),
        payload={
            "total": total,
            "completed": completed,
            "failed": counts.get("failed", 0),
            "pending": counts.get("pending", 0),
            "completed_pct": round(completed / total * 100, 2) if total else 0.0,
        },
    )
    return int(ok)


def materialize_authority_readiness_snapshot(
    db: Session, org_id: Optional[int], valid_at: Optional[datetime] = None
) -> int:
    """One aggregate authority-readiness snapshot for the org. Returns 0/1."""
    valid_at = valid_at or _now()
    counts = dict(
        db.query(models.AuthorityRecord.status, func.count(models.AuthorityRecord.id))
        .filter(models.AuthorityRecord.org_id == org_id)
        .group_by(models.AuthorityRecord.status)
        .all()
    )
    total = sum(counts.values())
    confirmed = counts.get("confirmed", 0)
    subject = str(org_id) if org_id is not None else "platform"
    ok = _safe_snapshot(
        db,
        snapshot_type="authority_readiness",
        org_id=org_id,
        subject_type="org",
        subject_id=subject,
        valid_at=valid_at,
        idempotency_key=_day_key(subject, valid_at),
        payload={
            "total": total,
            "pending": counts.get("pending", 0),
            "confirmed": confirmed,
            "rejected": counts.get("rejected", 0),
            "confirmed_pct": round(confirmed / total * 100, 2) if total else 0.0,
        },
    )
    return int(ok)


def materialize_all(
    db: Session, org_id: Optional[int], valid_at: Optional[datetime] = None
) -> dict[str, int]:
    """Flag-gated orchestrator: materialize the initial snapshot families.

    Returns per-family counts. A no-op ``{}`` when the layer is disabled, so a
    wired scheduler does nothing until ``UKIP_RETRO_EVENTS`` is enabled.
    """
    if not retro_events_enabled():
        return {}
    valid_at = valid_at or _now()
    result = {
        "journal_metric": materialize_journal_metric_snapshots(db, org_id, valid_at),
        "enrichment_coverage": materialize_enrichment_coverage_snapshot(db, org_id, valid_at),
        "authority_readiness": materialize_authority_readiness_snapshot(db, org_id, valid_at),
    }
    db.flush()
    return result
