"""
Analytics, stats, and lookup endpoints.
  POST /analytics/roi
  GET  /dashboard/summary
  GET  /analyzers/topics/{domain_id}
  GET  /analyzers/cooccurrence/{domain_id}
  GET  /analyzers/clusters/{domain_id}
  GET  /analyzers/correlation/{domain_id}
  GET  /stats
  GET  /brands
  GET  /product-types
  GET  /classifications
  GET  /health
"""
import logging
import re
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from backend import models
from backend.analyzers.external_attention import compute_attention_summary
from backend.analyzers.author_metrics import author_detail, author_rankings
from backend.analyzers.coauthorship import coauthorship_network
from backend.analyzers.correlation import CorrelationAnalyzer
from backend.analyzers.geographic import geographic_analysis, geographic_heatmap
from backend.analyzers.roi_calculator import ROIParams, simulate as _roi_simulate
from backend.analyzers.topic_modeling import TopicAnalyzer
from backend.analyzers.trend_analysis import TrendAnalyzer
from backend.enterprise_readiness import get_enterprise_readiness_report
from backend.institutional_benchmarks import evaluate_benchmark, list_benchmark_profiles
from backend.logging_utils import current_log_format
from backend.ops_checks import dispatch_operational_alert_if_needed, run_operational_checks
from backend.telemetry import telemetry_status
from backend.tenant_scoping import get_tenant_scoping_report
from backend.tenant_access import resolve_request_org_id, scope_query_to_org, scope_tag
from backend.services.analytics_service import AnalyticsService
from backend.services.engine_delegation import (
    _get_engine_client,
    try_engine_analytics,
)
from backend.services.pattern_discovery import PatternDiscoveryService
from backend.analyzers.concept_hierarchy import (
    build_concept_tree,
    materialize_domain_concepts,
)
from backend.analyzers.epistemic_classifier import classify_batch
from backend.analyzers.domain_health import compute_health_metrics
from backend.auth import get_current_user, require_role
from backend.database import get_db
from threading import Lock

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])

_topic_analyzer = TopicAnalyzer()
_correlation_analyzer = CorrelationAnalyzer()
_trend_analyzer = TrendAnalyzer()

_DOMAIN_RE = re.compile(r"^[a-z][a-z0-9_\-]{0,63}$")


def _validate_domain_id(domain_id: str) -> None:
    if not _DOMAIN_RE.match(domain_id):
        raise HTTPException(status_code=422, detail=f"Invalid domain_id '{domain_id}': must match [a-z][a-z0-9_-]{{0,63}}")


def _dashboard_external_attention(
    db: Session,
    domain_id: str,
    org_id: int | None,
    *,
    limit: int = 5,
) -> dict:
    query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
    if domain_id not in ("all", "default"):
        query = query.filter(models.RawEntity.domain == domain_id)
    elif domain_id == "default":
        query = query.filter((models.RawEntity.domain == domain_id) | (models.RawEntity.domain.is_(None)))

    candidates = (
        query.filter(
            models.RawEntity.attributes_json.isnot(None),
            models.RawEntity.attributes_json.like("%external_attention%"),
        )
        .limit(500)
        .all()
    )

    entities: list[dict] = []
    alerts: list[dict] = []
    total_mentions = 0
    active_entities = 0
    score_sum = 0

    for entity in candidates:
        attention = compute_attention_summary(entity.attributes_json)
        summary = attention["summary"]
        score = int(summary["attention_score"])
        mentions = int(summary["total_mentions"])
        if score <= 0 and mentions <= 0:
            continue

        active_entities += 1
        score_sum += score
        total_mentions += mentions
        label = entity.primary_label or entity.secondary_label or f"Entity #{entity.id}"
        entities.append({
            "id": entity.id,
            "label": label,
            "attention_score": score,
            "category": summary["category"],
            "total_mentions": mentions,
            "active_sources": summary["active_sources"],
            "last_seen_at": summary["last_seen_at"],
        })
        for alert in attention.get("alerts", []):
            alerts.append({
                **alert,
                "entity_id": entity.id,
                "entity_label": label,
            })

    entities.sort(key=lambda item: (-item["attention_score"], -item["total_mentions"], item["label"]))
    alerts.sort(key=lambda item: (-int(item.get("priority") or 0), item.get("entity_label") or ""))

    return {
        "summary": {
            "active_entities": active_entities,
            "avg_attention_score": round(score_sum / active_entities, 1) if active_entities else 0,
            "total_mentions": total_mentions,
            "top_score": entities[0]["attention_score"] if entities else 0,
        },
        "top_entities": entities[:limit],
        "alerts": alerts[:3],
    }

