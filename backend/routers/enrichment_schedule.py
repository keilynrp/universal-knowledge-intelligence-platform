"""
Enrichment Schedule API Router
================================
Endpoints for querying and controlling the enrichment scheduler.

  GET  /enrichment/schedule                         — global scheduler state
  GET  /enrichment/schedule/{domain_id}             — per-domain staleness report
  GET  /enrichment/schedule/{domain_id}/runs        — run history
  POST /enrichment/schedule/{domain_id}/trigger     — manual trigger (admin+)
  PUT  /enrichment/schedule/{domain_id}/policy      — upsert policy (admin+)
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.schema_registry import SchemaRegistry
from backend.schemas import (
    DomainEnrichmentPolicySchema,
    DomainEnrichmentPolicyUpdate,
    DomainStalenessReport,
    EnrichmentSchedulerRunSchema,
    SchedulerStateResponse,
)
from backend.services.enrichment_scheduler import scheduler as _scheduler

logger = logging.getLogger(__name__)
router = APIRouter(tags=["enrichment-schedule"])
_registry = SchemaRegistry()

_DEFAULT_MIN_ENRICHMENT_PCT = 80.0
_DEFAULT_MAX_BUDGET_PER_RUN = 100
_DEFAULT_STALENESS_THRESHOLD_DAYS = 30


def _get_or_default_policy(
    db: Session, domain_id: str
) -> models.DomainEnrichmentPolicy:
    """Return the policy row or a transient default object if none exists."""
    policy = (
        db.query(models.DomainEnrichmentPolicy)
        .filter(models.DomainEnrichmentPolicy.domain_id == domain_id)
        .first()
    )
    if policy is None:
        # Return a transient (unsaved) default policy
        policy = models.DomainEnrichmentPolicy(
            domain_id=domain_id,
            enabled=True,
            min_enrichment_pct=_DEFAULT_MIN_ENRICHMENT_PCT,
            max_budget_per_run=_DEFAULT_MAX_BUDGET_PER_RUN,
            staleness_threshold_days=_DEFAULT_STALENESS_THRESHOLD_DAYS,
        )
    return policy


def _domain_exists(domain_id: str) -> bool:
    """Return True if the domain is known to the schema registry."""
    try:
        domains = _registry.list_domains()
        return any(d.get("id") == domain_id for d in domains)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# GET /enrichment/schedule
# ---------------------------------------------------------------------------

@router.get("/enrichment/schedule", response_model=SchedulerStateResponse)
def get_scheduler_state(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> SchedulerStateResponse:
    """Return the global enrichment scheduler state."""
    domains_monitored: int = (
        db.query(models.DomainEnrichmentPolicy)
        .filter(models.DomainEnrichmentPolicy.enabled == True)  # noqa: E712
        .count()
    )

    # Sum queued_count from the most recent scheduler run per domain
    from sqlalchemy import func as sqla_func

    # Subquery: latest run id per domain
    latest_run_subq = (
        db.query(
            models.EnrichmentSchedulerRun.domain_id,
            sqla_func.max(models.EnrichmentSchedulerRun.started_at).label("max_started"),
        )
        .group_by(models.EnrichmentSchedulerRun.domain_id)
        .subquery()
    )
    total_queued_last_run: int = (
        db.query(sqla_func.coalesce(sqla_func.sum(models.EnrichmentSchedulerRun.queued_count), 0))
        .join(
            latest_run_subq,
            (models.EnrichmentSchedulerRun.domain_id == latest_run_subq.c.domain_id)
            & (models.EnrichmentSchedulerRun.started_at == latest_run_subq.c.max_started),
        )
        .scalar()
        or 0
    )

    return SchedulerStateResponse(
        enabled=_scheduler.running,
        interval_seconds=_scheduler.interval_seconds,
        last_run_at=_scheduler.last_run_at,
        next_run_at=_scheduler.next_run_at,
        domains_monitored=domains_monitored,
        total_queued_last_run=int(total_queued_last_run),
    )


# ---------------------------------------------------------------------------
# GET /enrichment/schedule/{domain_id}
# ---------------------------------------------------------------------------

@router.get("/enrichment/schedule/{domain_id}", response_model=DomainStalenessReport)
def get_domain_staleness(
    domain_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> DomainStalenessReport:
    """Return the staleness report for a specific domain."""
    if not _domain_exists(domain_id):
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

    policy = _get_or_default_policy(db, domain_id)
    report = _scheduler._check_domain(db, domain_id, policy)

    # Latest run
    last_run = (
        db.query(models.EnrichmentSchedulerRun)
        .filter(models.EnrichmentSchedulerRun.domain_id == domain_id)
        .order_by(models.EnrichmentSchedulerRun.started_at.desc())
        .first()
    )

    # Only include policy in response if it is persisted (has an id)
    policy_schema: Optional[DomainEnrichmentPolicySchema] = None
    if policy.id is not None:
        policy_schema = DomainEnrichmentPolicySchema.model_validate(policy)

    return DomainStalenessReport(
        domain_id=domain_id,
        policy=policy_schema,
        current_enrichment_pct=report["current_enrichment_pct"],
        total_entities=report["total_entities"],
        enriched_entities=report["enriched_entities"],
        stale_entities=report["stale_entities"],
        last_run=EnrichmentSchedulerRunSchema.model_validate(last_run) if last_run else None,
        is_stale=report["is_stale"],
    )


# ---------------------------------------------------------------------------
# GET /enrichment/schedule/{domain_id}/runs
# ---------------------------------------------------------------------------

@router.get(
    "/enrichment/schedule/{domain_id}/runs",
    response_model=List[EnrichmentSchedulerRunSchema],
)
def get_domain_runs(
    domain_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> List[EnrichmentSchedulerRunSchema]:
    """Return the run history for a domain, newest first."""
    runs = (
        db.query(models.EnrichmentSchedulerRun)
        .filter(models.EnrichmentSchedulerRun.domain_id == domain_id)
        .order_by(models.EnrichmentSchedulerRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [EnrichmentSchedulerRunSchema.model_validate(r) for r in runs]


# ---------------------------------------------------------------------------
# POST /enrichment/schedule/{domain_id}/trigger
# ---------------------------------------------------------------------------

@router.post("/enrichment/schedule/{domain_id}/trigger")
def trigger_domain(
    domain_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Manually trigger the scheduler for one domain (admin+)."""
    if not _domain_exists(domain_id):
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

    policy = _get_or_default_policy(db, domain_id)
    queued_count = _scheduler._requeue_domain(db, domain_id, policy)
    run = _scheduler._record_run(
        db,
        domain_id=domain_id,
        triggered_by="manual",
        queued_count=queued_count,
        notes="Manual trigger via API",
    )

    return {
        "domain_id": domain_id,
        "queued_count": queued_count,
        "triggered_by": "manual",
        "run_id": run.id,
    }


