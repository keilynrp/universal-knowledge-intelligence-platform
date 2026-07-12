"""Observability metrics for the retrospective layer (task 7.5).

Exposes event write volume, snapshot freshness, data recency (export-lag proxy),
and a best-effort failed-emission counter. All reads are tenant-scoped and
read-only.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models

# Process-local counter of non-fatal emission failures (see emit.py). Best-effort
# and per-process — a durable ledger would be needed for cross-process totals.
_lock = threading.Lock()
_failed_emissions = 0


def record_failed_emission() -> None:
    global _failed_emissions
    with _lock:
        _failed_emissions += 1


def failed_emission_count() -> int:
    return _failed_emissions


def reset_failed_emissions() -> None:
    """Test hook — reset the process-local counter."""
    global _failed_emissions
    with _lock:
        _failed_emissions = 0


def _scope(query, model, org_id: Optional[int]):
    return query.filter(
        model.org_id.is_(None) if org_id is None else model.org_id == org_id
    )


def _age_seconds(ts: Optional[datetime], now: datetime) -> Optional[float]:
    return (now - ts).total_seconds() if ts is not None else None


def retrospective_metrics(db: Session, org_id: Optional[int]) -> dict:
    """Return observability metrics for the retrospective layer, tenant-scoped."""
    now = datetime.now().replace(microsecond=0)
    E, S = models.RetrospectiveEvent, models.RetrospectiveSnapshot

    # ── Event write volume ──────────────────────────────────────────────
    by_type = dict(
        _scope(db.query(E.event_type, func.count(E.id)), E, org_id)
        .group_by(E.event_type)
        .all()
    )
    latest_event = _scope(db.query(func.max(E.recorded_at)), E, org_id).scalar()

    # ── Snapshot freshness (per type) ───────────────────────────────────
    snap_rows = (
        _scope(
            db.query(S.snapshot_type, func.count(S.id), func.max(S.valid_at), func.max(S.recorded_at)),
            S, org_id,
        )
        .group_by(S.snapshot_type)
        .all()
    )
    snapshots: dict[str, dict] = {}
    for stype, count, latest_valid, latest_recorded in snap_rows:
        snapshots[stype] = {
            "count": count,
            "latest_valid_at": latest_valid,
            "latest_recorded_at": latest_recorded,
            "freshness_age_seconds": _age_seconds(latest_recorded, now),
        }

    return {
        "as_of": now,
        "events": {
            "total": sum(by_type.values()),
            "by_type": by_type,
            "latest_recorded_at": latest_event,
            "data_recency_seconds": _age_seconds(latest_event, now),  # export-lag proxy
        },
        "snapshots": {
            "total": sum(s["count"] for s in snapshots.values()),
            "by_type": snapshots,
        },
        "failed_emissions": failed_emission_count(),
    }
