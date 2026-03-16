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
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend import models
from backend.analyzers.correlation import CorrelationAnalyzer
from backend.analyzers.roi_calculator import ROIParams, simulate as _roi_simulate
from backend.analyzers.topic_modeling import TopicAnalyzer
from backend.services.analytics_service import AnalyticsService
from backend.auth import get_current_user, require_role
from backend.database import get_db
import time
from threading import Lock

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])

_topic_analyzer = TopicAnalyzer()
_correlation_analyzer = CorrelationAnalyzer()

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
def analyzer_topics(
    domain_id: str,
    top_n: int = Query(default=30, ge=1, le=100),
    _: models.User = Depends(get_current_user),
):
    """Top concepts by frequency across enriched entities in a domain."""
    _key = f"topics_{domain_id}_{top_n}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = _topic_analyzer.top_topics(domain_id, top_n=top_n)
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_topics error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@router.get("/analyzers/cooccurrence/{domain_id}")
def analyzer_cooccurrence(
    domain_id: str,
    top_n: int = Query(default=20, ge=1, le=100),
    _: models.User = Depends(get_current_user),
):
    """Concept co-occurrence pairs with PMI score."""
    _key = f"cooccurrence_{domain_id}_{top_n}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = _topic_analyzer.cooccurrence(domain_id, top_n=top_n)
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_cooccurrence error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@router.get("/analyzers/clusters/{domain_id}")
def analyzer_clusters(
    domain_id: str,
    n_clusters: int = Query(default=6, ge=2, le=20),
    _: models.User = Depends(get_current_user),
):
    """Greedy concept clusters seeded by top concepts."""
    _key = f"clusters_{domain_id}_{n_clusters}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = _topic_analyzer.topic_clusters(domain_id, n_clusters=n_clusters)
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_clusters error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@router.get("/analyzers/correlation/{domain_id}")
def analyzer_correlation(
    domain_id: str,
    top_n: int = Query(default=20, ge=1, le=50),
    _: models.User = Depends(get_current_user),
):
    """Cramér's V pairwise field correlations for categorical columns in a domain."""
    _key = f"correlation_{domain_id}_{top_n}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = _correlation_analyzer.top_correlations(domain_id, top_n=top_n)
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_correlation error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@router.get("/dashboard/summary", tags=["analytics"])
def dashboard_summary(
    domain_id: str = Query(default="default", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Aggregated KPIs + timeline + heatmap + concepts for the Executive Dashboard."""
    _key = f"dashboard_{domain_id}"
    cached = _dashboard_cache.get(_key)
    if cached is not None:
        return cached
    result = AnalyticsService.get_domain_snapshot(db, _topic_analyzer, domain_id, top_n_concepts=30, top_n_entities=10)
    _dashboard_cache.set(_key, result)
    return result


@router.get("/dashboard/compare", tags=["analytics"])
def dashboard_compare(
    domains: str = Query(
        default="default,science",
        description="Comma-separated list of domain IDs to compare (2–4 domains)",
    ),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """
    Side-by-side KPI comparison for 2–4 domains.
    Returns a list of domain snapshots in the same order as requested.
    """
    domain_ids = [d.strip() for d in domains.split(",") if d.strip()]
    if len(domain_ids) < 2:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Provide at least 2 domain IDs")
    if len(domain_ids) > 4:
        domain_ids = domain_ids[:4]

    return {
        "domains": [
            AnalyticsService.get_domain_snapshot(db, _topic_analyzer, did, top_n_concepts=10, top_n_entities=5)
            for did in domain_ids
        ]
    }


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
    _analytics_cache.invalidate(f"topics_{domain_id}")
    _analytics_cache.invalidate(f"cooccurrence_{domain_id}")
    _analytics_cache.invalidate(f"clusters_{domain_id}")
    _analytics_cache.invalidate(f"correlation_{domain_id}")
    _dashboard_cache.invalidate(f"dashboard_{domain_id}")


# ── Global stats and lookup endpoints ────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    return AnalyticsService.get_stats(db)


@router.get("/brands")
def get_all_brands(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    brands = (
        db.query(models.RawEntity.secondary_label, func.count(models.RawEntity.id).label("count"))
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
    _: models.User = Depends(get_current_user),
):
    types = (
        db.query(models.RawEntity.entity_type, func.count(models.RawEntity.id).label("count"))
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
    _: models.User = Depends(get_current_user),
):
    classes = (
        db.query(models.RawEntity.entity_type, func.count(models.RawEntity.id).label("count"))
        .filter(models.RawEntity.entity_type != None)
        .group_by(models.RawEntity.entity_type)
        .order_by(func.count(models.RawEntity.id).desc())
        .limit(limit)
        .all()
    )
    return [{"name": c[0], "count": c[1]} for c in classes]


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Liveness + DB connectivity probe."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    status = "ok" if db_status == "ok" else "degraded"
    return {"status": status, "database": db_status}