# ---------------------------------------------------------------------------
# PUT /enrichment/schedule/{domain_id}/policy
# ---------------------------------------------------------------------------

@router.put(
    "/enrichment/schedule/{domain_id}/policy",
    response_model=DomainEnrichmentPolicySchema,
)
def upsert_policy(
    domain_id: str,
    payload: DomainEnrichmentPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Create or update the enrichment policy for a domain (admin+).

    Returns HTTP 201 on creation, 200 on update.
    """
    from fastapi import Response as FastAPIResponse
    from fastapi.responses import JSONResponse

    existing = (
        db.query(models.DomainEnrichmentPolicy)
        .filter(models.DomainEnrichmentPolicy.domain_id == domain_id)
        .first()
    )

    now = datetime.now(timezone.utc)

    if existing is None:
        # Create with defaults, then apply provided fields
        new_policy = models.DomainEnrichmentPolicy(
            domain_id=domain_id,
            enabled=payload.enabled if payload.enabled is not None else True,
            min_enrichment_pct=(
                payload.min_enrichment_pct
                if payload.min_enrichment_pct is not None
                else _DEFAULT_MIN_ENRICHMENT_PCT
            ),
            max_budget_per_run=(
                payload.max_budget_per_run
                if payload.max_budget_per_run is not None
                else _DEFAULT_MAX_BUDGET_PER_RUN
            ),
            staleness_threshold_days=(
                payload.staleness_threshold_days
                if payload.staleness_threshold_days is not None
                else _DEFAULT_STALENESS_THRESHOLD_DAYS
            ),
            created_at=now,
            updated_at=now,
        )
        db.add(new_policy)
        db.commit()
        db.refresh(new_policy)
        return JSONResponse(
            status_code=201,
            content=DomainEnrichmentPolicySchema.model_validate(new_policy).model_dump(mode="json"),
        )

    # Update existing
    if payload.enabled is not None:
        existing.enabled = payload.enabled
    if payload.min_enrichment_pct is not None:
        existing.min_enrichment_pct = payload.min_enrichment_pct
    if payload.max_budget_per_run is not None:
        existing.max_budget_per_run = payload.max_budget_per_run
    if payload.staleness_threshold_days is not None:
        existing.staleness_threshold_days = payload.staleness_threshold_days
    existing.updated_at = now

    db.commit()
    db.refresh(existing)
    return DomainEnrichmentPolicySchema.model_validate(existing)
