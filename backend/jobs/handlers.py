"""Durable-queue handlers for migrated domains (ADR-007, Phase 4).

Registered on import. Each handler is mode-aware: in ``shadow`` mode it records
that it *would* have run but performs NO external side effect (the in-process
path stayed authoritative); in ``queue`` mode it performs the real execution.
Handlers are idempotent — at-least-once delivery may run them more than once.

Imports of operational modules are lazy to avoid import cycles at load time.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from .. import models
from . import runtime
from .migration import JobMode

logger = logging.getLogger(__name__)


def _mode(job: models.BackgroundJob) -> str:
    if not job.payload:
        return JobMode.QUEUE
    try:
        return json.loads(job.payload).get("mode", JobMode.QUEUE)
    except (ValueError, TypeError):
        return JobMode.QUEUE


def _payload(job: models.BackgroundJob) -> dict:
    try:
        return json.loads(job.payload) if job.payload else {}
    except (ValueError, TypeError):
        return {}


def _shadow_noop(job: models.BackgroundJob, what: str) -> bool:
    """Return True (and log) when the job is a side-effect-free shadow run."""
    if _mode(job) == JobMode.SHADOW:
        logger.info("shadow job %s (%s): parity-only, no side effect", job.job_id, what)
        return True
    return False


def report_execute(db: Session, job: models.BackgroundJob) -> None:
    if _shadow_noop(job, "report"):
        return
    from backend.routers.scheduled_reports import _execute_report

    schedule_id = _payload(job).get("schedule_id")
    schedule = db.get(models.ScheduledReport, schedule_id)
    if schedule is None:
        logger.warning("report job %s: schedule %s not found", job.job_id, schedule_id)
        return
    _execute_report(schedule, db)


def import_execute(db: Session, job: models.BackgroundJob) -> None:
    if _shadow_noop(job, "import"):
        return
    from backend.routers.scheduled_imports import _execute_import

    schedule_id = _payload(job).get("schedule_id")
    schedule = db.get(models.ScheduledImport, schedule_id)
    if schedule is None:
        logger.warning("import job %s: schedule %s not found", job.job_id, schedule_id)
        return
    _execute_import(schedule, db)


def enrichment_execute(db: Session, job: models.BackgroundJob) -> None:
    if _shadow_noop(job, "enrichment"):
        return
    from backend import enrichment_worker

    entity_id = _payload(job).get("entity_id")
    entity = db.get(models.RawEntity, entity_id)
    if entity is None:
        logger.warning("enrichment job %s: entity %s not found", job.job_id, entity_id)
        return
    enrichment_worker.enrich_single_record(db, entity)


def register_all() -> None:
    """Register every migrated-domain handler. Idempotent."""
    runtime.register_handler("report.execute", report_execute)
    runtime.register_handler("import.execute", import_execute)
    runtime.register_handler("enrichment.execute", enrichment_execute)


register_all()
