"""Background worker that drains AuthorityResolveJob rows (Phase 1, Task 3).

Mirrors the enrichment worker pattern: poll for a pending job, atomically claim
it (UPDATE ... WHERE status='pending'), run the shared batch-resolution core,
and persist progress counters. Failures mark the job 'failed' with the error.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend import models
from backend.authority.batch_resolution import execute_batch_resolution
from backend.authority.resolver import resolve_all as _resolve_all
from backend.database import SessionLocal
from backend.tenant_access import persisted_org_id

logger = logging.getLogger(__name__)

_POLL_SECONDS = 3


def reset_stale_jobs(db: Session) -> int:
    """Reset jobs stuck in 'processing' (e.g. after a crash) back to 'pending'."""
    res = db.execute(
        update(models.AuthorityResolveJob)
        .where(models.AuthorityResolveJob.status == "processing")
        .values(status="pending")
    )
    db.commit()
    return res.rowcount or 0


def _claim_one(db: Session):
    """Atomically claim the oldest pending job. Returns the job or None."""
    job = (
        db.query(models.AuthorityResolveJob)
        .filter_by(status="pending")
        .order_by(models.AuthorityResolveJob.id)
        .first()
    )
    if not job:
        return None
    res = db.execute(
        update(models.AuthorityResolveJob)
        .where(
            models.AuthorityResolveJob.id == job.id,
            models.AuthorityResolveJob.status == "pending",
        )
        .values(status="processing")
    )
    db.commit()
    if res.rowcount != 1:
        return None
    db.refresh(job)
    return job


def _run_job(db: Session, job: models.AuthorityResolveJob) -> None:
    params = json.loads(job.params_json) if job.params_json else {}
    limit = int(params.get("limit", 100))
    skip_existing = bool(params.get("skip_existing", False))
    entity_type_filter = params.get("entity_type_filter") or None
    value_source = params.get("value_source") or None

    def _progress(processed: int, total: int, created: int) -> None:
        job.processed = processed
        job.total = total
        job.records_created = created
        db.add(job)
        db.commit()

    try:
        summary, _records = execute_batch_resolution(
            db,
            org_id=job.org_id,
            record_org_id=persisted_org_id(job.org_id),
            field=job.field_name,
            entity_type=job.entity_type,
            limit=limit,
            skip_existing=skip_existing,
            resolve_fn=_resolve_all,
            progress_cb=_progress,
            entity_type_filter=entity_type_filter,
            value_source=value_source,
        )
        db.commit()
        job.status = "done"
        job.total = summary["resolved_count"]
        job.processed = summary["resolved_count"]
        job.records_created = summary["records_created"]
        job.finished_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        logger.info(
            "Authority batch job %d done: %d records from %d values",
            job.id,
            summary["records_created"],
            summary["resolved_count"],
        )
    except Exception as exc:  # noqa: BLE001 — record failure, keep worker alive
        db.rollback()
        job.status = "failed"
        job.error = str(exc)[:2000]
        job.finished_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        logger.exception("Authority batch job %d failed", job.id)


async def run_batch_worker() -> None:
    """Poll loop: claim + run one pending job per iteration.

    ``_run_job`` is synchronous and can take minutes for large jobs (external
    HTTP per value), so it MUST run in a worker thread — running it inline
    would block the event loop, starve every request including ``/health``,
    and get the container killed by its healthcheck (observed in prod with a
    500-value auto-enqueued job). The DB session is only ever touched by that
    one thread at a time, so the sequential handoff is safe.
    """
    while True:
        try:
            db = SessionLocal()
            try:
                job = _claim_one(db)
                if job:
                    await asyncio.to_thread(_run_job, db, job)
            finally:
                db.close()
        except Exception:  # noqa: BLE001 — never let the loop die
            logger.exception("authority batch worker iteration failed")
        await asyncio.sleep(_POLL_SECONDS)
