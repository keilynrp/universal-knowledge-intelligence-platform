from collections import defaultdict
import json
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.analyzers.topic_modeling import TopicAnalyzer
from backend.institutional_benchmarks import evaluate_benchmark
from backend.quality_scorer import _fetch_lookups, score_entity
from backend.services.impact_projection import ImpactProjectionService
from backend.services.pattern_discovery import PatternDiscoveryService
from backend.tenant_access import scope_query_to_org
from backend.schema_registry import registry


class AnalyticsService:
    """
    Core business logic and complex persistence queries for dashboard KPIs and Analytics.
    Extracted from the HTTP router layer to enable isolated unit testing.
    """

    _YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")
    _AUTHOR_LIST_RE = re.compile(r"(;|,).*(;|,)")
    _TOP_BRANDS_N = 5
    _TOP_YEARS_N  = 6
    _LONG_LABEL_LIMIT = 72
    _GENERIC_CONCEPT_LABELS = {
        "context",
        "field",
        "identity",
        "measure",
        "order",
        "persona",
        "production",
        "work",
    }

    @staticmethod
    def _domain_name(domain_id: str) -> str:
        if domain_id == "all":
            return "All domains"
        domain = registry.get_domain(domain_id)
        return domain.name if domain else domain_id

    @classmethod
    def _extract_temporal_year(
        cls,
        attributes_json: str | None,
        primary_label: str | None = None,
        secondary_label: str | None = None,
    ) -> int | None:
        """Extract a plausible scientific year from attrs first, then labels."""
        attrs: dict = {}
        if attributes_json:
            try:
                attrs = json.loads(attributes_json) or {}
            except (TypeError, ValueError):
                attrs = {}

        for key in ("publication_year", "year", "creation_date", "published_at", "date"):
            value = attrs.get(key)
            if value is None:
                continue
            match = cls._YEAR_RE.search(str(value))
            if match:
                return int(match.group(1))

        for fallback in (primary_label, secondary_label):
            if not fallback:
                continue
            match = cls._YEAR_RE.search(str(fallback))
            if match:
                return int(match.group(1))

        return None

    @classmethod
    def _dashboard_label(
        cls,
        primary_label: str | None,
        secondary_label: str | None,
    ) -> str | None:
        """Prefer primary labels for executive reads and trim noisy overlong labels."""
        for raw in (primary_label, secondary_label):
            if not raw:
                continue
            candidate = re.sub(r"\s+", " ", raw).strip()
            if not candidate:
                continue
            if candidate.count(";") >= 2 or candidate.count(",") >= 5:
                continue
            if cls._AUTHOR_LIST_RE.search(candidate) and len(candidate.split()) > 8:
                continue
            if len(candidate) <= cls._LONG_LABEL_LIMIT:
                return candidate
            return f"{candidate[: cls._LONG_LABEL_LIMIT - 1].rstrip()}…"
        return None

    @classmethod
    def _dashboard_concepts(cls, topics: list[dict], top_n: int) -> list[dict]:
        """Normalize obvious concept noise for executive-facing concept clouds."""
        concept_totals: dict[str, int] = defaultdict(int)
        for topic in topics:
            raw = str(topic.get("concept") or "").strip()
            if not raw:
                continue
            cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
            if cleaned.casefold() in cls._GENERIC_CONCEPT_LABELS:
                continue
            concept_totals[cleaned] += int(topic.get("count") or 0)

        total_mentions = sum(concept_totals.values()) or 1
        normalized = [
            {
                "concept": concept,
                "count": count,
                "pct": round(count / total_mentions * 100, 2),
            }
            for concept, count in sorted(
                concept_totals.items(),
                key=lambda item: (-item[1], item[0].lower()),
            )[:top_n]
        ]
        return normalized

    @staticmethod
    def build_recommended_actions(snapshot: dict) -> list[dict]:
        """Return a short, deterministic list of explainable next actions."""
        kpis = snapshot.get("kpis", {})
        quality = snapshot.get("quality") or {}
        top_entities = snapshot.get("top_entities") or []
        top_concepts = snapshot.get("top_concepts") or []

        total_entities = int(kpis.get("total_entities") or 0)
        enrichment_pct = float(kpis.get("enrichment_pct") or 0)
        enriched_count = int(kpis.get("enriched_count") or 0)
        avg_quality = quality.get("average")

        actions: list[dict] = []

        if total_entities and enrichment_pct < 40:
            actions.append({
                "id": "bulk_enrichment",
                "title": "Run bulk enrichment before external review",
                "detail": "Coverage is still too shallow to treat this dataset as decision-ready.",
                "evidence": (
                    f"Only {enriched_count:,} of {total_entities:,} entities "
                    f"are enriched ({enrichment_pct:.1f}% coverage)."
                ),
                "priority": "high",
                "category": "coverage",
                "meta": {
                    "enriched_count": enriched_count,
                    "total_entities": total_entities,
                    "enrichment_pct": round(enrichment_pct, 1),
                },
            })

        if avg_quality is not None and avg_quality < 0.6:
            actions.append({
                "id": "review_low_quality_records",
                "title": "Review low-quality records before briefing stakeholders",
                "detail": "Low-confidence records can distort the first executive readout.",
                "evidence": f"Average quality is {round(avg_quality * 100)}%.",
                "priority": "high" if avg_quality < 0.45 else "medium",
                "category": "quality",
                "meta": {
                    "quality_pct": round(avg_quality * 100),
                },
            })

        if top_entities:
            lead_entity = top_entities[0]
            label = lead_entity.get("primary_label") or f"Entity #{lead_entity.get('id')}"
            citations = int(lead_entity.get("citation_count") or 0)
            actions.append({
                "id": "focus_top_impact_entity",
                "title": "Prioritize the top-impact entity for manual analysis",
                "detail": "A quick manual read of the strongest entity usually improves the pilot narrative.",
                "evidence": f"{label} currently leads with {citations:,} citations.",
                "priority": "medium",
                "category": "impact",
                "meta": {
                    "label": label,
                    "citations": citations,
                },
            })

        if top_concepts and enrichment_pct >= 40:
            lead_concept = top_concepts[0]
            actions.append({
                "id": "explore_leading_concept_cluster",
                "title": "Explore the leading concept cluster",
                "detail": "The strongest semantic cluster is a good candidate for the next decision lens.",
                "evidence": (
                    f"{lead_concept.get('concept', 'Top concept')} appears "
                    f"{int(lead_concept.get('count') or 0):,} times in the current snapshot."
                ),
                "priority": "medium",
                "category": "semantic",
                "meta": {
                    "concept": lead_concept.get("concept", "Top concept"),
                    "count": int(lead_concept.get("count") or 0),
                },
            })

        return actions[:4]

    @classmethod
    def get_domain_snapshot(
        cls,
        db: Session,
        topic_analyzer: TopicAnalyzer,
        domain_id: str,
        org_id: int | None = None,
        benchmark_org: models.Organization | None = None,
        benchmark_profile_id: str | None = None,
        top_n_concepts: int = 10,
        top_n_entities: int = 5
    ) -> dict:
        """Reusable per-domain KPI snapshot — used by dashboard/summary and compare."""
        def _q():
            q = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
            if domain_id and domain_id != "all":
                if domain_id == "default":
                    q = q.filter(
                        (models.RawEntity.domain == domain_id)
                        | (models.RawEntity.domain == None)  # noqa: E711
                    )
                else:
                    q = q.filter(models.RawEntity.domain == domain_id)
            return q

        # Hero KPIs
        total_entities = _q().with_entities(func.count(models.RawEntity.id)).scalar() or 0
        enriched_count = (
            _q().with_entities(func.count(models.RawEntity.id))
            .filter(models.RawEntity.enrichment_status == "completed")
            .scalar() or 0
        )
        enrichment_pct = round(enriched_count / total_entities * 100, 1) if total_entities else 0.0
        avg_citations_raw = (
            _q().with_entities(func.avg(models.RawEntity.enrichment_citation_count))
            .filter(models.RawEntity.enrichment_status == "completed")
            .scalar()
        )
        avg_citations = round(float(avg_citations_raw), 1) if avg_citations_raw else 0.0

        # Entity types distribution
        type_rows = (
            _q().with_entities(models.RawEntity.entity_type,
                               func.count(models.RawEntity.id).label("cnt"))
            .filter(models.RawEntity.entity_type != None)
            .group_by(models.RawEntity.entity_type)
            .order_by(func.count(models.RawEntity.id).desc())
            .limit(8).all()
        )
        type_distribution = [{"type": r[0], "count": r[1]} for r in type_rows]

        temporal_rows = (
            _q().with_entities(
                models.RawEntity.attributes_json,
                models.RawEntity.primary_label,
                models.RawEntity.secondary_label,
            ).all()
        )
        entities_by_year_counter = defaultdict(int)
        label_totals = defaultdict(int)
        label_year_raw = defaultdict(lambda: defaultdict(int))
        all_years_set = set()

        for attributes_json, primary_label, secondary_label in temporal_rows:
            year = cls._extract_temporal_year(attributes_json, primary_label, secondary_label)
            if year is None:
                continue

            entities_by_year_counter[year] += 1
            dashboard_label = cls._dashboard_label(primary_label, secondary_label)
            if dashboard_label:
                label_totals[dashboard_label] += 1
                label_year_raw[dashboard_label][year] += 1
                all_years_set.add(year)

        entities_by_year = [
            {"year": year, "count": entities_by_year_counter[year]}
            for year in sorted(entities_by_year_counter)
        ]

        # Top concepts via TopicAnalyzer
        top_concepts = []
        total_concepts = 0
        try:
            result = topic_analyzer.top_topics(domain_id, top_n=top_n_concepts, org_id=org_id)
            top_concepts = cls._dashboard_concepts(result.get("topics", []), top_n_concepts)
            total_concepts = int(result.get("total_distinct_concepts") or len(top_concepts))
        except Exception:
            pass

        emerging_topic_signals = {
            "domain_id": domain_id,
            "is_experimental": True,
            "years_available": [],
            "baseline_years": [],
            "recent_years": [],
            "signals": [],
        }
        try:
            emerging_topic_signals = topic_analyzer.emerging_signals(
                domain_id,
                top_n=4,
                org_id=org_id,
            )
        except Exception:
            pass

        # Top entities by citation count
        top_entity_rows = (
            _q()
            .with_entities(models.RawEntity.id, models.RawEntity.primary_label,
                           models.RawEntity.enrichment_citation_count,
                           models.RawEntity.enrichment_source)
            .filter(models.RawEntity.enrichment_status == "completed")
            .order_by(models.RawEntity.enrichment_citation_count.desc())
            .limit(top_n_entities * 5)
            .all()
        )
        top_entities: list[dict] = []
        seen_entity_keys: set[tuple[str, str]] = set()
        for r in top_entity_rows:
            label = (r.primary_label or f"Entity #{r.id}").strip()
            key = (label.casefold(), (r.enrichment_source or "").casefold())
            if key in seen_entity_keys:
                continue
            seen_entity_keys.add(key)
            top_entities.append({
                "id": r.id,
                "primary_label": r.primary_label,
                "citation_count": r.enrichment_citation_count or 0,
                "source": r.enrichment_source,
            })
            if len(top_entities) >= top_n_entities:
                break

        # Heatmap: secondary_label x year
        top_labels = sorted(label_totals, key=lambda b: label_totals[b], reverse=True)[:cls._TOP_BRANDS_N]
        heatmap_domains = sorted(all_years_set)[-cls._TOP_YEARS_N:]
        brand_year_matrix = {
            "brands": top_labels, "years": heatmap_domains,
            "matrix": [[label_year_raw[b].get(d, 0) for d in heatmap_domains] for b in top_labels],
        }

        # Quality KPI
        entities_for_quality = _q().all()
        confirmed_labels, entities_with_rels = _fetch_lookups(db)
        quality_values: list[float] = []
        for entity in entities_for_quality:
            score = entity.quality_score
            if score is None:
                score, _ = score_entity(entity, confirmed_labels, entities_with_rels)
            if score is not None:
                quality_values.append(float(score))
        avg_quality = round(sum(quality_values) / len(quality_values), 3) if quality_values else None
        quality_dist = {
            "high":   sum(1 for v in quality_values if v >= 0.7),
            "medium": sum(1 for v in quality_values if 0.3 <= v < 0.7),
            "low":    sum(1 for v in quality_values if v < 0.3),
        }

        snapshot = {
            "domain_id": domain_id,
            "domain_name": cls._domain_name(domain_id),
            "kpis": {
                "total_entities": total_entities,
                "enriched_count": enriched_count,
                "enrichment_pct": enrichment_pct,
                "avg_citations":  avg_citations,
                "total_concepts": total_concepts,
            },
            "type_distribution":  type_distribution,
            "entities_by_year":   entities_by_year,
            "brand_year_matrix":  brand_year_matrix,
            "top_concepts":       top_concepts,
            "emerging_topic_signals": emerging_topic_signals,
            "top_entities":       top_entities,
            "quality": {"average": avg_quality, "distribution": quality_dist},
        }
        snapshot["impact_projection"] = ImpactProjectionService.build_from_snapshot(snapshot)
        snapshot["hidden_patterns"] = PatternDiscoveryService.discover(
            db,
            domain_id=domain_id,
            org_id=org_id,
            limit=5,
        )
        snapshot["recommended_actions"] = cls.build_recommended_actions(snapshot)
        snapshot["institutional_benchmark"] = evaluate_benchmark(
            snapshot,
            benchmark_profile_id,
            org=benchmark_org,
        )
        return snapshot

    @staticmethod
    def get_stats(db: Session, org_id: int | None = None) -> dict:
        total_entities = (
            scope_query_to_org(db.query(func.count(models.RawEntity.id)), models.RawEntity, org_id)
            .scalar()
            or 0
        )

        unique_secondary_labels = (
            scope_query_to_org(
                db.query(func.count(func.distinct(models.RawEntity.secondary_label))),
                models.RawEntity,
                org_id,
            )
            .filter(models.RawEntity.secondary_label != None)
            .scalar() or 0
        )
        unique_entity_types = (
            scope_query_to_org(
                db.query(func.count(func.distinct(models.RawEntity.entity_type))),
                models.RawEntity,
                org_id,
            )
            .filter(models.RawEntity.entity_type != None)
            .scalar() or 0
        )

        validation_rows = (
            scope_query_to_org(
                db.query(models.RawEntity.validation_status, func.count(models.RawEntity.id)),
                models.RawEntity,
                org_id,
            )
            .group_by(models.RawEntity.validation_status)
            .all()
        )
        validation_status = {row[0] or "pending": row[1] for row in validation_rows}

        with_canonical_id = (
            scope_query_to_org(db.query(func.count(models.RawEntity.id)), models.RawEntity, org_id)
            .filter(models.RawEntity.canonical_id != None, models.RawEntity.canonical_id != "")
            .scalar() or 0
        )

        top_secondary_labels = (
            scope_query_to_org(
                db.query(models.RawEntity.secondary_label, func.count(models.RawEntity.id).label("count")),
                models.RawEntity,
                org_id,
            )
            .filter(models.RawEntity.secondary_label != None)
            .group_by(models.RawEntity.secondary_label)
            .order_by(func.count(models.RawEntity.id).desc())
            .limit(10)
            .all()
        )
        type_distribution = (
            scope_query_to_org(
                db.query(models.RawEntity.entity_type, func.count(models.RawEntity.id).label("count")),
                models.RawEntity,
                org_id,
            )
            .filter(models.RawEntity.entity_type != None)
            .group_by(models.RawEntity.entity_type)
            .order_by(func.count(models.RawEntity.id).desc())
            .limit(10)
            .all()
        )
        domain_distribution = (
            scope_query_to_org(
                db.query(models.RawEntity.domain, func.count(models.RawEntity.id).label("count")),
                models.RawEntity,
                org_id,
            )
            .filter(models.RawEntity.domain != None)
            .group_by(models.RawEntity.domain)
            .order_by(func.count(models.RawEntity.id).desc())
            .all()
        )

        quality_rows = (
            scope_query_to_org(db.query(models.RawEntity.quality_score), models.RawEntity, org_id)
            .filter(models.RawEntity.quality_score != None)
            .all()
        )
        quality_values = [r[0] for r in quality_rows if r[0] is not None]
        avg_quality = round(sum(quality_values) / len(quality_values), 3) if quality_values else None
        quality_dist = {
            "high":     sum(1 for v in quality_values if v >= 0.7),
            "medium":   sum(1 for v in quality_values if 0.3 <= v < 0.7),
            "low":      sum(1 for v in quality_values if v < 0.3),
            "unscored": (
                scope_query_to_org(db.query(func.count(models.RawEntity.id)), models.RawEntity, org_id)
                .filter(models.RawEntity.quality_score == None)
                .scalar()
                or 0
            ),
        }

        return {
            "total_entities": total_entities,
            "unique_secondary_labels": unique_secondary_labels,
            "unique_entity_types": unique_entity_types,
            "validation_status": validation_status,
            "identifier_coverage": {
                "with_canonical_id": with_canonical_id,
                "total": total_entities,
            },
            "top_secondary_labels": [{"name": b[0], "count": b[1]} for b in top_secondary_labels],
            "type_distribution": [{"name": t[0], "count": t[1]} for t in type_distribution],
            "domain_distribution": [{"name": d[0], "count": d[1]} for d in domain_distribution],
            "quality": {"average": avg_quality, "distribution": quality_dist},
        }
