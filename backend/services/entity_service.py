from collections import defaultdict
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend import models


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
    }

    @classmethod
    def get_facets(cls, db: Session, fields_raw: str) -> dict:
        requested = [f.strip() for f in fields_raw.split(",") if f.strip()]
        result = {}
        for field in requested:
            col = cls._FACET_FIELDS.get(field)
            if col is None:
                continue
            rows = (
                db.query(col, func.count(models.RawEntity.id).label("cnt"))
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
    ) -> tuple[int, list[models.RawEntity]]:
        query = db.query(models.RawEntity)
        
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

        sort_col = {
            "id": models.RawEntity.id,
            "quality_score": models.RawEntity.quality_score,
            "primary_label": models.RawEntity.primary_label,
            "enrichment_status": models.RawEntity.enrichment_status,
        }.get(sort_by, models.RawEntity.id)
        
        query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

        total = query.count()
        entities = query.offset(skip).limit(limit).all()
        return total, entities

    @staticmethod
    def get_grouped(db: Session, skip: int, limit: int, search: Optional[str]) -> tuple[int, list[dict]]:
        variant_counts = (
            db.query(
                models.RawEntity.primary_label,
                func.count(models.RawEntity.id).label("variant_count"),
            )
            .filter(models.RawEntity.primary_label != None)
            .group_by(models.RawEntity.primary_label)
            .subquery()
        )

        query = (
            db.query(models.RawEntity.primary_label, variant_counts.c.variant_count)
            .join(variant_counts, models.RawEntity.primary_label == variant_counts.c.primary_label)
            .group_by(models.RawEntity.primary_label, variant_counts.c.variant_count)
        )

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
            db.query(models.RawEntity)
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
