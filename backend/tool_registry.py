"""
Phase 11 Sprint 49 — Tool Registry
A lightweight registry of callable analytics tools that the LLM (or frontend)
can invoke by name with typed parameters.

Built-in tools:
  get_entity_stats     — entity count + enrichment breakdown
  get_gaps             — run GapAnalyzer, return gap list
  get_topics           — run TopicAnalyzer, return top concepts
  get_harmonization_log — last N harmonization steps
  get_enrichment_stats  — enrichment coverage + citation stats

Tenant scoping (issue #32): every handler receives the caller's resolved
``org_id`` and scopes its queries with ``scope_query_to_org``. ``org_id=None``
means super_admin global scope (no filter); ``-1`` means legacy-global.
"""
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session
from backend.analytics.rag_engine import ENRICHED_STATUSES
from backend.tenant_access import scope_query_to_org

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    name:        str
    description: str
    parameters:  Dict[str, Any]   # JSON Schema for params


class ToolRegistry:
    def __init__(self) -> None:
        self._tools:    Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable]       = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
    ) -> None:
        self._tools[name]    = ToolDefinition(name=name, description=description, parameters=parameters)
        self._handlers[name] = handler

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self._tools.values()
        ]

    def invoke(
        self,
        name: str,
        params: Dict[str, Any],
        db: Session,
        org_id: int | None = None,
    ) -> Any:
        if name not in self._handlers:
            raise KeyError(name)
        return self._handlers[name](params, db, org_id)


# ── Singleton ──────────────────────────────────────────────────────────────────

_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = _build_registry()
    return _registry


# ── Tool implementations ────────────────────────────────────────────────────────

def _tool_entity_stats(params: Dict[str, Any], db: Session, org_id: int | None = None) -> Dict[str, Any]:
    from backend import models
    domain_id = params.get("domain_id", "default")
    total    = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).count()
    enriched = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
        models.RawEntity.enrichment_status.in_(ENRICHED_STATUSES)
    ).count()
    pending  = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
        models.RawEntity.enrichment_status == "pending"
    ).count()
    return {
        "domain_id": domain_id,
        "total": total,
        "enriched": enriched,
        "pending": pending,
        "pct_enriched": round(enriched / total * 100, 1) if total else 0.0,
    }


def _tool_get_gaps(params: Dict[str, Any], db: Session, org_id: int | None = None) -> List[Dict[str, Any]]:
    from backend.analyzers.gap_detector import GapAnalyzer
    domain_id = params.get("domain_id", "default")
    gaps = GapAnalyzer().analyze(domain_id, db, org_id)
    return [
        {
            "category": g.category, "severity": g.severity,
            "title": g.title, "pct": g.pct,
            "affected_count": g.affected_count, "total_count": g.total_count,
            "action": g.action,
        }
        for g in gaps
    ]


def _tool_get_topics(params: Dict[str, Any], db: Session, org_id: int | None = None) -> List[Dict[str, Any]]:
    from backend.analyzers.topic_modeling import TopicAnalyzer
    domain_id = params.get("domain_id", "default")
    top_n     = int(params.get("top_n", 10))
    result = TopicAnalyzer().top_topics(domain_id, top_n=top_n, org_id=org_id)
    return [{"concept": t["concept"], "count": t["count"]} for t in result.get("topics", [])]


def _tool_harmonization_log(params: Dict[str, Any], db: Session, org_id: int | None = None) -> List[Dict[str, Any]]:
    from backend import models
    limit = int(params.get("limit", 10))
    steps = (
        scope_query_to_org(db.query(models.HarmonizationLog), models.HarmonizationLog, org_id)
        .order_by(models.HarmonizationLog.executed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "step_id": s.step_id,
            "step_name": s.step_name,
            "records_updated": s.records_updated,
            "fields_modified": s.fields_modified,
            "reverted": s.reverted,
            "executed_at": str(s.executed_at),
        }
        for s in steps
    ]


def _tool_enrichment_stats(params: Dict[str, Any], db: Session, org_id: int | None = None) -> Dict[str, Any]:
    from backend import models
    from sqlalchemy import func
    domain_id      = params.get("domain_id", "default")
    total_enriched = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
        models.RawEntity.enrichment_status.in_(ENRICHED_STATUSES)
    ).count()
    avg_citations  = scope_query_to_org(
        db.query(func.avg(models.RawEntity.enrichment_citation_count)), models.RawEntity, org_id
    ).filter(
        models.RawEntity.enrichment_citation_count.isnot(None),
    ).scalar() or 0.0
    return {
        "domain_id": domain_id,
        "total_enriched": total_enriched,
        "avg_citation_count": round(float(avg_citations), 2),
    }


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _tool_researchers_by_topic(params: Dict[str, Any], db: Session, org_id: int | None = None) -> Dict[str, Any]:
    from backend.services.researcher_topic_analytics import researchers_by_topic

    return researchers_by_topic(
        db,
        domain_id=params.get("domain_id", "default"),
        org_id=org_id,
        topic=params.get("topic", ""),
        limit=int(params.get("limit", 25)),
        source=params.get("source"),
        year_from=_optional_int(params.get("year_from")),
        year_to=_optional_int(params.get("year_to")),
        country=params.get("country"),
        institution=params.get("institution"),
        min_citations=int(params.get("min_citations", 0)),
    )


