"""
Enrichment Scheduler Service
=============================
Background service that periodically detects stale domains and re-queues
eligible entities (``enrichment_status IN ('none', 'failed')``) for enrichment.

Architecture decisions:
- Pure asyncio loop (no APScheduler) — matches enrichment_worker.py pattern
- Per-domain policy stored in DB (DomainEnrichmentPolicy)
- Direct DB writes for re-queue (no HTTP layer)
- Audit log via EnrichmentSchedulerRun table

Usage (from main.py lifespan)::

    from backend.services.enrichment_scheduler import EnrichmentScheduler

    _enrichment_scheduler = EnrichmentScheduler()
    asyncio.create_task(_enrichment_scheduler.start_loop())
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend import models
from backend.services.entity_query import count_total, count_enriched

logger = logging.getLogger(__name__)

# Module-level singleton — shared between main.py (startup) and the API router
scheduler: "EnrichmentScheduler"  # forward ref; assigned after class definition

# Default policy values — used when no DomainEnrichmentPolicy row exists for a domain
_DEFAULT_MIN_ENRICHMENT_PCT = 80.0
_DEFAULT_MAX_BUDGET_PER_RUN = 100
_DEFAULT_STALENESS_THRESHOLD_DAYS = 30
_DEFAULT_INTERVAL_SECONDS = 60


class EnrichmentScheduler:
    """
    Stateful scheduler that wakes on a configurable interval, checks all
    enabled domain policies, and re-queues stale entities.
    """

    def __init__(self, interval_seconds: int = _DEFAULT_INTERVAL_SECONDS) -> None:
        self.interval_seconds: int = interval_seconds
        self.last_run_at: Optional[datetime] = None
        self.next_run_at: Optional[datetime] = None
        self.running: bool = False

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    def _check_domain(
        self,
        db: Session,
        domain_id: str,
        policy: models.DomainEnrichmentPolicy,
    ) -> Dict[str, Any]:
        """
        Compute a staleness report for a single domain.

        Returns a dict with:
            domain_id, total_entities, enriched_entities, stale_entities,
            current_enrichment_pct, is_stale, policy
        """
        scope = f"domain:{domain_id}"

        total = count_total(db, scope)
        enriched = count_enriched(db, scope)

        if total == 0:
            return {
                "domain_id": domain_id,
                "total_entities": 0,
                "enriched_entities": 0,
                "stale_entities": 0,
                "current_enrichment_pct": 0.0,
                "is_stale": False,
                "policy": policy,
            }

        current_pct = (enriched / total) * 100.0

        # Count stale entities (none + failed)
        from sqlalchemy import func as sqla_func
        stale_count = (
            db.query(sqla_func.count(models.RawEntity.id))
            .filter(
                models.RawEntity.source != "graph_materializer",
                models.RawEntity.enrichment_status.in_(["none", "failed"]),
            )
            .scalar()
            or 0
        )

        # Apply domain filter for stale count
        from backend.domain_scope import parse_scope, resolve_domain_filter
        parsed = parse_scope(scope)
        domain_filt = resolve_domain_filter(parsed, models.RawEntity)
        if domain_filt is not None:
            stale_count = (
                db.query(sqla_func.count(models.RawEntity.id))
                .filter(
                    models.RawEntity.source != "graph_materializer",
                    models.RawEntity.enrichment_status.in_(["none", "failed"]),
                    domain_filt,
                )
                .scalar()
                or 0
            )

        min_pct = policy.min_enrichment_pct if policy else _DEFAULT_MIN_ENRICHMENT_PCT
        is_stale = current_pct < min_pct

        return {
            "domain_id": domain_id,
            "total_entities": total,
            "enriched_entities": enriched,
            "stale_entities": stale_count,
            "current_enrichment_pct": round(current_pct, 2),
            "is_stale": is_stale,
            "policy": policy,
        }

    def _requeue_domain(
        self,
        db: Session,
        domain_id: str,
        policy: models.DomainEnrichmentPolicy,
    ) -> int:
        """
        Set up to ``max_budget_per_run`` entities with status 'none' or 'failed'
        to 'pending' for the given domain.

        Returns the number of entities actually queued.
        """
        budget = policy.max_budget_per_run if policy else _DEFAULT_MAX_BUDGET_PER_RUN

        # Find eligible entity IDs, bounded by budget
        from backend.domain_scope import parse_scope, resolve_domain_filter
        scope = f"domain:{domain_id}"
        parsed = parse_scope(scope)
        domain_filt = resolve_domain_filter(parsed, models.RawEntity)

        q = (
            db.query(models.RawEntity.id)
            .filter(
                models.RawEntity.source != "graph_materializer",
                models.RawEntity.enrichment_status.in_(["none", "failed"]),
            )
        )
        if domain_filt is not None:
            q = q.filter(domain_filt)

        eligible_ids = [row[0] for row in q.limit(budget).all()]
        if not eligible_ids:
            return 0

        stmt = (
            update(models.RawEntity)
            .where(
                models.RawEntity.id.in_(eligible_ids),
                models.RawEntity.enrichment_status.in_(["none", "failed"]),
            )
            .values(enrichment_status="pending")
            .execution_options(synchronize_session="fetch")
        )
        result = db.execute(stmt)
        db.commit()

        queued_count = result.rowcount or len(eligible_ids)
        return queued_count

    def _record_run(
        self,
        db: Session,
        domain_id: str,
        triggered_by: str,
        queued_count: int,
        notes: Optional[str] = None,
    ) -> models.EnrichmentSchedulerRun:
        """Insert an EnrichmentSchedulerRun row and return it."""
        now = datetime.now(timezone.utc)
        run = models.EnrichmentSchedulerRun(
            domain_id=domain_id,
            triggered_by=triggered_by,
            queued_count=queued_count,
            started_at=now,
            finished_at=now,
            notes=notes,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    # ------------------------------------------------------------------
    # Main scheduler loop
    # ------------------------------------------------------------------

    def run_once(self, db: Session) -> Dict[str, Any]:
        """
        Single scheduler tick: iterate all enabled DomainEnrichmentPolicy rows,
        check staleness, re-queue stale domains, record runs.

        Returns a summary dict with counts for logging.
        """
        self.last_run_at = datetime.now(timezone.utc)

        policies: List[models.DomainEnrichmentPolicy] = (
            db.query(models.DomainEnrichmentPolicy)
            .filter(models.DomainEnrichmentPolicy.enabled == True)  # noqa: E712
            .all()
        )

        total_queued = 0
        domains_checked = 0
        domains_stale = 0

        for policy in policies:
            domain_id = policy.domain_id
            try:
                report = self._check_domain(db, domain_id, policy)
                domains_checked += 1

                if report["total_entities"] == 0:
                    logger.debug(
                        "Scheduler: domain '%s' has 0 entities — skipping", domain_id
                    )
                    continue

                if report["is_stale"]:
                    domains_stale += 1
                    queued = self._requeue_domain(db, domain_id, policy)
                    total_queued += queued
                    self._record_run(
                        db,
                        domain_id=domain_id,
                        triggered_by="scheduler",
                        queued_count=queued,
                        notes=(
                            f"Enrichment {report['current_enrichment_pct']:.1f}% "
                            f"< threshold {policy.min_enrichment_pct}%"
                        ),
                    )
                    logger.info(
                        "Scheduler: domain '%s' is stale (%.1f%% < %.1f%%) — queued %d entities",
                        domain_id,
                        report["current_enrichment_pct"],
                        policy.min_enrichment_pct,
                        queued,
                    )
                else:
                    logger.debug(
                        "Scheduler: domain '%s' is healthy (%.1f%% >= %.1f%%)",
                        domain_id,
                        report["current_enrichment_pct"],
                        policy.min_enrichment_pct,
                    )

            except Exception:
                logger.exception(
                    "Scheduler: error processing domain '%s'", domain_id
                )

        logger.info(
            "Scheduler run complete — %d domains checked, %d stale, %d entities queued",
            domains_checked,
            domains_stale,
            total_queued,
        )
        return {
            "domains_checked": domains_checked,
            "domains_stale": domains_stale,
            "total_queued": total_queued,
        }

    async def start_loop(self) -> None:
        """
        Async loop: sleep for interval_seconds then call run_once.
        Matches the pattern used in enrichment_worker.py.
        """
        from backend import database

        logger.info(
            "Enrichment scheduler started (interval=%ds)", self.interval_seconds
        )
        self.running = True

        # Initial delay to let the server finish booting
        await asyncio.sleep(10)

        while True:
            self.next_run_at = datetime.now(timezone.utc)
            try:
                with database.SessionLocal() as db:
                    self.run_once(db)
            except Exception:
                logger.exception("Enrichment scheduler loop error")

            self.last_run_at = datetime.now(timezone.utc)
            # Schedule next run
            next_ts = datetime.now(timezone.utc).timestamp() + self.interval_seconds
            self.next_run_at = datetime.fromtimestamp(next_ts, tz=timezone.utc)

            await asyncio.sleep(self.interval_seconds)


# Singleton — instantiated once at import time
scheduler = EnrichmentScheduler()
