"""
Domain analyzer endpoints (extracted from analytics.py).
  GET  /analyzers/topics/{domain_id}
  GET  /analyzers/cooccurrence/{domain_id}
  GET  /analyzers/clusters/{domain_id}
  GET  /analyzers/correlation/{domain_id}
  GET  /analyzers/trends/{domain_id}
  GET  /analyzers/authors/{domain_id}/{record_id}
  GET  /analyzers/authors/{domain_id}
  GET  /analyzers/geographic/{domain_id}
  GET  /analyzers/geographic/{domain_id}/country/{country_code}
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from backend import models
from backend.analyzers.author_metrics import author_detail, author_rankings
from backend.analyzers.coauthorship import coauthorship_network
from backend.analyzers.correlation import CorrelationAnalyzer
from backend.analyzers.geographic import country_timeseries, geographic_analysis
from backend.analyzers.topic_modeling import TopicAnalyzer
from backend.analyzers.trend_analysis import TrendAnalyzer
from backend.auth import get_current_user
from backend.database import get_db
from backend.routers.analytics import _analytics_cache, _validate_domain_id
from backend.services.engine_delegation import (
    _get_engine_client,
    try_engine_analytics,
)
from backend.tenant_access import resolve_request_org_id, scope_tag

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])

_topic_analyzer = TopicAnalyzer()
_correlation_analyzer = CorrelationAnalyzer()
_trend_analyzer = TrendAnalyzer()


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
    """Cramer's V pairwise field correlations for categorical columns in a domain."""
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
    year_from: int | None = Query(default=None, ge=1900, le=2100),
    year_to: int | None = Query(default=None, ge=1900, le=2100),
    min_citations: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Per-country aggregation with optional filters and collaboration analysis."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = (
        f"geo_{domain_id}_{scope_tag(org_id)}_{sort_by}_{limit}_{include_collaboration}"
        f"_{year_from}_{year_to}_{min_citations}"
    )
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = geographic_analysis(
            domain_id, sort_by=sort_by, limit=limit,
            include_collaboration=include_collaboration,
            year_from=year_from, year_to=year_to, min_citations=min_citations,
            org_id=org_id,
        )
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_geographic error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@router.get("/analyzers/geographic/{domain_id}/country/{country_code}")
def analyzer_geographic_country(
    domain_id: str,
    country_code: str,
    years: int = Query(default=9, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Yearly entity & citation series for a single country."""
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"geo_ts_{domain_id}_{scope_tag(org_id)}_{country_code.upper()}_{years}"
    cached = _analytics_cache.get(_key)
    if cached is not None:
        return cached
    try:
        result = country_timeseries(domain_id, country_code, years=years, org_id=org_id)
        _analytics_cache.set(_key, result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_geographic_country error %s/%s", domain_id, country_code)
        raise HTTPException(status_code=500, detail="Analysis error")
