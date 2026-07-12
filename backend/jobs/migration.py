"""Flag-gated incremental migration to the durable queue (ADR-007, Phase 4).

Each in-process domain (reports, imports, enrichment) has a mode, default **off**,
so merging changes nothing in production until a mode is deliberately set:

- ``off``    — in-process path only (current behavior).
- ``shadow`` — in-process stays authoritative AND a durable job is enqueued for
  parity comparison; the shadow job never re-runs the external side effect.
- ``queue``  — the durable job is authoritative; the in-process path skips.

Cutover order per the rollout plan: reports → imports → enrichment. The actual
flip is an operational act (set the env var in prod), not a code change.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from . import service

logger = logging.getLogger(__name__)


class JobMode:
    OFF = "off"
    SHADOW = "shadow"
    QUEUE = "queue"


_VALID = {JobMode.OFF, JobMode.SHADOW, JobMode.QUEUE}


def job_mode(domain: str) -> str:
    """Mode for a domain from ``UKIP_JOBS_<DOMAIN>`` (default ``off``)."""
    raw = os.environ.get(f"UKIP_JOBS_{domain.upper()}", JobMode.OFF).strip().lower()
    return raw if raw in _VALID else JobMode.OFF


def should_run_inprocess(mode: str) -> bool:
    """In-process executes in off and shadow; skips in queue."""
    return mode in (JobMode.OFF, JobMode.SHADOW)


def should_enqueue(mode: str) -> bool:
    """A durable job is enqueued in shadow and queue; not in off."""
    return mode in (JobMode.SHADOW, JobMode.QUEUE)


def inprocess_schedulers_enabled() -> bool:
    """4.5 — in-process schedulers start unless explicitly disabled.

    Defaults ON so nothing changes until an operator sets
    ``UKIP_INPROCESS_SCHEDULERS=0`` after cutover.
    """
    return os.environ.get("UKIP_INPROCESS_SCHEDULERS", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def enqueue_occurrence(
    db: Session,
    *,
    domain: str,
    job_type: str,
    schedule_id: int,
    org_id: Optional[int],
    occurrence_at: datetime,
    mode: str,
    payload: Optional[dict[str, Any]] = None,
) -> Optional[object]:
    """Enqueue a durable job for one schedule occurrence, idempotently.

    The idempotency key is ``{domain}:{schedule_id}:{occurrence_at}`` so a due
    schedule scanned repeatedly enqueues a single job per occurrence. Returns the
    job, or None when the mode does not enqueue.
    """
    if not should_enqueue(mode):
        return None
    body = {"schedule_id": schedule_id, "mode": mode}
    if payload:
        body.update(payload)
    occ = occurrence_at.replace(microsecond=0).isoformat() if occurrence_at else "adhoc"
    return service.enqueue(
        db,
        job_type=job_type,
        org_id=org_id,
        idempotency_key=f"{domain}:{schedule_id}:{occ}",
        payload=body,
        correlation_id=f"{domain}:{schedule_id}",
    )


def dispatch_due(
    db: Session,
    *,
    domain: str,
    job_type: str,
    schedule: Any,
    execute: Callable[[Any, Session], Any],
) -> str:
    """Route a due schedule occurrence per the domain mode. Returns the mode used.

    ``off``/``shadow`` run ``execute`` in-process (authoritative); ``shadow``/
    ``queue`` also enqueue a durable job (best-effort — enqueue failure never
    blocks the in-process path). ``queue`` skips in-process execution.
    """
    mode = job_mode(domain)
    if should_enqueue(mode):
        try:
            enqueue_occurrence(
                db, domain=domain, job_type=job_type, schedule_id=schedule.id,
                org_id=getattr(schedule, "org_id", None),
                occurrence_at=getattr(schedule, "next_run_at", None), mode=mode,
            )
            db.commit()
        except Exception:  # noqa: BLE001 — migration enqueue is best-effort
            db.rollback()
            logger.exception("durable enqueue failed for %s schedule %s", domain, schedule.id)
    if should_run_inprocess(mode):
        execute(schedule, db)
    return mode
