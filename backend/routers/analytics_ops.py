"""
Lookups, ops, and specialized analytics endpoints (extracted from analytics.py).
  GET  /stats
  GET  /secondary-labels
  GET  /brands
  GET  /product-types
  GET  /classifications
  GET  /health
  GET  /ops/checks
  POST /ops/checks/run
  GET  /ops/enterprise-readiness
  GET  /ops/tenant-model
  POST /analytics/concepts/{domain_id}/materialize
  GET  /analytics/concepts/{domain_id}/tree
  GET  /analytics/concepts/{domain_id}/{concept_node_id}
  POST /analytics/epistemic/{domain_id}/classify
  GET  /analytics/epistemic/{domain_id}/distribution
  GET  /analytics/domain-health/compare
  GET  /analytics/domain-health/{domain_id}
"""
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from backend import models
from backend.schemas import EnrichmentStatus
from backend.analyzers.concept_hierarchy import (
    build_concept_tree,
    materialize_domain_concepts,
)
from backend.analyzers.domain_health import compute_health_metrics
from backend.analyzers.epistemic_classifier import classify_batch
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.enterprise_readiness import get_enterprise_readiness_report
from backend.logging_utils import current_log_format
from backend.ops_checks import dispatch_operational_alert_if_needed, run_operational_checks
from backend.routers.analytics import _validate_domain_id
from backend.services.analytics_service import AnalyticsService
from backend.telemetry import telemetry_status
from backend.tenant_access import resolve_request_org_id, scope_query_to_org
from backend.tenant_scoping import get_tenant_scoping_report

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])


# ── Global stats and lookup endpoints ────────────────────────────────────────

