"""Observability for the durable job runtime (ADR-007, task 3.3).

Bounded, tenant-safe metrics derived from the queue plus process-local worker
heartbeats, and a health assessment (queue age, expired leases, worker liveness).
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..models import utc_now_naive
from .states import JobStatus

# Alert thresholds (seconds). Operator-tunable defaults; see the runbook.
DEFAULT_QUEUE_AGE_SLO_SECONDS = 900        # 15 min oldest-queued age
DEFAULT_WORKER_STALE_SECONDS = 120         # heartbeat older than this = stale

# ── Process-local worker heartbeats ─────────────────────────────────────────
_lock = threading.Lock()
_heartbeats: dict[str, datetime] = {}


def heartbeat(worker_id: str, now: Optional[datetime] = None) -> None:
    with _lock:
        _heartbeats[worker_id] = now or utc_now_naive()


def live_workers(now: Optional[datetime] = None,
                 stale_seconds: int = DEFAULT_WORKER_STALE_SECONDS) -> list[str]:
    now = now or utc_now_naive()
    with _lock:
        return sorted(
            wid for wid, ts in _heartbeats.items()
            if (now - ts).total_seconds() <= stale_seconds
        )


def reset_heartbeats() -> None:
    """Test hook."""
    with _lock:
        _heartbeats.clear()


# ── Queue metrics ───────────────────────────────────────────────────────────

def _age_seconds(ts: Optional[datetime], now: datetime) -> Optional[float]:
    return (now - ts).total_seconds() if ts is not None else None


def job_metrics(db: Session, *, org_id: Optional[int] = None,
                now: Optional[datetime] = None) -> dict:
    """Queue depth, status counts, oldest-queued age by type, expired leases.

    ``org_id=None`` with no filter returns platform-wide aggregates; pass an
    org_id to scope to one tenant.
    """
    now = now or utc_now_naive()
    J = models.BackgroundJob
    q = db.query(J)
    scoped = org_id is not None
    if scoped:
        q = q.filter(J.org_id == org_id)

    by_status = dict(
        q.with_entities(J.status, func.count(J.id)).group_by(J.status).all()
    )

    # Oldest queued age per job type (queue-age SLO signal).
    type_rows = (
        q.filter(J.status == JobStatus.QUEUED)
        .with_entities(J.job_type, func.count(J.id), func.min(J.available_at))
        .group_by(J.job_type)
        .all()
    )
    by_type = {
        jtype: {
            "queued": count,
            "oldest_queued_age_seconds": _age_seconds(oldest, now),
        }
        for jtype, count, oldest in type_rows
    }
    oldest_overall = max(
        (v["oldest_queued_age_seconds"] or 0.0 for v in by_type.values()), default=0.0
    )

    expired_leases = (
        q.filter(J.status == JobStatus.RUNNING,
                 J.lease_expires_at.isnot(None),
                 J.lease_expires_at < now).count()
    )

    return {
        "as_of": now,
        "scope": org_id if scoped else "platform",
        "depth": {
            "queued": by_status.get(JobStatus.QUEUED, 0),
            "running": by_status.get(JobStatus.RUNNING, 0),
            "retry_wait": by_status.get(JobStatus.RETRY_WAIT, 0),
        },
        "counts_by_status": by_status,
        "by_type": by_type,
        "oldest_queued_age_seconds": oldest_overall,
        "expired_leases": expired_leases,
    }


def health(db: Session, *, now: Optional[datetime] = None,
           queue_age_slo_seconds: int = DEFAULT_QUEUE_AGE_SLO_SECONDS) -> dict:
    """Health assessment for the job runtime. ``degraded`` when SLOs are breached."""
    now = now or utc_now_naive()
    m = job_metrics(db, now=now)
    workers = live_workers(now=now)
    reasons: list[str] = []
    if m["oldest_queued_age_seconds"] > queue_age_slo_seconds:
        reasons.append("queue_age_slo_breached")
    if m["expired_leases"] > 0:
        reasons.append("expired_leases_present")
    if not workers and m["depth"]["queued"] > 0:
        reasons.append("no_live_workers_with_backlog")
    return {
        "status": "degraded" if reasons else "ok",
        "reasons": reasons,
        "live_workers": len(workers),
        "queued": m["depth"]["queued"],
        "oldest_queued_age_seconds": m["oldest_queued_age_seconds"],
        "expired_leases": m["expired_leases"],
    }
