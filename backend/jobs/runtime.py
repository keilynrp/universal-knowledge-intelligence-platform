"""Worker & scheduler runtime for the durable job queue (ADR-007, tasks 3.1-3.2).

- A handler registry maps ``job_type`` → idempotent callable.
- ``run_once`` claims and executes a single job (atomic, at-least-once).
- ``JobWorker`` polls with heartbeats and drains gracefully on stop.
- ``scheduler_tick`` advances retry-ready jobs and recovers abandoned leases.

Handlers MUST be idempotent: at-least-once delivery means a handler can run more
than once for the same job (crash before commit, lease expiry, replay).
"""
from __future__ import annotations

import logging
import time
from threading import Event
from typing import Callable, Optional

from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal
from . import metrics, service
from .states import JobStatus

logger = logging.getLogger(__name__)

# job_type -> handler(db, job) -> None
Handler = Callable[[Session, models.BackgroundJob], None]
_HANDLERS: dict[str, Handler] = {}


def register(job_type: str) -> Callable[[Handler], Handler]:
    """Decorator to register a handler for a job type."""
    def _wrap(fn: Handler) -> Handler:
        _HANDLERS[job_type] = fn
        return fn
    return _wrap


def register_handler(job_type: str, fn: Handler) -> None:
    _HANDLERS[job_type] = fn


def unregister(job_type: str) -> None:
    _HANDLERS.pop(job_type, None)


def get_handler(job_type: str) -> Optional[Handler]:
    return _HANDLERS.get(job_type)


# ── Single unit of work ─────────────────────────────────────────────────────

def run_once(db: Session, *, lease_owner: str, job_type: Optional[str] = None,
             lease_seconds: int = service._DEFAULT_LEASE_SECONDS) -> Optional[models.BackgroundJob]:
    """Claim and execute one job. Returns the job processed, or None if idle."""
    job = service.claim(db, lease_owner=lease_owner, job_type=job_type,
                        lease_seconds=lease_seconds)
    if job is None:
        return None

    handler = get_handler(job.job_type)
    if handler is None:
        service.fail(db, job, error_code="no_handler",
                     error_detail=f"no handler registered for {job.job_type}",
                     terminal=True)
        logger.error("job %s has no handler for type %s", job.job_id, job.job_type)
        return job

    try:
        handler(db, job)
    except Exception as exc:  # noqa: BLE001 — recorded as a typed job failure
        db.rollback()
        status = service.fail(db, job, error_code=type(exc).__name__,
                              error_detail=str(exc))
        logger.warning("job %s failed (%s): %s", job.job_id, status, exc)
        return job

    service.complete(db, job)
    return job


# ── Worker loop with graceful drain ─────────────────────────────────────────

class JobWorker:
    """Polls for jobs and drains gracefully when ``stop`` is set."""

    def __init__(self, worker_id: str, *, job_type: Optional[str] = None,
                 poll_seconds: float = 2.0,
                 lease_seconds: int = service._DEFAULT_LEASE_SECONDS,
                 session_factory: Callable[[], Session] = SessionLocal):
        self.worker_id = worker_id
        self.job_type = job_type
        self.poll_seconds = poll_seconds
        self.lease_seconds = lease_seconds
        self._session_factory = session_factory
        self.stop = Event()

    def request_stop(self) -> None:
        """Signal the loop to stop claiming new work and drain."""
        self.stop.set()

    def run(self) -> None:
        """Run until ``request_stop`` — finishes the in-flight job, claims no more."""
        logger.info("job worker %s starting (type=%s)", self.worker_id, self.job_type)
        while not self.stop.is_set():
            db = self._session_factory()
            try:
                metrics.heartbeat(self.worker_id)
                job = run_once(db, lease_owner=self.worker_id, job_type=self.job_type,
                               lease_seconds=self.lease_seconds)
            except Exception:  # noqa: BLE001 — loop must survive unexpected errors
                logger.exception("worker %s loop error", self.worker_id)
                job = None
            finally:
                db.close()
            if job is None and not self.stop.is_set():
                time.sleep(self.poll_seconds)
        logger.info("job worker %s drained and stopped", self.worker_id)


# ── Scheduler / dispatcher tick ─────────────────────────────────────────────

def scheduler_tick(db: Session) -> dict:
    """One dispatcher pass: promote due retries and recover abandoned leases."""
    promoted = service.promote_retry_ready(db)
    recovered = service.recover_abandoned_leases(db)
    return {"promoted_retries": promoted, "recovered_leases": recovered}


class JobScheduler:
    """Periodically runs ``scheduler_tick`` until stopped. Single instance only."""

    def __init__(self, *, interval_seconds: float = 5.0,
                 session_factory: Callable[[], Session] = SessionLocal):
        self.interval_seconds = interval_seconds
        self._session_factory = session_factory
        self.stop = Event()

    def request_stop(self) -> None:
        self.stop.set()

    def run(self) -> None:
        logger.info("job scheduler starting")
        while not self.stop.is_set():
            db = self._session_factory()
            try:
                result = scheduler_tick(db)
                if result["promoted_retries"] or result["recovered_leases"]:
                    logger.info("scheduler tick: %s", result)
            except Exception:  # noqa: BLE001
                logger.exception("scheduler tick error")
            finally:
                db.close()
            self.stop.wait(self.interval_seconds)
        logger.info("job scheduler stopped")
