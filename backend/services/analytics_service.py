from collections import defaultdict
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.analyzers.topic_modeling import TopicAnalyzer


class AnalyticsService:
    """
    Core business logic and complex persistence queries for dashboard KPIs and Analytics.
    Extracted from the HTTP router layer to enable isolated unit testing.
    """

    _YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")
    _TOP_BRANDS_N = 5
    _TOP_YEARS_N  = 6

    @classmethod
    def get_domain_snapshot(
        cls,
        db: Session,
        topic_analyzer: TopicAnalyzer,
        domain_id: str,
        top_n_concepts: int = 10,
        top_n_entities: int = 5
    ) -> dict:
        """Reusable per-domain KPI snapshot — used by dashboard/summary and compare."""
        def _q():
            q = db.query(models.RawEntity)
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

        entities_by_year = []

        # Top concepts via TopicAnalyzer
        top_concepts = []
        try:
            result = topic_analyzer.top_topics(domain_id, top_n=top_n_concepts)
            top_concepts = result.get("topics", [])
        except Exception:
            pass

        total_concepts = len(top_concepts)

        # Top entities by citation count
        top_entity_rows = (
            _q()
            .with_entities(models.RawEntity.id, models.RawEntity.primary_label,
                           models.RawEntity.enrichment_citation_count,
                           models.RawEntity.enrichment_source)
            .filter(models.RawEntity.enrichment_status == "completed")
            .order_by(models.RawEntity.enrichment_citation_count.desc())
            .limit(top_n_entities)
            .all()
        )
        top_entities = [
            {"id": r.id, "primary_label": r.primary_label,
             "citation_count": r.enrichment_citation_count or 0, "source": r.enrichment_source}
            for r in top_entity_rows
        ]

        # Heatmap: secondary_label × domain
        label_domain_rows = (
            _q().with_entities(models.RawEntity.secondary_label, models.RawEntity.domain)
            .filter(models.RawEntity.secondary_label != None, models.RawEntity.secondary_label != "")
            .all()
        )
        label_totals = defaultdict(int)
        label_domain_raw = defaultdict(lambda: defaultdict(int))
        all_domains_set = set()
        for (label, dom) in label_domain_rows:
            label_totals[label] += 1
            dom_key = dom or "default"
            label_domain_raw[label][dom_key] += 1
            all_domains_set.add(dom_key)
        
        top_labels = sorted(label_totals, key=lambda b: label_totals[b], reverse=True)[:cls._TOP_BRANDS_N]
        heatmap_domains = sorted(all_domains_set)[:cls._TOP_YEARS_N]
        brand_year_matrix = {
            "brands": top_labels, "years": heatmap_domains,
            "matrix": [[label_domain_raw[b].get(d, 0) for d in heatmap_domains] for b in top_labels],
        }

        # Quality KPI
        quality_rows = (
            _q()
            .with_entities(models.RawEntity.quality_score)
            .filter(models.RawEntity.quality_score != None)
            .all()
        )
        quality_values = [r[0] for r in quality_rows if r[0] is not None]
        avg_quality = round(sum(quality_values) / len(quality_values), 3) if quality_values else None
        quality_dist = {
            "high":   sum(1 for v in quality_values if v >= 0.7),
            "medium": sum(1 for v in quality_values if 0.3 <= v < 0.7),
            "low":    sum(1 for v in quality_values if v < 0.3),
        }

        return {
            "domain_id": domain_id,
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
            "top_entities":       top_entities,
            "quality": {"average": avg_quality, "distribution": quality_dist},
        }

    @staticmethod
    def get_stats(db: Session) -> dict:
        total_entities = db.query(func.count(models.RawEntity.id)).scalar() or 0

        unique_secondary_labels = (
            db.query(func.count(func.distinct(models.RawEntity.secondary_label)))
            .filter(models.RawEntity.secondary_label != None)
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

        with_canonical_id = (
            db.query(func.count(models.RawEntity.id))
            .filter(models.RawEntity.canonical_id != None, models.RawEntity.canonical_id != "")
            .scalar() or 0
        )

        top_secondary_labels = (
            db.query(models.RawEntity.secondary_label, func.count(models.RawEntity.id).label("count"))
            .filter(models.RawEntity.secondary_label != None)
            .group_by(models.RawEntity.secondary_label)
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
        domain_distribution = (
            db.query(models.RawEntity.domain, func.count(models.RawEntity.id).label("count"))
            .filter(models.RawEntity.domain != None)
            .group_by(models.RawEntity.domain)
            .order_by(func.count(models.RawEntity.id).desc())
            .all()
        )

        quality_rows = (
            db.query(models.RawEntity.quality_score)
            .filter(models.RawEntity.quality_score != None)
            .all()
        )
        quality_values = [r[0] for r in quality_rows if r[0] is not None]
        avg_quality = round(sum(quality_values) / len(quality_values), 3) if quality_values else None
        quality_dist = {
            "high":     sum(1 for v in quality_values if v >= 0.7),
            "medium":   sum(1 for v in quality_values if 0.3 <= v < 0.7),
            "low":      sum(1 for v in quality_values if v < 0.3),
            "unscored": db.query(func.count(models.RawEntity.id)).filter(models.RawEntity.quality_score == None).scalar() or 0,
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