# ── In-memory TTL analytics cache (Sprint 83) ─────────────────────────────────

class _SimpleCache:
    """Thread-safe in-memory TTL cache for expensive analytics computations."""

    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = Lock()
        self._ttl = ttl_seconds

    def get(self, key: str):
        with self._lock:
            if key in self._store:
                ts, val = self._store[key]
                if time.time() - ts < self._ttl:
                    return val
                del self._store[key]
        return None

    def set(self, key: str, value: object) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)

    def invalidate(self, prefix: str = "") -> int:
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)] if prefix else list(self._store.keys())
            for k in keys:
                del self._store[k]
            return len(keys)


_analytics_cache = _SimpleCache(ttl_seconds=300)   # 5 min — topic / correlation
_dashboard_cache = _SimpleCache(ttl_seconds=120)   # 2 min — dashboard snapshots


def _resolve_benchmark_org(
    db: Session,
    current_user: models.User,
    requested_org_id: int | None = None,
) -> models.Organization | None:
    effective_org_id = requested_org_id or resolve_request_org_id(db, current_user)
    if not effective_org_id:
        return None

    if current_user.role != "super_admin":
        membership = (
            db.query(models.OrganizationMember)
            .filter(
                models.OrganizationMember.org_id == effective_org_id,
                models.OrganizationMember.user_id == current_user.id,
            )
            .first()
        )
        if membership is None:
            raise HTTPException(status_code=403, detail="Not authorized for this organization")

    return db.get(models.Organization, effective_org_id)


# ── ROI Calculator ────────────────────────────────────────────────────────────

class _ROIRequest(BaseModel):
    investment:          float = Field(..., gt=0)
    horizon_years:       int   = Field(5, ge=1, le=20)
    base_adoption_rate:  float = Field(0.15, ge=0.0, le=1.0)
    adoption_volatility: float = Field(0.05, ge=0.0, le=1.0)
    revenue_per_unit:    float = Field(..., gt=0)
    market_size:         int   = Field(..., ge=1)
    annual_cost:         float = Field(0.0, ge=0.0)
    n_simulations:       int   = Field(2000, ge=100, le=10_000)


@router.post("/analytics/roi", tags=["analytics"])
def run_roi_simulation(
    payload: _ROIRequest,
    _: models.User = Depends(get_current_user),
):
    """Run a Monte Carlo ROI projection for an R&D investment scenario."""
    params = ROIParams(
        investment=payload.investment,
        horizon_years=payload.horizon_years,
        base_adoption_rate=payload.base_adoption_rate,
        adoption_volatility=payload.adoption_volatility,
        revenue_per_unit=payload.revenue_per_unit,
        market_size=payload.market_size,
        annual_cost=payload.annual_cost,
        n_simulations=payload.n_simulations,
    )
    result = _roi_simulate(params)
    return {
        "p5": result.p5, "p10": result.p10, "p25": result.p25,
        "p50": result.p50, "p75": result.p75, "p90": result.p90, "p95": result.p95,
        "net_p10": result.net_p10, "net_p50": result.net_p50, "net_p90": result.net_p90,
        "pessimistic_roi": result.pessimistic_roi,
        "base_roi": result.base_roi,
        "optimistic_roi": result.optimistic_roi,
        "breakeven_prob": result.breakeven_prob,
        "breakeven_year": result.breakeven_year,
        "trajectory": [
            {
                "year": t.year,
                "optimistic": t.optimistic,
                "median": t.median,
                "pessimistic": t.pessimistic,
            }
            for t in result.trajectory
        ],
        "histogram": result.histogram,
        "n_simulations": result.n_simulations,
        "params": result.params,
    }


