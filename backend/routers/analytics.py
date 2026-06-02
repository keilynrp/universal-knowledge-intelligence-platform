"""
Analytics — Dashboard, Discovery & Shared State.
  POST /analytics/keywords/{domain_id}/materialize
  GET  /analytics/keywords/{domain_id}/signals
  GET  /analytics/researchers-by-topic
  GET  /analytics/topic-researcher-graph
  GET  /analytics/abstract-coverage
  POST /analytics/roi
  GET  /dashboard/summary
  GET  /analytics/patterns
  GET  /dashboard/compare
  GET  /analytics/benchmarks/profiles
  GET  /analytics/benchmarks/evaluate
  POST /analytics/cache/invalidate
"""
import logging
import json
import re
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models
from backend.cache import MISS, get_cache
from backend.analyzers.external_attention import compute_attention_summary
from backend.analyzers.geographic import geographic_heatmap
from backend.analyzers.roi_calculator import ROIParams, simulate as _roi_simulate
from backend.analyzers.topic_modeling import TopicAnalyzer
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.domain_scope import parse_scope, resolve_domain_filter
from backend.institutional_benchmarks import evaluate_benchmark, list_benchmark_profiles
from backend.services.analytics_service import AnalyticsService
from backend.services.entity_query import entity_base_q
from backend.services.pattern_discovery import PatternDiscoveryService
from backend.services.researcher_topic_analytics import (
    researchers_by_topic,
    topic_researcher_graph,
)
from backend.services.semantic_keyword_signal_engine import materialize_keyword_signals
from backend.analyzers.coauthorship import coauthorship_network
from backend.tenant_access import resolve_request_org_id, scope_tag

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])

_topic_analyzer = TopicAnalyzer()

_DOMAIN_RE = re.compile(r"^[a-z][a-z0-9_\-]{0,63}$")

_ABSTRACT_FIELD_PATHS = (
    ("abstract",),
    ("abstract_text",),
    ("summary",),
    ("resumen",),
    ("description",),
    ("raw_abstract",),
    ("raw_record", "abstract"),
    ("raw_record", "AB"),
)


def _validate_domain_id(domain_id: str) -> None:
    if not _DOMAIN_RE.match(domain_id):
        raise HTTPException(status_code=422, detail=f"Invalid domain_id '{domain_id}': must match [a-z][a-z0-9_-]{{0,63}}")