@router.get("/stats")
def get_stats(
    domain_id: str = Query(default="all", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    return AnalyticsService.get_stats(db, org_id=org_id, domain_id=domain_id)


def _get_secondary_label_counts(
    db: Session,
    org_id: int | None,
    limit: int,
) -> list[dict[str, int | str | None]]:
    labels = (
        scope_query_to_org(
            db.query(models.RawEntity.secondary_label, func.count(models.RawEntity.id).label("count")),
            models.RawEntity,
            org_id,
        )
        .filter(models.RawEntity.secondary_label != None)
        .group_by(models.RawEntity.secondary_label)
        .order_by(func.count(models.RawEntity.id).desc())
        .limit(limit)
        .all()
    )
    return [{"name": label[0], "count": label[1]} for label in labels]


@router.get("/secondary-labels")
def get_all_secondary_labels(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    return _get_secondary_label_counts(db, org_id, limit)


@router.get("/brands")
def get_all_brands(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Backward-compatible alias for secondary-label counts."""
    org_id = resolve_request_org_id(db, current_user)
    return _get_secondary_label_counts(db, org_id, limit)


@router.get("/product-types")
def get_all_entity_types(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    types = (
        scope_query_to_org(
            db.query(models.RawEntity.entity_type, func.count(models.RawEntity.id).label("count")),
            models.RawEntity,
            org_id,
        )
        .filter(models.RawEntity.entity_type != None)
        .group_by(models.RawEntity.entity_type)
        .order_by(func.count(models.RawEntity.id).desc())
        .limit(limit)
        .all()
    )
    return [{"name": t[0], "count": t[1]} for t in types]


@router.get("/classifications")
def get_all_classifications(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    classes = (
        scope_query_to_org(
            db.query(models.RawEntity.entity_type, func.count(models.RawEntity.id).label("count")),
            models.RawEntity,
            org_id,
        )
        .filter(models.RawEntity.entity_type != None)
        .group_by(models.RawEntity.entity_type)
        .order_by(func.count(models.RawEntity.id).desc())
        .limit(limit)
        .all()
    )
    return [{"name": c[0], "count": c[1]} for c in classes]


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check(request: Request, db: Session = Depends(get_db)):
    """Liveness + DB connectivity probe with operational metadata."""
    started = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
        logger.exception("health_check_db_error")
    status = "ok" if db_status == "ok" else "degraded"
    return {
        "status": status,
        "service": "ukip-backend",
        "database": db_status,
        "request_id": getattr(request.state, "request_id", None),
        "log_format": current_log_format(),
        "telemetry": telemetry_status(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }


@router.get("/ops/checks", tags=["analytics"])
def operational_checks(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Repeatable operational checklist for runtime, schedulers, and alert readiness."""
    return run_operational_checks(db)


@router.post("/ops/checks/run", tags=["analytics"])
def run_operational_checks_now(
    notify: bool = Query(default=False, description="Dispatch ops.check_failed when the result is not ok"),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Run operational checks on demand and optionally fan out a failure alert."""
    report = run_operational_checks(db)
    report["notification"] = (
        dispatch_operational_alert_if_needed(db, report)
        if notify
        else {"attempted": False, "event": "ops.check_failed", "reason": "notify_disabled"}
    )
    return report


@router.get("/ops/enterprise-readiness", tags=["analytics"])
def enterprise_readiness(
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Internal baseline of enterprise readiness and compliance gaps."""
    return get_enterprise_readiness_report()


@router.get("/ops/tenant-model", tags=["analytics"])
def tenant_model(
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Internal target model and migration waves for tenant isolation."""
    return get_tenant_scoping_report()


# ── Concept Hierarchy (Domain Analysis Fase A) ──────────────────────────────

@router.post("/analytics/concepts/{domain_id}/materialize", tags=["analytics"], status_code=200)
async def materialize_concepts(
    domain_id: str,
    _: models.User = Depends(require_role("super_admin", "admin")),
    db: Session = Depends(get_db),
):
    """Materialize the concept hierarchy from OpenAlex for a domain's enriched entities."""
    _validate_domain_id(domain_id)
    result = await materialize_domain_concepts(db, domain_id)
    return result


@router.get("/analytics/concepts/{domain_id}/tree", tags=["analytics"])
def concept_tree(
    domain_id: str,
    root_level: int | None = Query(default=None, ge=0, le=5),
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the materialized concept hierarchy as a nested JSON tree."""
    _validate_domain_id(domain_id)
    return build_concept_tree(db, domain_id, root_level=root_level)


@router.get("/analytics/concepts/{domain_id}/{concept_node_id}", tags=["analytics"])
def concept_detail(
    domain_id: str,
    concept_node_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    _: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return concept node metadata and paginated entities tagged with that concept."""
    _validate_domain_id(domain_id)
    node = (
        db.query(models.ConceptNode)
        .filter(
            models.ConceptNode.id == concept_node_id,
            models.ConceptNode.domain == domain_id,
        )
        .first()
    )
    if not node:
        raise HTTPException(status_code=404, detail="Concept node not found")

    # Prefer exact OpenAlex concept ID matches; fall back to concept names for
    # legacy records enriched before enrichment_concept_ids existed.
    concept_name = node.display_name
    concept_id_marker = f'"{node.openalex_id}"'
    query = (
        db.query(models.RawEntity)
        .filter(
            models.RawEntity.domain == domain_id,
            models.RawEntity.enrichment_status == EnrichmentStatus.completed,
            or_(
                models.RawEntity.attributes_json.like(f"%{concept_id_marker}%"),
                (
                    or_(
                        models.RawEntity.attributes_json.is_(None),
                        models.RawEntity.attributes_json.notlike("%enrichment_concept_ids%"),
                    )
                    & models.RawEntity.enrichment_concepts.like(f"%{concept_name}%")
                ),
            ),
        )
    )
    total = query.count()
    entities = (
        query.offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return {
        "id": node.id,
        "name": node.display_name,
        "level": node.level,
        "openalex_id": node.openalex_id,
        "entity_count": node.entity_count,
        "entities": [
            {"id": e.id, "primary_label": e.primary_label}
            for e in entities
        ],
        "page": page,
        "per_page": per_page,
        "total": total,
    }


# ── Epistemic classification endpoints ───────────────────────────────────────


def _require_epistemology(domain_id: str):
    """Validate domain exists and has epistemology config. Raises 400 if not."""
    from backend.schema_registry import registry as _reg

    domain = _reg.get_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")
    if not domain.epistemology or not domain.epistemology.paradigms:
        raise HTTPException(
            status_code=400,
            detail=f"Domain '{domain_id}' has no epistemology configuration",
        )
    return domain


@router.post(
    "/analytics/epistemic/{domain_id}/classify",
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def epistemic_classify_batch(
    domain_id: str,
    db: Session = Depends(get_db),
):
    _validate_domain_id(domain_id)
    _require_epistemology(domain_id)
    result = classify_batch(db, domain_id)
    return result


@router.get(
    "/analytics/epistemic/{domain_id}/distribution",
    dependencies=[Depends(get_current_user)],
)
def epistemic_distribution(
    domain_id: str,
    db: Session = Depends(get_db),
):
    _validate_domain_id(domain_id)
    domain = _require_epistemology(domain_id)

    import json as _json

    entities = (
        db.query(models.RawEntity.attributes_json, models.RawEntity.normalized_json)
        .filter(
            models.RawEntity.domain == domain_id,
            models.RawEntity.enrichment_status == EnrichmentStatus.completed,
        )
        .all()
    )

    paradigm_counts: dict[str, int] = {}
    by_year: dict[int, dict[str, int]] = {}
    total_classified = 0
    total_unclassified = 0

    for attrs_json, norm_json in entities:
        try:
            attrs = _json.loads(attrs_json or "{}") or {}
        except (TypeError, ValueError):
            attrs = {}

        profile = attrs.get("epistemic_profile")
        if not profile or not profile.get("dominant"):
            total_unclassified += 1
            continue

        total_classified += 1
        dominant = profile["dominant"]
        paradigm_counts[dominant] = paradigm_counts.get(dominant, 0) + 1

        # Extract year for temporal breakdown
        year = attrs.get("year")
        if not year:
            try:
                norm = _json.loads(norm_json or "{}") or {}
                year = norm.get("year")
            except (TypeError, ValueError):
                pass
        if year:
            try:
                year = int(year)
                if year not in by_year:
                    by_year[year] = {}
                by_year[year][dominant] = by_year[year].get(dominant, 0) + 1
            except (TypeError, ValueError):
                pass

    # Build temporal series sorted by year
    temporal = [
        {"year": y, "paradigm_counts": counts}
        for y, counts in sorted(by_year.items())
    ]

    return {
        "domain_id": domain_id,
        "total_classified": total_classified,
        "total_unclassified": total_unclassified,
        "paradigm_counts": paradigm_counts,
        "paradigms": [
            {"id": p.id, "label": p.label}
            for p in domain.epistemology.paradigms
        ],
        "by_year": temporal,
    }


# ── Domain health (community metrics) endpoints ─────────────────────────────


def _require_discourse_community(domain_id: str):
    """Validate domain exists and has discourse_community config. Raises 400 if not."""
    from backend.schema_registry import registry as _reg

    domain = _reg.get_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")
    if not domain.discourse_community:
        raise HTTPException(
            status_code=400,
            detail=f"Domain '{domain_id}' has no discourse_community configuration",
        )
    return domain


@router.get(
    "/analytics/domain-health/compare",
    dependencies=[Depends(get_current_user)],
)
def domain_health_compare(
    domains: str = Query(..., description="Comma-separated domain IDs"),
    db: Session = Depends(get_db),
):
    from backend.schema_registry import registry as _reg

    domain_ids = [d.strip() for d in domains.split(",") if d.strip()]
    result = {}
    for did in domain_ids:
        domain = _reg.get_domain(did)
        if domain and domain.discourse_community:
            result[did] = compute_health_metrics(db, did)
    return result


@router.get(
    "/analytics/domain-health/{domain_id}",
    dependencies=[Depends(get_current_user)],
)
def domain_health(
    domain_id: str,
    db: Session = Depends(get_db),
):
    _validate_domain_id(domain_id)
    _require_discourse_community(domain_id)
    return compute_health_metrics(db, domain_id)