# ── Topic Modeling & Correlation ──────────────────────────────────────────────

@router.get("/analyzers/topics/{domain_id}")
async def analyzer_topics(
    request: Request,
    domain_id: str,
    top_n: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Top concepts by frequency across enriched entities in a domain."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"topics_{domain_id}_{scope_tag(org_id)}_{top_n}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    # Try engine delegation
    engine_result = await try_engine_analytics(
        _get_engine_client(request), domain_id, "topics", top_n, org_id
    )
    if engine_result is not None and isinstance(engine_result, dict) and "topics" in engine_result:
        engine_result.setdefault("domain_id", domain_id)
        _analytics_cache.set(_key, engine_result)
        return engine_result
    try:
        result = _topic_analyzer.top_topics(domain_id, top_n=top_n, org_id=org_id)
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_topics error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@router.get("/analyzers/cooccurrence/{domain_id}")
async def analyzer_cooccurrence(
    request: Request,
    domain_id: str,
    top_n: int = Query(default=20, ge=1, le=100),
    normalize_similar: bool = Query(default=False),
    min_similarity: float = Query(default=0.88, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Concept co-occurrence pairs with PMI score."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"cooccurrence_{domain_id}_{scope_tag(org_id)}_{top_n}_{normalize_similar}_{min_similarity}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    if not normalize_similar:
        engine_result = await try_engine_analytics(
            _get_engine_client(request), domain_id, "cooccurrence", top_n, org_id
        )
        if engine_result is not None and isinstance(engine_result, dict) and "pairs" in engine_result:
            engine_result.setdefault("domain_id", domain_id)
            _analytics_cache.set(_key, engine_result)
            return engine_result
    try:
        result = _topic_analyzer.cooccurrence(
            domain_id,
            top_n=top_n,
            org_id=org_id,
            normalize_similar=normalize_similar,
            min_similarity=min_similarity,
        )
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_cooccurrence error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@router.get("/analyzers/clusters/{domain_id}")
async def analyzer_clusters(
    request: Request,
    domain_id: str,
    n_clusters: int = Query(default=6, ge=2, le=20),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Greedy concept clusters seeded by top concepts."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"clusters_{domain_id}_{scope_tag(org_id)}_{n_clusters}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    engine_result = await try_engine_analytics(
        _get_engine_client(request), domain_id, "clusters", n_clusters, org_id
    )
    if engine_result is not None and isinstance(engine_result, dict) and "clusters" in engine_result:
        engine_result.setdefault("domain_id", domain_id)
        _analytics_cache.set(_key, engine_result)
        return engine_result
    try:
        result = _topic_analyzer.topic_clusters(domain_id, n_clusters=n_clusters, org_id=org_id)
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_clusters error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@router.get("/analyzers/correlation/{domain_id}")
async def analyzer_correlation(
    request: Request,
    domain_id: str,
    top_n: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Cramér's V pairwise field correlations for categorical columns in a domain."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"correlation_{domain_id}_{scope_tag(org_id)}_{top_n}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    engine_result = await try_engine_analytics(
        _get_engine_client(request), domain_id, "correlation", top_n, org_id
    )
    if engine_result is not None and isinstance(engine_result, dict) and "correlations" in engine_result:
        engine_result.setdefault("domain_id", domain_id)
        _analytics_cache.set(_key, engine_result)
        return engine_result
    try:
        result = _correlation_analyzer.top_correlations(domain_id, top_n=top_n, org_id=org_id)
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_correlation error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


# ── Trend Topics ─────────────────────────────────────────────────────────────

@router.get("/analyzers/trends/{domain_id}")
def analyzer_trends(
    domain_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    min_year: int | None = Query(default=None),
    max_year: int | None = Query(default=None),
    min_years: int = Query(default=3, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Concept frequency trends with slope-based classification (emerging/declining/stable)."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"trends_{domain_id}_{scope_tag(org_id)}_{limit}_{min_year}_{max_year}_{min_years}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = _trend_analyzer.trends(
            domain_id, limit=limit, min_year=min_year, max_year=max_year,
            min_years=min_years, org_id=org_id,
        )
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_trends error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


# ── Author Productivity ──────────────────────────────────────────────────────

@router.get("/analyzers/authors/{domain_id}/{record_id}")
def analyzer_author_detail(
    domain_id: str,
    record_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Full productivity detail for a single author by authority record ID."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    try:
        result = author_detail(domain_id, record_id, org_id=org_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Author not found in this domain")
    return result


@router.get("/analyzers/authors/{domain_id}")
def analyzer_authors(
    domain_id: str,
    sort_by: str = Query(default="h_index", pattern="^(h_index|total_publications|total_citations)$"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Ranked list of authors with h-index and productivity metrics."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"authors_{domain_id}_{scope_tag(org_id)}_{sort_by}_{limit}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = author_rankings(domain_id, sort_by=sort_by, limit=limit, org_id=org_id)
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_authors error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


# ── Geographic / Country Analysis ────────────────────────────────────────────

@router.get("/analyzers/geographic/{domain_id}")
def analyzer_geographic(
    domain_id: str,
    sort_by: str = Query(default="entity_count", pattern="^(entity_count|citation_sum)$"),
    limit: int | None = Query(default=None, ge=1, le=200),
    include_collaboration: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Per-country aggregation with optional international collaboration analysis."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"geo_{domain_id}_{scope_tag(org_id)}_{sort_by}_{limit}_{include_collaboration}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = geographic_analysis(
            domain_id, sort_by=sort_by, limit=limit,
            include_collaboration=include_collaboration, org_id=org_id,
        )
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_geographic error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


# ── Co-authorship Network ────────────────────────────────────────────────────

@router.get("/analyzers/coauthorship/{domain_id}")
def analyzer_coauthorship(
    domain_id: str,
    min_weight: int = Query(default=1, ge=1),
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Co-authorship network with degree centrality and community detection."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"coauth_{domain_id}_{scope_tag(org_id)}_{min_weight}_{limit}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = coauthorship_network(
            domain_id, min_weight=min_weight, limit=limit, org_id=org_id,
        )
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_coauthorship error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@router.get("/dashboard/summary", tags=["analytics"])
def dashboard_summary(
    response: Response,
    domain_id: str = Query(default="default", min_length=1, max_length=64),
    profile_id: str = Query(default="", max_length=80),
    force_refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Aggregated KPIs + timeline + heatmap + concepts for the Executive Dashboard."""
    response.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    org_id = resolve_request_org_id(db, current_user)
    benchmark_org = db.get(models.Organization, org_id) if org_id else None
    profile_key = profile_id or "default_profile"
    _key = f"dashboard_{domain_id}_{profile_key}_{scope_tag(org_id)}"
    if force_refresh:
        _dashboard_cache.invalidate(_key)
    else:
        cached = _dashboard_cache.get(_key)
        if cached is not None:
            return cached
    result = AnalyticsService.get_domain_snapshot(
        db,
        _topic_analyzer,
        domain_id,
        org_id=org_id,
        benchmark_org=benchmark_org,
        benchmark_profile_id=profile_id or None,
        top_n_concepts=30,
        top_n_entities=10,
    )
    # Enrich dashboard with geographic heatmap
    try:
        result["geographic_heatmap"] = geographic_heatmap(domain_id, org_id=org_id)
    except Exception:
        result["geographic_heatmap"] = []

    try:
        result["external_attention"] = _dashboard_external_attention(db, domain_id, org_id)
    except Exception:
        logger.exception("Failed to build external attention dashboard summary")
        result["external_attention"] = {
            "summary": {
                "active_entities": 0,
                "avg_attention_score": 0,
                "total_mentions": 0,
                "top_score": 0,
            },
            "top_entities": [],
            "alerts": [],
        }

    _dashboard_cache.set(_key, result)
    return result


@router.get("/analytics/patterns", tags=["analytics"])
def discover_hidden_patterns(
    domain_id: str = Query(default="default", min_length=1, max_length=64),
    import_batch_id: int | None = Query(default=None, ge=1),
    provider: str | None = Query(default=None, min_length=2, max_length=80),
    portal_slug: str | None = Query(default=None, min_length=3, max_length=120),
    limit: int = Query(default=6, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Discover explainable hidden patterns for a domain, import batch, provider, or catalog portal."""
    org_id = resolve_request_org_id(db, current_user)
    return PatternDiscoveryService.discover(
        db,
        domain_id=domain_id,
        org_id=org_id,
        import_batch_id=import_batch_id,
        provider=provider,
        portal_slug=portal_slug,
        limit=limit,
    )


@router.get("/dashboard/compare", tags=["analytics"])
def dashboard_compare(
    domains: str = Query(
        default="default,science",
        description="Comma-separated list of domain IDs to compare (2–4 domains)",
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Side-by-side KPI comparison for 2–4 domains.
    Returns a list of domain snapshots in the same order as requested.
    """
    domain_ids = [d.strip() for d in domains.split(",") if d.strip()]
    for did in domain_ids:
        _validate_domain_id(did)
    if len(domain_ids) < 2:
        raise HTTPException(status_code=422, detail="Provide at least 2 domain IDs")
    if len(domain_ids) > 4:
        domain_ids = domain_ids[:4]

    org_id = resolve_request_org_id(db, current_user)
    return {
        "domains": [
            AnalyticsService.get_domain_snapshot(
                db, _topic_analyzer, did, org_id=org_id, top_n_concepts=10, top_n_entities=5
            )
            for did in domain_ids
        ]
    }


@router.get("/analytics/benchmarks/profiles", tags=["analytics"])
def list_institutional_benchmark_profiles(
    org_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    benchmark_org = _resolve_benchmark_org(db, current_user, org_id)
    return list_benchmark_profiles(org=benchmark_org)


@router.get("/analytics/benchmarks/evaluate", tags=["analytics"])
def evaluate_institutional_benchmark(
    domain_id: str = Query(default="default", min_length=1, max_length=64),
    profile_id: str = Query(default="", max_length=80),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    benchmark_org = db.get(models.Organization, org_id) if org_id else None
    try:
        snapshot = AnalyticsService.get_domain_snapshot(
            db,
            _topic_analyzer,
            domain_id,
            org_id=org_id,
            benchmark_org=benchmark_org,
            benchmark_profile_id=profile_id or None,
            top_n_concepts=30,
            top_n_entities=10,
        )
        return evaluate_benchmark(snapshot, profile_id or None, org=benchmark_org)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Cache management ──────────────────────────────────────────────────────────

@router.post("/analytics/cache/invalidate", tags=["analytics"])
def invalidate_analytics_cache(
    prefix: str = Query(default="", description="Optional key prefix to target specific domain"),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Manually bust the analytics in-memory cache (admin+). Called automatically on data mutations."""
    n1 = _analytics_cache.invalidate(prefix)
    n2 = _dashboard_cache.invalidate(prefix)
    return {"invalidated": n1 + n2, "prefix": prefix or "(all)"}


def invalidate_analytics_for_domain(domain_id: str) -> None:
    """
    Call this from ingest/entity routers after mutations to keep analytics fresh.
    Invalidates only entries matching the affected domain.
    """
    _analytics_cache.invalidate(f"topics_{domain_id}_")
    _analytics_cache.invalidate(f"cooccurrence_{domain_id}_")
    _analytics_cache.invalidate(f"clusters_{domain_id}_")
    _analytics_cache.invalidate(f"correlation_{domain_id}_")
    _analytics_cache.invalidate(f"trends_{domain_id}_")
    _analytics_cache.invalidate(f"authors_{domain_id}_")
    _analytics_cache.invalidate(f"geo_{domain_id}_")
    _dashboard_cache.invalidate(f"dashboard_{domain_id}")


# ── Global stats and lookup endpoints ────────────────────────────────────────

@router.get("/stats")
def get_stats(
    domain_id: str = Query(default="all", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    return AnalyticsService.get_stats(db, org_id=org_id, domain_id=domain_id)


@router.get("/brands")
def get_all_brands(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, current_user)
    brands = (
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
    return [{"name": b[0], "count": b[1]} for b in brands]


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
            models.RawEntity.enrichment_status == "completed",
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
            models.RawEntity.enrichment_status == "completed",
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