def _parse_attrs(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _nested_value(data: dict, path: tuple[str, ...]):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _text_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_text_value(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        for key in ("text", "value", "abstract", "summary", "description"):
            text = _text_value(value.get(key))
            if text:
                return text
        return ""
    return str(value).strip()


def _abstract_matches(attrs: dict) -> list[dict]:
    matches: list[dict] = []
    for path in _ABSTRACT_FIELD_PATHS:
        text_value = _text_value(_nested_value(attrs, path))
        if text_value:
            matches.append({
                "field": ".".join(path),
                "length": len(text_value),
                "preview": text_value[:220],
            })
    return matches


def _dashboard_external_attention(
    db: Session,
    domain_id: str,
    org_id: int | None,
    *,
    limit: int = 5,
) -> dict:
    query = entity_base_q(db, domain_id, org_id)

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


@router.post("/analytics/keywords/{domain_id}/materialize", tags=["analytics"])
def materialize_semantic_keyword_signals(
    domain_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    persist: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Materialize semantic keyword opportunity signals for a domain."""
    if domain_id != "all":
        _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    return materialize_keyword_signals(db, domain_id, org_id=org_id, persist=persist, limit=limit)


@router.get("/analytics/keywords/{domain_id}/signals", tags=["analytics"])
def get_semantic_keyword_signals(
    domain_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Preview semantic keyword opportunity signals without persisting them."""
    if domain_id != "all":
        _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    return materialize_keyword_signals(db, domain_id, org_id=org_id, persist=False, limit=limit)


@router.get("/analytics/researchers-by-topic", tags=["analytics"])
def analytics_researchers_by_topic(
    topic: str = Query(..., min_length=2, max_length=160),
    domain_id: str = Query(default="default", min_length=1, max_length=64),
    limit: int = Query(default=25, ge=1, le=100),
    source: str | None = Query(default=None, max_length=80),
    year_from: int | None = Query(default=None, ge=1800, le=2100),
    year_to: int | None = Query(default=None, ge=1800, le=2100),
    country: str | None = Query(default=None, max_length=80),
    institution: str | None = Query(default=None, max_length=160),
    min_citations: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Rank researchers associated with a topic using ingested and enriched record evidence."""
    if domain_id != "all":
        _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    return researchers_by_topic(
        db,
        domain_id=domain_id,
        org_id=org_id,
        topic=topic,
        limit=limit,
        source=source,
        year_from=year_from,
        year_to=year_to,
        country=country,
        institution=institution,
        min_citations=min_citations,
    )


@router.get("/analytics/topic-researcher-graph", tags=["analytics"])
def analytics_topic_researcher_graph(
    topic: str = Query(..., min_length=2, max_length=160),
    domain_id: str = Query(default="default", min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    min_weight: int = Query(default=1, ge=1),
    source: str | None = Query(default=None, max_length=80),
    year_from: int | None = Query(default=None, ge=1800, le=2100),
    year_to: int | None = Query(default=None, ge=1800, le=2100),
    country: str | None = Query(default=None, max_length=80),
    institution: str | None = Query(default=None, max_length=160),
    min_citations: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Build a topic-centered researcher graph from co-authorship and topic affinity evidence."""
    if domain_id != "all":
        _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    return topic_researcher_graph(
        db,
        domain_id=domain_id,
        org_id=org_id,
        topic=topic,
        limit=limit,
        min_weight=min_weight,
        source=source,
        year_from=year_from,
        year_to=year_to,
        country=country,
        institution=institution,
        min_citations=min_citations,
    )


@router.get("/analytics/abstract-coverage", tags=["analytics"])
def abstract_coverage(
    domain_id: str = Query(default="all", min_length=1, max_length=64),
    sample_limit: int = Query(default=5, ge=0, le=25),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Audit whether tenant-scoped records contain abstract or summary text."""
    org_id = resolve_request_org_id(db, current_user)
    query = entity_base_q(db, domain_id, org_id)

    rows = (
        query.with_entities(
            models.RawEntity.id,
            models.RawEntity.domain,
            models.RawEntity.source,
            models.RawEntity.primary_label,
            models.RawEntity.attributes_json,
        )
        .all()
    )

    by_domain: dict[str, dict] = {}
    by_source: dict[str, dict] = {}
    field_counts: dict[str, int] = defaultdict(int)
    samples: list[dict] = []
    total = len(rows)
    with_abstract = 0

    def bucket(target: dict[str, dict], key: str, has_abstract: bool) -> None:
        entry = target.setdefault(key, {"total": 0, "with_abstract": 0, "coverage_pct": 0.0})
        entry["total"] += 1
        if has_abstract:
            entry["with_abstract"] += 1

    for row in rows:
        attrs = _parse_attrs(row.attributes_json)
        matches = _abstract_matches(attrs)
        has_abstract = bool(matches)
        if has_abstract:
            with_abstract += 1
            for match in matches:
                field_counts[match["field"]] += 1
            if len(samples) < sample_limit:
                samples.append({
                    "id": row.id,
                    "domain": row.domain or "default",
                    "source": row.source or "unknown",
                    "label": row.primary_label,
                    "fields": matches,
                })

        bucket(by_domain, row.domain or "default", has_abstract)
        bucket(by_source, row.source or "unknown", has_abstract)

    for collection in (by_domain, by_source):
        for entry in collection.values():
            entry["coverage_pct"] = round((entry["with_abstract"] / entry["total"]) * 100, 2) if entry["total"] else 0.0

    return {
        "domain_id": domain_id,
        "org_scope": scope_tag(org_id),
        "abstract_fields": [".".join(path) for path in _ABSTRACT_FIELD_PATHS],
        "summary": {
            "total_records": total,
            "records_with_abstract": with_abstract,
            "coverage_pct": round((with_abstract / total) * 100, 2) if total else 0.0,
        },
        "by_domain": dict(sorted(by_domain.items())),
        "by_source": dict(sorted(by_source.items())),
        "field_counts": dict(sorted(field_counts.items())),
        "samples": samples,
    }

# ── In-memory TTL analytics cache (Sprint 83) ─────────────────────────────────

class _SimpleCache:
    """Thin wrapper over the distributed cache for expensive analytics results.

    Public surface unchanged (get/set/invalidate) so the ~10 call-sites in
    ``analytics_analyzers.py`` and ``admin_data_fixes.py`` keep working. Backed
    by Redis when ``REDIS_URL`` is set (cross-worker, deploy-surviving) and the
    in-process backend otherwise. ``get`` translates MISS → None to preserve the
    None-on-miss contract; ``invalidate`` returns an int count.
    """

    def __init__(self, ttl_seconds: int = 300, *, namespace: str = "analytics"):
        self._ttl = ttl_seconds
        self._backend = get_cache(namespace, ttl=ttl_seconds, maxsize=4096)

    def get(self, key: str):
        value = self._backend.get(key)
        return None if value is MISS else value

    def set(self, key: str, value: object) -> None:
        self._backend.set(key, value)

    def invalidate(self, prefix: str = "") -> int:
        return self._backend.invalidate_prefix(prefix)

    def exists_prefix(self, prefix: str) -> bool:
        return self._backend.exists_prefix(prefix)


_analytics_cache = _SimpleCache(ttl_seconds=300, namespace="analytics")   # 5 min — topic / correlation
_dashboard_cache = _SimpleCache(ttl_seconds=120, namespace="dashboard")   # 2 min — dashboard snapshots


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


# ── Co-authorship Network ────────────────────────────────────────────────────

# NOTE: The route decorator was removed in F4b.1. The V2 reader in
# backend/routers/coauthorship.py now owns GET /analyzers/coauthorship/{domain_id}
# and calls this function as the legacy fall-through when COAUTHOR_V2_READ is off.
# F5 removes this entirely once the flag is permanently on.
def _legacy_coauthorship_network(
    response: Response,
    domain_id: str,
    min_weight: int = 1,
    limit: int | None = None,
    force_refresh: bool = False,
    db: Session = None,
    current_user: models.User = None,
):
    """Legacy co-authorship network (entity_relationships CO_AUTHOR edges)."""
    response.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    _validate_domain_id(domain_id)
    org_id = resolve_request_org_id(db, current_user)
    _key = f"coauth_{domain_id}_{scope_tag(org_id)}_{min_weight}_{limit}"
    cached = None if force_refresh else _analytics_cache.get(_key)
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
        description="Comma-separated list of domain IDs to compare (2-4 domains)",
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Side-by-side KPI comparison for 2-4 domains.
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
    _analytics_cache.invalidate(f"coauth_{domain_id}_")
    _dashboard_cache.invalidate(f"dashboard_{domain_id}")