def _tool_topic_researcher_graph(params: Dict[str, Any], db: Session, org_id: int | None = None) -> Dict[str, Any]:
    from backend.services.researcher_topic_analytics import topic_researcher_graph

    return topic_researcher_graph(
        db,
        domain_id=params.get("domain_id", "default"),
        org_id=org_id,
        topic=params.get("topic", ""),
        limit=int(params.get("limit", 50)),
        min_weight=int(params.get("min_weight", 1)),
        source=params.get("source"),
        year_from=_optional_int(params.get("year_from")),
        year_to=_optional_int(params.get("year_to")),
        country=params.get("country"),
        institution=params.get("institution"),
        min_citations=int(params.get("min_citations", 0)),
    )


# ── Registry factory ───────────────────────────────────────────────────────────

def _build_registry() -> ToolRegistry:
    r = ToolRegistry()

    r.register(
        name="get_entity_stats",
        description="Returns total entity count, enrichment coverage, and pending count for a domain.",
        parameters={"domain_id": {"type": "string", "default": "default"}},
        handler=_tool_entity_stats,
    )
    r.register(
        name="get_gaps",
        description="Runs the Gap Detector and returns prioritized data quality issues for a domain.",
        parameters={"domain_id": {"type": "string", "default": "default"}},
        handler=_tool_get_gaps,
    )
    r.register(
        name="get_topics",
        description="Returns the top N concept topics extracted from enriched entities in a domain.",
        parameters={
            "domain_id": {"type": "string", "default": "default"},
            "top_n":     {"type": "integer", "default": 10},
        },
        handler=_tool_get_topics,
    )
    r.register(
        name="get_harmonization_log",
        description="Returns the most recent harmonization pipeline steps.",
        parameters={"limit": {"type": "integer", "default": 10}},
        handler=_tool_harmonization_log,
    )
    r.register(
        name="get_enrichment_stats",
        description="Returns enrichment coverage and average citation count for a domain.",
        parameters={"domain_id": {"type": "string", "default": "default"}},
        handler=_tool_enrichment_stats,
    )
    r.register(
        name="find_researchers_by_topic",
        description="Returns researchers working on a requested topic, ranked by evidence, citations, authority identifiers, recency, and enrichment quality.",
        parameters={
            "domain_id": {"type": "string", "default": "default"},
            "topic": {"type": "string"},
            "limit": {"type": "integer", "default": 25},
            "source": {"type": "string"},
            "year_from": {"type": "integer"},
            "year_to": {"type": "integer"},
            "country": {"type": "string"},
            "institution": {"type": "string"},
            "min_citations": {"type": "integer", "default": 0},
        },
        handler=_tool_researchers_by_topic,
    )
    r.register(
        name="get_topic_researcher_graph",
        description="Builds a topic-centered researcher graph with works-on-topic and coauthor relationships.",
        parameters={
            "domain_id": {"type": "string", "default": "default"},
            "topic": {"type": "string"},
            "limit": {"type": "integer", "default": 50},
            "min_weight": {"type": "integer", "default": 1},
            "source": {"type": "string"},
            "year_from": {"type": "integer"},
            "year_to": {"type": "integer"},
            "country": {"type": "string"},
            "institution": {"type": "string"},
            "min_citations": {"type": "integer", "default": 0},
        },
        handler=_tool_topic_researcher_graph,
    )
    r.register(
        name="analyze_domain",
        description=(
            "Runs GapAnalyzer and TopicAnalyzer for a domain and returns a combined "
            "health summary: critical/warning/ok counts, top 5 concepts, and recommended actions."
        ),
        parameters={"domain_id": {"type": "string", "default": "default"}},
        handler=_tool_analyze_domain,
    )

    return r


def _tool_analyze_domain(params: Dict[str, Any], db: Session, org_id: int | None = None) -> Dict[str, Any]:
    from backend.analyzers.gap_detector import GapAnalyzer
    from backend.analyzers.topic_modeling import TopicAnalyzer

    domain_id = params.get("domain_id", "default")

    # Gaps
    try:
        gaps = GapAnalyzer().analyze(domain_id, db, org_id)
        gap_summary = {
            "critical": sum(1 for g in gaps if g.severity == "critical"),
            "warning":  sum(1 for g in gaps if g.severity == "warning"),
            "ok":       sum(1 for g in gaps if g.severity == "ok"),
            "actions":  [g.action for g in gaps if g.severity == "critical"][:3],
        }
    except Exception as exc:
        gap_summary = {"error": str(exc)}

    # Topics
    try:
        result   = TopicAnalyzer().top_topics(domain_id, top_n=5, org_id=org_id)
        top_concepts = [t["concept"] for t in result.get("topics", [])]
    except Exception as exc:
        top_concepts = []

    return {
        "domain_id":    domain_id,
        "gap_summary":  gap_summary,
        "top_concepts": top_concepts,
        "health_score": max(0, 100 - gap_summary.get("critical", 0) * 20 - gap_summary.get("warning", 0) * 5)
        if isinstance(gap_summary, dict) and "critical" in gap_summary else None,
    }
