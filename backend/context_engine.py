"""
Phase 11 — Context Engineering Layer
ContextEngine: assembles rich, structured domain context for LLM injection.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ContextEngine:
    """
    Assembles a structured snapshot of a domain's current state:
    schema, entity stats, data gaps, and top topics.
    Suitable for injecting into LLM system prompts.
    """

    def build_domain_context(
        self, domain_id: str, db: Session, org_id: int | None = None
    ) -> Dict[str, Any]:
        """Return a rich context dict for the given domain.

        The result is injected into LLM system prompts, so every aggregate
        is scoped to ``org_id`` (issue #32). ``org_id=None`` = super_admin global.
        """

        ctx: Dict[str, Any] = {
            "domain_id":    domain_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Schema info
        ctx["schema"] = self._get_schema(domain_id)

        # 2. Entity stats
        ctx["entity_stats"] = self._get_entity_stats(domain_id, db, org_id)

        # 3. Gap summary
        ctx["gaps"] = self._get_gap_summary(domain_id, db, org_id)

        # 4. Top topics
        ctx["top_topics"] = self._get_top_topics(domain_id, db, org_id)

        return ctx

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_schema(self, domain_id: str) -> Dict[str, Any]:
        from backend.schema_registry import SchemaRegistry
        domain = SchemaRegistry().get_domain(domain_id)
        if domain is None:
            return {}
        return {
            "name":           domain.name,
            "primary_entity": domain.primary_entity,
            "attributes": [
                {"name": a.name, "type": a.type, "label": a.label}
                for a in domain.attributes
            ],
        }

    def _get_entity_stats(self, domain_id: str, db: Session, org_id: int | None = None) -> Dict[str, Any]:
        from backend import models
        from backend.analytics.rag_engine import ENRICHED_STATUSES
        from backend.tenant_access import scope_query_to_org
        total    = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).count()
        enriched = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
            models.RawEntity.enrichment_status.in_(ENRICHED_STATUSES)
        ).count()
        return {
            "total":        total,
            "enriched":     enriched,
            "pct_enriched": round(enriched / total * 100, 1) if total else 0.0,
        }

    def _get_gap_summary(self, domain_id: str, db: Session, org_id: int | None = None) -> Dict[str, Any]:
        try:
            from backend.analyzers.gap_detector import GapAnalyzer
            gaps = GapAnalyzer().analyze(domain_id, db, org_id)
            return {
                "critical": sum(1 for g in gaps if g.severity == "critical"),
                "warning":  sum(1 for g in gaps if g.severity == "warning"),
                "ok":       sum(1 for g in gaps if g.severity == "ok"),
            }
        except Exception as exc:
            logger.debug("ContextEngine gap error: %s", exc)
            return {"critical": 0, "warning": 0, "ok": 0}

    def _get_top_topics(self, domain_id: str, db: Session, org_id: int | None = None, top_n: int = 5) -> List[Dict[str, Any]]:
        try:
            from backend.analyzers.topic_modeling import TopicAnalyzer
            result = TopicAnalyzer().top_topics(domain_id, top_n=top_n, org_id=org_id)
            # top_topics returns a dict with a "topics" key (list of {concept, count, ...})
            raw_topics = result.get("topics", [])
            return [{"concept": t["concept"], "count": t["count"]} for t in raw_topics[:top_n]]
        except Exception as exc:
            logger.debug("ContextEngine topics error: %s", exc)
            return []

    # ── LLM formatting ─────────────────────────────────────────────────────────

    def format_for_llm(self, ctx: Dict[str, Any]) -> str:
        """
        Serialises the context dict into a concise structured block
        suitable for injection into an LLM system prompt.
        """
        stats  = ctx.get("entity_stats", {})
        gaps   = ctx.get("gaps", {})
        schema = ctx.get("schema", {})
        topics = ctx.get("top_topics", [])

        lines = [
            "=== DOMAIN CONTEXT ===",
            f"Domain      : {ctx.get('domain_id', 'unknown')}",
            f"Schema      : {schema.get('name', '')} (primary entity: {schema.get('primary_entity', '')})",
            f"Entities    : {stats.get('total', 0):,} total, "
            f"{stats.get('enriched', 0):,} enriched ({stats.get('pct_enriched', 0)}%)",
            f"Data gaps   : {gaps.get('critical', 0)} critical · "
            f"{gaps.get('warning', 0)} warnings · {gaps.get('ok', 0)} ok",
        ]

        if topics:
            topic_str = ", ".join(t["concept"] for t in topics)
            lines.append(f"Top concepts: {topic_str}")

        lines.append("======================")
        return "\n".join(lines)

    def snapshot_json(self, ctx: Dict[str, Any]) -> str:
        """Serialise context to a compact JSON string (for DB storage)."""
        return json.dumps(ctx, ensure_ascii=False)

    def diff_snapshots(self, json_a: str, json_b: str) -> Dict[str, Any]:
        """
        Compare two stored context JSON strings (A = older, B = newer).
        Returns a delta dict with before/after/change for entity_stats, gaps,
        and a merged top_topics list.
        """
        a = json.loads(json_a)
        b = json.loads(json_b)

        def _delta(section: str, key: str) -> Dict[str, Any]:
            va = a.get(section, {}).get(key, 0)
            vb = b.get(section, {}).get(key, 0)
            return {"before": va, "after": vb, "change": round(vb - va, 4)}

        topics_a = {t["concept"]: t["count"] for t in a.get("top_topics", [])}
        topics_b = {t["concept"]: t["count"] for t in b.get("top_topics", [])}
        all_concepts = sorted(set(topics_a) | set(topics_b))
        topics_delta = [
            {
                "concept": c,
                "before":  topics_a.get(c, 0),
                "after":   topics_b.get(c, 0),
                "change":  topics_b.get(c, 0) - topics_a.get(c, 0),
            }
            for c in all_concepts
        ]

        return {
            "snapshot_a_domain":    a.get("domain_id"),
            "snapshot_b_domain":    b.get("domain_id"),
            "snapshot_a_generated": a.get("generated_at"),
            "snapshot_b_generated": b.get("generated_at"),
            "entity_stats": {
                "total":        _delta("entity_stats", "total"),
                "enriched":     _delta("entity_stats", "enriched"),
                "pct_enriched": _delta("entity_stats", "pct_enriched"),
            },
            "gaps": {
                "critical": _delta("gaps", "critical"),
                "warning":  _delta("gaps", "warning"),
                "ok":       _delta("gaps", "ok"),
            },
            "top_topics": topics_delta,
        }

    def build_analysis_prompt(self, context_json: str) -> str:
        """
        Format a session snapshot into a structured analysis request for the LLM.
        Returns the user-side message (the system prompt is kept generic in the caller).
        """
        ctx    = json.loads(context_json)
        stats  = ctx.get("entity_stats", {})
        gaps   = ctx.get("gaps", {})
        topics = ctx.get("top_topics", [])
        schema = ctx.get("schema", {})

        topic_str = ", ".join(t["concept"] for t in topics[:10]) if topics else "none"

        return (
            "You are a data analyst reviewing a knowledge management platform snapshot.\n\n"
            "=== DOMAIN SNAPSHOT ===\n"
            f"Domain        : {ctx.get('domain_id', 'unknown')}\n"
            f"Schema        : {schema.get('name', '')} ({schema.get('primary_entity', '')})\n"
            f"Taken at      : {ctx.get('generated_at', 'unknown')}\n"
            f"Total entities: {stats.get('total', 0):,}\n"
            f"Enriched      : {stats.get('enriched', 0):,} ({stats.get('pct_enriched', 0)}%)\n"
            f"Critical gaps : {gaps.get('critical', 0)}\n"
            f"Warnings      : {gaps.get('warning', 0)}\n"
            f"Top concepts  : {topic_str}\n"
            "=======================\n\n"
            "Please provide:\n"
            "1. A 2-3 sentence summary of the current data health.\n"
            "2. The top 3 risks or data quality issues that need immediate attention.\n"
            "3. Three specific, actionable recommendations to improve data quality and enrichment coverage.\n"
            "4. A brief outlook: what the domain will look like in 3 months if no action is taken.\n\n"
            "Be concise, specific, and prioritize by impact."
        )

    def build_diff_analysis_prompt(self, diff: Dict[str, Any]) -> str:
        """
        Format a diff result into a structured change-analysis request for the LLM.
        """
        es   = diff.get("entity_stats", {})
        gaps = diff.get("gaps", {})

        def _fmt(d: Dict[str, Any]) -> str:
            c = d.get("change", 0)
            sign = "+" if c > 0 else ""
            return f"{d.get('before', 0)} → {d.get('after', 0)} ({sign}{c})"

        changed_topics = [
            t for t in diff.get("top_topics", []) if t.get("change", 0) != 0
        ]
        topic_lines = "\n".join(
            f"  {t['concept']}: {t['before']} → {t['after']} ({'+' if t['change'] > 0 else ''}{t['change']})"
            for t in sorted(changed_topics, key=lambda x: abs(x["change"]), reverse=True)[:8]
        ) or "  (no changes)"

        return (
            "You are a data analyst reviewing changes between two knowledge platform snapshots.\n\n"
            "=== SNAPSHOT DELTA ===\n"
            f"From domain   : {diff.get('snapshot_a_domain', '?')}  [{diff.get('snapshot_a_generated', '?')}]\n"
            f"To domain     : {diff.get('snapshot_b_domain', '?')}  [{diff.get('snapshot_b_generated', '?')}]\n\n"
            "Entity stats:\n"
            f"  Total    : {_fmt(es.get('total', {}))}\n"
            f"  Enriched : {_fmt(es.get('enriched', {}))}\n"
            f"  Enriched%: {_fmt(es.get('pct_enriched', {}))}\n\n"
            "Data gaps:\n"
            f"  Critical : {_fmt(gaps.get('critical', {}))}\n"
            f"  Warnings : {_fmt(gaps.get('warning', {}))}\n"
            f"  OK       : {_fmt(gaps.get('ok', {}))}\n\n"
            "Concept changes:\n"
            f"{topic_lines}\n"
            "======================\n\n"
            "Please provide:\n"
            "1. A 2-3 sentence narrative of what changed between the two snapshots.\n"
            "2. Whether the overall data health improved, deteriorated, or stayed the same — and why.\n"
            "3. The most significant change and its likely cause or implication.\n"
            "4. Two concrete next steps based on the observed trends.\n\n"
            "Be concise and data-driven."
        )

    def build_recall_prompt(self, label: str, context_json: str, user_query: str) -> str:
        """
        Format a persisted session snapshot + the incoming user query into a
        structured block for prepending to an LLM system prompt.
        """
        ctx    = json.loads(context_json)
        stats  = ctx.get("entity_stats", {})
        gaps   = ctx.get("gaps", {})
        topics = ctx.get("top_topics", [])

        topic_str = ", ".join(t["concept"] for t in topics) if topics else "none"

        lines = [
            "=== MEMORY CONTEXT ===",
            f"Recalled session : {label or 'Unnamed'}",
            f"Domain           : {ctx.get('domain_id', 'unknown')}",
            f"Snapshot taken   : {ctx.get('generated_at', 'unknown')}",
            f"Entities         : {stats.get('total', 0):,} total, "
            f"{stats.get('enriched', 0):,} enriched ({stats.get('pct_enriched', 0)}%)",
            f"Data gaps        : {gaps.get('critical', 0)} critical · "
            f"{gaps.get('warning', 0)} warnings · {gaps.get('ok', 0)} ok",
            f"Top concepts     : {topic_str}",
            "======================",
            f"User query: {user_query}",
        ]
        return "\n".join(lines)
