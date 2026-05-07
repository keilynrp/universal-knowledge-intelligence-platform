from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from statistics import median
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend import models
from backend.tenant_access import scope_query_to_org


_WORD_RE = re.compile(r"[a-z0-9]+")


class PatternDiscoveryService:
    """Deterministic data-mining layer for explainable hidden portfolio signals."""

    @classmethod
    def discover(
        cls,
        db: Session,
        *,
        domain_id: str = "default",
        org_id: int | None = None,
        import_batch_id: int | None = None,
        provider: str | None = None,
        portal_slug: str | None = None,
        limit: int = 6,
    ) -> dict[str, Any]:
        scoped_import_batch_id = import_batch_id
        scoped_domain_id = domain_id

        if portal_slug:
            portal = (
                scope_query_to_org(db.query(models.CatalogPortal), models.CatalogPortal, org_id)
                .filter(models.CatalogPortal.slug == portal_slug)
                .first()
            )
            if portal:
                scoped_import_batch_id = scoped_import_batch_id or portal.source_batch_id
                scoped_domain_id = scoped_domain_id or portal.domain_id

        query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        if scoped_import_batch_id:
            query = query.filter(models.RawEntity.import_batch_id == scoped_import_batch_id)
        elif scoped_domain_id and scoped_domain_id != "all":
            if scoped_domain_id == "default":
                query = query.filter(
                    (models.RawEntity.domain == scoped_domain_id)
                    | (models.RawEntity.domain == None)  # noqa: E711
                )
            else:
                query = query.filter(models.RawEntity.domain == scoped_domain_id)

        if provider:
            provider_value = provider.strip().lower()
            query = query.filter(or_(
                models.RawEntity.enrichment_source == provider_value,
                models.RawEntity.source == provider_value,
                models.RawEntity.attributes_json.contains(f'"provider": "{provider_value}"'),
            ))

        entities = query.limit(5000).all()
        patterns: list[dict[str, Any]] = []
        patterns.extend(cls._semantic_clusters(entities))
        patterns.extend(cls._impact_outliers(entities))
        patterns.extend(cls._quality_gaps(entities))
        patterns.extend(cls._provider_gaps(entities))
        patterns.extend(cls._duplicate_candidates(entities))
        patterns.extend(cls._collaboration_bridges(db, org_id, entities))

        ranked = sorted(
            patterns,
            key=lambda pattern: (
                int(pattern.get("impact_score") or 0),
                cls._confidence_rank(str(pattern.get("confidence") or "")),
                pattern.get("label") or "",
            ),
            reverse=True,
        )[:limit]

        return {
            "scope": {
                "domain_id": scoped_domain_id,
                "import_batch_id": scoped_import_batch_id,
                "provider": provider,
                "portal_slug": portal_slug,
            },
            "summary": {
                "records_analyzed": len(entities),
                "patterns_found": len(ranked),
                "highest_impact_score": max((int(p.get("impact_score") or 0) for p in ranked), default=0),
            },
            "patterns": ranked,
        }

    @staticmethod
    def _safe_json(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def _concepts(cls, entity: models.RawEntity) -> list[str]:
        attrs = cls._safe_json(entity.attributes_json)
        raw_values = [
            entity.enrichment_concepts,
            attrs.get("concepts"),
            attrs.get("keywords"),
        ]
        raw_record = attrs.get("raw_record")
        if isinstance(raw_record, dict):
            raw_values.extend([
                raw_record.get("keywords"),
                raw_record.get("concepts"),
                raw_record.get("DE"),
                raw_record.get("ID"),
            ])

        concepts: list[str] = []
        seen: set[str] = set()
        for raw in raw_values:
            if isinstance(raw, list):
                candidates = raw
            elif isinstance(raw, str):
                candidates = re.split(r"[;,|]", raw)
            else:
                candidates = []
            for candidate in candidates:
                label = str(candidate or "").strip()
                key = label.casefold()
                if label and key not in seen:
                    seen.add(key)
                    concepts.append(label)
        return concepts

    @staticmethod
    def _entity_ref(entity: models.RawEntity) -> dict[str, Any]:
        return {
            "id": entity.id,
            "label": entity.primary_label or entity.canonical_id or f"Entity #{entity.id}",
            "entity_type": entity.entity_type,
        }

    @classmethod
    def _semantic_clusters(cls, entities: list[models.RawEntity]) -> list[dict[str, Any]]:
        concept_counter: Counter[str] = Counter()
        concept_entities: dict[str, list[models.RawEntity]] = defaultdict(list)
        for entity in entities:
            for concept in cls._concepts(entity):
                key = concept.strip()
                concept_counter[key] += 1
                if len(concept_entities[key]) < 5:
                    concept_entities[key].append(entity)

        total = len(entities) or 1
        patterns = []
        for concept, count in concept_counter.most_common(3):
            if count < 2:
                continue
            share = count / total
            score = min(95, round(45 + share * 150 + math.log1p(count) * 8))
            patterns.append({
                "id": f"semantic_cluster:{cls._slug(concept)}",
                "type": "semantic_cluster",
                "label": f"Concentración temática: {concept}",
                "confidence": cls._confidence(score),
                "impact_score": score,
                "evidence": f"{count:,} registros comparten este concepto dentro del portafolio analizado.",
                "entities": [cls._entity_ref(entity) for entity in concept_entities[concept]],
                "recommended_action": "Explorar este cluster como posible lente narrativo o línea estratégica.",
            })
        return patterns

    @classmethod
    def _impact_outliers(cls, entities: list[models.RawEntity]) -> list[dict[str, Any]]:
        citation_values = [
            int(entity.enrichment_citation_count or 0)
            for entity in entities
            if int(entity.enrichment_citation_count or 0) > 0
        ]
        if len(citation_values) < 3:
            return []

        med = median(citation_values)
        deviations = [abs(value - med) for value in citation_values]
        mad = median(deviations) or 1
        threshold = med + 3 * mad
        candidates = [
            entity
            for entity in entities
            if int(entity.enrichment_citation_count or 0) >= threshold
        ]
        if not candidates:
            return []

        lead = max(candidates, key=lambda entity: int(entity.enrichment_citation_count or 0))
        citations = int(lead.enrichment_citation_count or 0)
        score = min(98, round(60 + min(30, math.log1p(citations) * 4)))
        return [{
            "id": f"impact_outlier:{lead.id}",
            "type": "impact_outlier",
            "label": "Output de impacto atípico",
            "confidence": cls._confidence(score),
            "impact_score": score,
            "evidence": f"{lead.primary_label or 'Este registro'} supera claramente la línea base de citas del portafolio ({citations:,} citas).",
            "entities": [cls._entity_ref(lead)],
            "recommended_action": "Usarlo como ancla del brief y revisar manualmente su contexto institucional.",
        }]

    @classmethod
    def _quality_gaps(cls, entities: list[models.RawEntity]) -> list[dict[str, Any]]:
        scored = [entity for entity in entities if entity.quality_score is not None]
        low = [entity for entity in scored if float(entity.quality_score or 0) < 0.45]
        if len(low) < 2:
            return []
        share = len(low) / (len(scored) or 1)
        score = min(90, round(45 + share * 100))
        weakest = sorted(low, key=lambda entity: float(entity.quality_score or 0))[:5]
        return [{
            "id": "quality_gap:low-confidence-records",
            "type": "quality_gap",
            "label": "Brecha oculta de calidad",
            "confidence": cls._confidence(score),
            "impact_score": score,
            "evidence": f"{len(low):,} registros tienen baja calidad y pueden distorsionar la lectura ejecutiva.",
            "entities": [cls._entity_ref(entity) for entity in weakest],
            "recommended_action": "Priorizar revisión de estos registros antes de compartir conclusiones externas.",
        }]

    @classmethod
    def _provider_gaps(cls, entities: list[models.RawEntity]) -> list[dict[str, Any]]:
        providers: Counter[str] = Counter()
        for entity in entities:
            attrs = cls._safe_json(entity.attributes_json)
            provider = (
                entity.enrichment_source
                or attrs.get("provider")
                or entity.source
                or "unknown"
            )
            providers[str(provider).lower()] += 1
        if len(providers) < 2:
            return []
        total = sum(providers.values()) or 1
        provider, count = providers.most_common(1)[0]
        share = count / total
        if share < 0.72:
            return []
        score = min(86, round(45 + share * 45))
        return [{
            "id": f"provider_gap:{provider}",
            "type": "provider_gap",
            "label": "Dependencia fuerte de una fuente",
            "confidence": cls._confidence(score),
            "impact_score": score,
            "evidence": f"{provider} concentra {round(share * 100)}% de los registros analizados.",
            "entities": [],
            "recommended_action": "Comparar con fuentes complementarias para reducir sesgo de cobertura.",
        }]

    @classmethod
    def _duplicate_candidates(cls, entities: list[models.RawEntity]) -> list[dict[str, Any]]:
        buckets: dict[str, list[models.RawEntity]] = defaultdict(list)
        for entity in entities:
            normalized = cls._label_key(entity.primary_label)
            if normalized:
                buckets[normalized].append(entity)

        candidates = sorted(
            (group for group in buckets.values() if len(group) >= 2),
            key=len,
            reverse=True,
        )
        if not candidates:
            return []
        group = candidates[0][:5]
        score = min(88, 50 + len(candidates[0]) * 8)
        return [{
            "id": f"duplicate_candidate:{cls._label_key(group[0].primary_label)}",
            "type": "duplicate_candidate",
            "label": "Posibles variantes duplicadas",
            "confidence": cls._confidence(score),
            "impact_score": score,
            "evidence": f"{len(candidates[0])} registros comparten una etiqueta normalizada muy similar.",
            "entities": [cls._entity_ref(entity) for entity in group],
            "recommended_action": "Revisar si deben fusionarse, normalizarse o mantenerse como variantes.",
        }]

    @classmethod
    def _collaboration_bridges(
        cls,
        db: Session,
        org_id: int | None,
        entities: list[models.RawEntity],
    ) -> list[dict[str, Any]]:
        entity_ids = {entity.id for entity in entities}
        if not entity_ids:
            return []
        rows = (
            scope_query_to_org(db.query(models.EntityRelationship), models.EntityRelationship, org_id)
            .filter(
                models.EntityRelationship.source_id.in_(entity_ids)
                | models.EntityRelationship.target_id.in_(entity_ids)
            )
            .limit(5000)
            .all()
        )
        if len(rows) < 3:
            return []
        degree: Counter[int] = Counter()
        relation_mix: Counter[str] = Counter()
        for row in rows:
            degree[row.source_id] += 1
            degree[row.target_id] += 1
            relation_mix[row.relation_type] += 1
        leader_id, leader_degree = degree.most_common(1)[0]
        leader = next((entity for entity in entities if entity.id == leader_id), None)
        if leader is None:
            return []
        score = min(92, 50 + leader_degree * 6)
        dominant_relation = relation_mix.most_common(1)[0][0]
        return [{
            "id": f"collaboration_bridge:{leader.id}",
            "type": "collaboration_bridge",
            "label": "Entidad puente en el grafo",
            "confidence": cls._confidence(score),
            "impact_score": score,
            "evidence": f"{leader.primary_label or 'Esta entidad'} concentra {leader_degree} relaciones; la relación dominante es {dominant_relation}.",
            "entities": [cls._entity_ref(leader)],
            "recommended_action": "Inspeccionar esta entidad como puente entre comunidades, autores o temas.",
        }]

    @staticmethod
    def _confidence(score: int) -> str:
        if score >= 75:
            return "high"
        if score >= 55:
            return "medium"
        return "low"

    @staticmethod
    def _confidence_rank(confidence: str) -> int:
        return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    @staticmethod
    def _label_key(value: str | None) -> str:
        if not value:
            return ""
        words = _WORD_RE.findall(value.lower())
        stop = {"the", "a", "an", "of", "and", "for", "in", "on", "de", "la", "el"}
        useful = [word for word in words if word not in stop]
        return " ".join(useful[:12])
