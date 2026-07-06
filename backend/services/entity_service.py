from collections import Counter, defaultdict
from typing import Optional

from sqlalchemy import and_, false as sa_false, func, or_
from sqlalchemy.orm import Session

from backend import models
from backend.quality_scorer import _fetch_lookups, score_entity
from backend.services import work_type as work_type_mod
from backend.tenant_access import scope_query_to_org


class EntityService:
    """
    Core business logic and complex persistence queries for Universal Entities.
    Extracted from the HTTP router layer to enable isolated unit testing.
    """

    _FACET_FIELDS = {
        "entity_type":        models.RawEntity.entity_type,
        "domain":             models.RawEntity.domain,
        "validation_status":  models.RawEntity.validation_status,
        "enrichment_status":  models.RawEntity.enrichment_status,
        "source":             models.RawEntity.source,
        "work_type":          models.RawEntity.enrichment_work_type,
    }

    _JOURNAL_NIF_BAYES_READY = "nif_bayes_ready"

    # Transient (non-mapped) attributes attached to RawEntity instances by
    # attach_journal_metrics so schemas.Entity can serialize the journal signal.
    _JOURNAL_METRIC_ATTRS = (
        "journal_display_name",
        "journal_nif",
        "journal_nif_bayes",
        "journal_nif_ci_low",
        "journal_nif_ci_high",
        "journal_nif_bayes_ready",
    )

    @staticmethod
    def ensure_quality_scores(db: Session, org_id: int | None = None) -> int:
        """Compute missing quality scores before quality filtering/sorting.

        Some records arrive without a persisted quality_score. SQL predicates such
        as quality_score >= 0.7 exclude NULL rows, so materialize missing scores
        before applying user-facing quality thresholds.
        """
        missing = (
            scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
            .filter(models.RawEntity.quality_score.is_(None))
            .all()
        )
        if not missing:
            return 0

        confirmed_labels, entities_with_rels = _fetch_lookups(db)
        for entity in missing:
            score, _ = score_entity(entity, confirmed_labels, entities_with_rels)
            entity.quality_score = score
        db.flush()
        return len(missing)

    @staticmethod
    def attach_journal_metrics(db: Session, entities, org_id: int | None):
        """Attach per-record journal scientometric signal to RawEntity instances.

        Looks up JournalMetric by enrichment_issn_l in a single batched query
        (no N+1) and sets transient attributes consumed by schemas.Entity. The
        org scoping predicate mirrors _filter_journal_metric_signal so the
        per-record badge agrees exactly with the journal_metric_signal facet.
        """
        issns = {
            e.enrichment_issn_l
            for e in entities
            if getattr(e, "enrichment_issn_l", None)
        }
        metrics: dict[str, models.JournalMetric] = {}
        if issns:
            rows = (
                db.query(models.JournalMetric)
                .filter(
                    models.JournalMetric.issn_l.in_(issns),
                    models.JournalMetric.org_id == org_id,
                )
                .all()
            )
            for row in rows:
                metrics[row.issn_l] = row

        for entity in entities:
            metric = metrics.get(getattr(entity, "enrichment_issn_l", None))
            if metric is not None:
                entity.journal_display_name = metric.display_name
                entity.journal_nif = metric.normalized_impact_factor
                entity.journal_nif_bayes = metric.nif_bayes
                entity.journal_nif_ci_low = metric.nif_ci_low
                entity.journal_nif_ci_high = metric.nif_ci_high
                entity.journal_nif_bayes_ready = (
                    metric.normalized_impact_factor is not None
                    and metric.nif_bayes is not None
                )
            else:
                entity.journal_display_name = None
                entity.journal_nif = None
                entity.journal_nif_bayes = None
                entity.journal_nif_ci_low = None
                entity.journal_nif_ci_high = None
                entity.journal_nif_bayes_ready = False
        return entities

    @staticmethod
    def _filter_journal_metric_signal(query, signal: Optional[str], org_id: int | None):
        if signal != EntityService._JOURNAL_NIF_BAYES_READY:
            return query
        return query.join(
            models.JournalMetric,
            and_(
                models.RawEntity.enrichment_issn_l == models.JournalMetric.issn_l,
                models.JournalMetric.org_id == org_id,
                models.JournalMetric.normalized_impact_factor.isnot(None),
                models.JournalMetric.nif_bayes.isnot(None),
            ),
        )

    @classmethod
    def get_facets(
        cls,
        db: Session,
        fields_raw: str,
        search: Optional[str] = None,
        min_quality: Optional[float] = None,
        import_batch_id: Optional[int] = None,
        ft_entity_type: Optional[str] = None,
        ft_domain: Optional[str] = None,
        ft_validation_status: Optional[str] = None,
        ft_enrichment_status: Optional[str] = None,
        ft_source: Optional[str] = None,
        concept: Optional[str] = None,
        ft_work_type: Optional[str] = None,
        ft_journal_metric_signal: Optional[str] = None,
        org_id: int | None = None,
    ) -> dict:
        if min_quality is not None:
            cls.ensure_quality_scores(db, org_id)

        requested = [f.strip() for f in fields_raw.split(",") if f.strip()]
        result = {}
        for field in requested:
            col = cls._FACET_FIELDS.get(field)
            if col is None and field != "journal_metric_signal":
                continue
            if field == "journal_metric_signal":
                query = scope_query_to_org(db.query(models.RawEntity.id), models.RawEntity, org_id)
            else:
                query = scope_query_to_org(
                    db.query(col, func.count(models.RawEntity.id).label("cnt")),
                    models.RawEntity,
                    org_id,
                )

            if search:
                search_filter = f"%{search}%"
                query = query.filter(
                    or_(
                        models.RawEntity.primary_label.ilike(search_filter),
                        models.RawEntity.canonical_id.ilike(search_filter),
                        models.RawEntity.secondary_label.ilike(search_filter),
                        models.RawEntity.entity_type.ilike(search_filter),
                    )
                )

            if min_quality is not None:
                query = query.filter(models.RawEntity.quality_score >= min_quality)
            if import_batch_id is not None:
                query = query.filter(models.RawEntity.import_batch_id == import_batch_id)
            if concept:
                query = query.filter(models.RawEntity.enrichment_concepts.ilike(f"%{concept}%"))

            if ft_entity_type and field != "entity_type":
                query = query.filter(models.RawEntity.entity_type == ft_entity_type)
            if ft_domain and field != "domain":
                query = query.filter(models.RawEntity.domain == ft_domain)
            if ft_validation_status and field != "validation_status":
                query = query.filter(models.RawEntity.validation_status == ft_validation_status)
            if ft_enrichment_status and field != "enrichment_status":
                query = query.filter(models.RawEntity.enrichment_status == ft_enrichment_status)
            if ft_source and field != "source":
                query = query.filter(models.RawEntity.source == ft_source)
            if ft_work_type and field != "work_type":
                expr = work_type_mod.work_type_filter(models.RawEntity.enrichment_work_type, ft_work_type)
                if expr is not None:
                    query = query.filter(expr)
            if ft_journal_metric_signal and field != "journal_metric_signal":
                query = cls._filter_journal_metric_signal(query, ft_journal_metric_signal, org_id)

            if field == "journal_metric_signal":
                ready_count = cls._filter_journal_metric_signal(
                    query,
                    cls._JOURNAL_NIF_BAYES_READY,
                    org_id,
                ).count()
                result[field] = (
                    [{"value": cls._JOURNAL_NIF_BAYES_READY, "count": ready_count}]
                    if ready_count
                    else []
                )
                continue

            if field == "work_type":
                raw_rows = query.group_by(col).all()  # includes NULLs (no strip)
                buckets: Counter = Counter()
                for raw_val, cnt in raw_rows:
                    buckets[work_type_mod.category_for(raw_val)] += cnt
                result[field] = sorted(
                    ({"value": code, "count": n} for code, n in buckets.items()),
                    key=lambda d: -d["count"],
                )
                continue

            rows = (
                query
                .filter(col != None, col != "")
                .group_by(col)
                .order_by(func.count(models.RawEntity.id).desc())
                .all()
            )
            result[field] = [{"value": r[0], "count": r[1]} for r in rows]
        return result

    @staticmethod
    def get_list(
        db: Session,
        skip: int,
        limit: int,
        search: Optional[str],
        sort_by: str,
        order: str,
        min_quality: Optional[float],
        ft_entity_type: Optional[str],
        ft_domain: Optional[str],
        ft_validation_status: Optional[str],
        ft_enrichment_status: Optional[str],
        ft_source: Optional[str],
        concept: Optional[str] = None,
        ft_work_type: Optional[str] = None,
        ft_journal_metric_signal: Optional[str] = None,
        org_id: int | None = None,
    ) -> tuple[int, list[models.RawEntity]]:
        if min_quality is not None or sort_by == "quality_score":
            EntityService.ensure_quality_scores(db, org_id)

        query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                or_(
                    models.RawEntity.primary_label.ilike(search_filter),
                    models.RawEntity.canonical_id.ilike(search_filter),
                    models.RawEntity.secondary_label.ilike(search_filter),
                    models.RawEntity.entity_type.ilike(search_filter),
                )
            )

        if min_quality is not None:
            query = query.filter(models.RawEntity.quality_score >= min_quality)
        if concept:
            query = query.filter(models.RawEntity.enrichment_concepts.ilike(f"%{concept}%"))

        if ft_entity_type:
            query = query.filter(models.RawEntity.entity_type == ft_entity_type)
        if ft_domain:
            query = query.filter(models.RawEntity.domain == ft_domain)
        if ft_validation_status:
            query = query.filter(models.RawEntity.validation_status == ft_validation_status)
        if ft_enrichment_status:
            query = query.filter(models.RawEntity.enrichment_status == ft_enrichment_status)
        if ft_source:
            query = query.filter(models.RawEntity.source == ft_source)
        if ft_work_type:
            expr = work_type_mod.work_type_filter(models.RawEntity.enrichment_work_type, ft_work_type)
            query = query.filter(expr) if expr is not None else query.filter(sa_false())
        if ft_journal_metric_signal:
            query = EntityService._filter_journal_metric_signal(query, ft_journal_metric_signal, org_id)

        sort_col = {
            "id": models.RawEntity.id,
            "quality_score": models.RawEntity.quality_score,
            "primary_label": models.RawEntity.primary_label,
            "enrichment_status": models.RawEntity.enrichment_status,
        }.get(sort_by, models.RawEntity.id)
        
        query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

        total = query.count()
        entities = query.offset(skip).limit(limit).all()
        if any(entity.quality_score is None for entity in entities):
            confirmed_labels, entities_with_rels = _fetch_lookups(db)
            for entity in entities:
                if entity.quality_score is None:
                    derived_score, _ = score_entity(entity, confirmed_labels, entities_with_rels)
                    entity.quality_score = derived_score
        return total, entities

    @staticmethod
    def get_grouped(
        db: Session,
        skip: int,
        limit: int,
        search: Optional[str],
        org_id: int | None = None,
    ) -> tuple[int, list[dict]]:
        variant_counts = (
            scope_query_to_org(
                db.query(
                    models.RawEntity.primary_label,
                    func.count(models.RawEntity.id).label("variant_count"),
                ),
                models.RawEntity,
                org_id,
            )
            .filter(models.RawEntity.primary_label != None)
            .group_by(models.RawEntity.primary_label)
            .subquery()
        )

        query = scope_query_to_org(
            db.query(models.RawEntity.primary_label, variant_counts.c.variant_count),
            models.RawEntity,
            org_id,
        ).join(
            variant_counts, models.RawEntity.primary_label == variant_counts.c.primary_label
        ).group_by(models.RawEntity.primary_label, variant_counts.c.variant_count)

        if search:
            search_filter = f"%{search}%"
            query = query.filter(models.RawEntity.primary_label.ilike(search_filter))

        query = query.order_by(variant_counts.c.variant_count.desc())
        total_groups = query.count()
        
        product_groups = query.offset(skip).limit(limit).all()

        entity_names = [row[0] for row in product_groups]
        if not entity_names:
            return total_groups, []

        all_variants = (
            scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
            .filter(models.RawEntity.primary_label.in_(entity_names))
            .all()
        )

        variants_by_name: dict[str, list] = defaultdict(list)
        for v in all_variants:
            variants_by_name[v.primary_label].append(v)

        results = [
            {
                "primary_label": entity_name,
                "variant_count": variant_count,
                "variants": variants_by_name.get(entity_name, []),
            }
            for entity_name, variant_count in product_groups
        ]
        return total_groups, results
