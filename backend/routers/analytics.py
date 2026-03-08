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
from backend.auth import get_current_user
from backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

_topic_analyzer = TopicAnalyzer()
_correlation_analyzer = CorrelationAnalyzer()


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
    try:
        return _topic_analyzer.top_topics(domain_id, top_n=top_n)
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
    try:
        return _topic_analyzer.cooccurrence(domain_id, top_n=top_n)
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
    try:
        return _topic_analyzer.topic_clusters(domain_id, n_clusters=n_clusters)
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
    try:
        return _correlation_analyzer.top_correlations(domain_id, top_n=top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_correlation error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


# ── Executive Dashboard ───────────────────────────────────────────────────────

_YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")
_TOP_BRANDS_N = 5
_TOP_YEARS_N  = 6


@router.get("/dashboard/summary", tags=["analytics"])
def dashboard_summary(
    domain_id: str = Query(default="default", min_length=1, max_length=64),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Aggregated KPIs + timeline + heatmap + concepts for the Executive Dashboard."""
    # ── Hero KPIs ─────────────────────────────────────────────────────────────
    total_entities = db.query(func.count(models.RawEntity.id)).scalar() or 0
    enriched_count = (
        db.query(func.count(models.RawEntity.id))
        .filter(models.RawEntity.enrichment_status == "completed")
        .scalar() or 0
    )
    enrichment_pct = round(enriched_count / total_entities * 100, 1) if total_entities else 0.0
    avg_citations_raw = (
        db.query(func.avg(models.RawEntity.enrichment_citation_count))
        .filter(models.RawEntity.enrichment_status == "completed")
        .scalar()
    )
    avg_citations = round(float(avg_citations_raw), 1) if avg_citations_raw else 0.0

    # ── Timeline: entities grouped by year extracted from creation_date ────────
    date_rows = (
        db.query(models.RawEntity.creation_date)
        .filter(models.RawEntity.creation_date != None, models.RawEntity.creation_date != "")
        .all()
    )
    year_counts: dict[int, int] = defaultdict(int)
    for (raw_date,) in date_rows:
        m = _YEAR_RE.search(str(raw_date))
        if m:
            year_counts[int(m.group(1))] += 1
    entities_by_year = [
        {"year": yr, "count": year_counts[yr]}
        for yr in sorted(year_counts)
    ]

    # ── Brand × Year heatmap (top 5 brands × last _TOP_YEARS_N years) ─────────
    brand_date_rows = (
        db.query(models.RawEntity.brand_capitalized, models.RawEntity.creation_date)
        .filter(
            models.RawEntity.brand_capitalized != None,
            models.RawEntity.brand_capitalized != "",
        )
        .all()
    )
    # Count total per brand (for ranking)
    brand_totals: dict[str, int] = defaultdict(int)
    brand_year_raw: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for (brand, raw_date) in brand_date_rows:
        brand_totals[brand] += 1
        m = _YEAR_RE.search(str(raw_date or ""))
        if m:
            brand_year_raw[brand][int(m.group(1))] += 1

    top_brands = sorted(brand_totals, key=lambda b: brand_totals[b], reverse=True)[:_TOP_BRANDS_N]
    all_years_in_data = sorted(year_counts.keys())
    heatmap_years = all_years_in_data[-_TOP_YEARS_N:] if all_years_in_data else []
    brand_year_matrix = {
        "brands": top_brands,
        "years": heatmap_years,
        "matrix": [
            [brand_year_raw[b].get(yr, 0) for yr in heatmap_years]
            for b in top_brands
        ],
    }

    # ── Top concepts via TopicAnalyzer ────────────────────────────────────────
    top_concepts: list[dict] = []
    try:
        result = _topic_analyzer.top_topics(domain_id, top_n=30)
        top_concepts = result.get("topics", [])
    except Exception:
        pass  # no concepts if domain has no enriched data

    total_concepts = len(top_concepts)

    # ── Top entities by citation count ────────────────────────────────────────
    top_entity_rows = (
        db.query(
            models.RawEntity.id,
            models.RawEntity.entity_name,
            models.RawEntity.brand_capitalized,
            models.RawEntity.enrichment_citation_count,
            models.RawEntity.enrichment_source,
        )
        .filter(models.RawEntity.enrichment_status == "completed")
        .order_by(models.RawEntity.enrichment_citation_count.desc())
        .limit(10)
        .all()
    )
    top_entities = [
        {
            "id": r.id,
            "entity_name": r.entity_name,
            "brand": r.brand_capitalized,
            "citation_count": r.enrichment_citation_count or 0,
            "source": r.enrichment_source,
        }
        for r in top_entity_rows
    ]

    return {
        "domain_id": domain_id,
        "kpis": {
            "total_entities":  total_entities,
            "enriched_count":  enriched_count,
            "enrichment_pct":  enrichment_pct,
            "avg_citations":   avg_citations,
            "total_concepts":  total_concepts,
        },
        "entities_by_year":   entities_by_year,
        "brand_year_matrix":  brand_year_matrix,
        "top_concepts":       top_concepts,
        "top_entities":       top_entities,
    }


# ── Global stats and lookup endpoints ────────────────────────────────────────

@router.get("/stats")
def get_stats(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    total_entities = db.query(func.count(models.RawEntity.id)).scalar() or 0

    unique_brands = (
        db.query(func.count(func.distinct(models.RawEntity.brand_capitalized)))
        .filter(models.RawEntity.brand_capitalized != None)
        .scalar() or 0
    )
    unique_models = (
        db.query(func.count(func.distinct(models.RawEntity.model)))
        .filter(models.RawEntity.model != None)
        .scalar() or 0
    )
    unique_entity_types = (
        db.query(func.count(func.distinct(models.RawEntity.entity_type)))
        .filter(models.RawEntity.entity_type != None)
        .scalar() or 0
    )

    validation_rows = (
        db.query(models.RawEntity.validation_status, func.count(models.RawEntity.id))
        .group_by(models.RawEntity.validation_status)
        .all()
    )
    validation_status = {row[0] or "pending": row[1] for row in validation_rows}

    with_sku = (
        db.query(func.count(models.RawEntity.id))
        .filter(models.RawEntity.sku != None, models.RawEntity.sku != "")
        .scalar() or 0
    )
    with_barcode = (
        db.query(func.count(models.RawEntity.id))
        .filter(models.RawEntity.barcode != None, models.RawEntity.barcode != "")
        .scalar() or 0
    )
    with_gtin = (
        db.query(func.count(models.RawEntity.id))
        .filter(models.RawEntity.gtin != None, models.RawEntity.gtin != "")
        .scalar() or 0
    )

    top_brands = (
        db.query(models.RawEntity.brand_capitalized, func.count(models.RawEntity.id).label("count"))
        .filter(models.RawEntity.brand_capitalized != None)
        .group_by(models.RawEntity.brand_capitalized)
        .order_by(func.count(models.RawEntity.id).desc())
        .limit(10)
        .all()
    )
    type_distribution = (
        db.query(models.RawEntity.entity_type, func.count(models.RawEntity.id).label("count"))
        .filter(models.RawEntity.entity_type != None)
        .group_by(models.RawEntity.entity_type)
        .order_by(func.count(models.RawEntity.id).desc())
        .limit(10)
        .all()
    )
    status_distribution = (
        db.query(models.RawEntity.status, func.count(models.RawEntity.id).label("count"))
        .filter(models.RawEntity.status != None)
        .group_by(models.RawEntity.status)
        .order_by(func.count(models.RawEntity.id).desc())
        .all()
    )
    classification_distribution = (
        db.query(models.RawEntity.classification, func.count(models.RawEntity.id).label("count"))
        .filter(models.RawEntity.classification != None)
        .group_by(models.RawEntity.classification)
        .order_by(func.count(models.RawEntity.id).desc())
        .all()
    )
    products_with_variants = (
        db.query(func.count(models.RawEntity.id))
        .filter(models.RawEntity.variant != None, models.RawEntity.variant != "")
        .scalar() or 0
    )
    unique_products_with_variants = (
        db.query(func.count(func.distinct(models.RawEntity.entity_name)))
        .filter(
            models.RawEntity.variant != None,
            models.RawEntity.variant != "",
            models.RawEntity.entity_name != None,
        )
        .scalar() or 0
    )

    return {
        "total_entities": total_entities,
        "unique_brands": unique_brands,
        "unique_models": unique_models,
        "unique_entity_types": unique_entity_types,
        "entities_with_variants": products_with_variants,
        "unique_entities_with_variants": unique_products_with_variants,
        "validation_status": validation_status,
        "identifier_coverage": {
            "with_sku": with_sku,
            "with_barcode": with_barcode,
            "with_gtin": with_gtin,
            "total": total_entities,
        },
        "top_brands": [{"name": b[0], "count": b[1]} for b in top_brands],
        "type_distribution": [{"name": t[0], "count": t[1]} for t in type_distribution],
        "classification_distribution": [
            {"name": c[0], "count": c[1]} for c in classification_distribution
        ],
        "status_distribution": [{"name": s[0], "count": s[1]} for s in status_distribution],
    }


@router.get("/brands")
def get_all_brands(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    brands = (
        db.query(models.RawEntity.brand_capitalized, func.count(models.RawEntity.id).label("count"))
        .filter(models.RawEntity.brand_capitalized != None)
        .group_by(models.RawEntity.brand_capitalized)
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
        db.query(models.RawEntity.classification, func.count(models.RawEntity.id).label("count"))
        .filter(models.RawEntity.classification != None)
        .group_by(models.RawEntity.classification)
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
