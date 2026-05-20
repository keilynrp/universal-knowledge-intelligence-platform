from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from itertools import combinations
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend import models
from backend.tenant_access import scope_query_to_org


MODEL_VERSION = "semantic-keyword-signal-engine-mvp-1"
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "de", "del", "el", "en", "for", "from",
    "in", "is", "la", "las", "los", "of", "on", "or", "para", "por", "the", "to", "un", "una",
    "with", "y",
}
SIGNAL_NODE_SOURCE = "semantic_keyword_signal_engine"


def _safe_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item is not None)
    text = str(value).lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9áéíóúüñ\s-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.split(r"[\s-]+", _normalize_text(text))
        if len(token) >= 3 and token not in STOPWORDS
    ]


def _ngrams(tokens: list[str], max_n: int = 4) -> set[str]:
    terms: set[str] = set()
    for n in range(1, max_n + 1):
        if len(tokens) < n:
            continue
        for idx in range(0, len(tokens) - n + 1):
            phrase_tokens = tokens[idx : idx + n]
            if all(token in STOPWORDS for token in phrase_tokens):
                continue
            terms.add(" ".join(phrase_tokens))
    return terms


def _extract_text_sources(entity: models.RawEntity, attrs: dict[str, Any]) -> dict[str, str]:
    raw_record = attrs.get("raw_record") if isinstance(attrs.get("raw_record"), dict) else {}
    return {
        "title": entity.primary_label or "",
        "abstract": (
            attrs.get("abstract")
            or attrs.get("summary")
            or attrs.get("resumen")
            or attrs.get("description")
            or raw_record.get("abstract")
            or raw_record.get("AB")
            or ""
        ),
        "keywords": attrs.get("keywords") or raw_record.get("keywords") or raw_record.get("DE") or "",
        "enrichment_concepts": entity.enrichment_concepts or "",
        "journal": attrs.get("journal") or attrs.get("source_title") or attrs.get("venue") or "",
        "document_type": attrs.get("document_type") or attrs.get("type") or "",
    }


def _external_observation_text(observation: dict[str, Any]) -> str:
    fields = [
        observation.get("title"),
        observation.get("description"),
        observation.get("snippet"),
        observation.get("summary"),
        observation.get("source_name"),
        observation.get("url"),
    ]
    return _normalize_text(" ".join(str(value) for value in fields if value))


def _external_mentions(attrs: dict[str, Any], keyword: str) -> tuple[int, set[str]]:
    raw = (
        attrs.get("external_attention_observations")
        or attrs.get("external_attention")
        or attrs.get("attention_observations")
        or []
    )
    if isinstance(raw, dict):
        raw = raw.get("observations") or raw.get("mentions") or []
    if not isinstance(raw, list):
        return 0, set()

    keyword_norm = _normalize_text(keyword)
    mentions = 0
    source_types: set[str] = set()
    for observation in raw:
        if not isinstance(observation, dict):
            continue
        text = _external_observation_text(observation)
        if keyword_norm and keyword_norm in text:
            try:
                count = int(observation.get("mention_count") or observation.get("mentions") or observation.get("count") or 1)
            except (TypeError, ValueError):
                count = 1
            mentions += max(1, count)
            source_type = str(observation.get("source_type") or "other").strip().lower().replace("-", "_")
            source_types.add(source_type or "other")
    return mentions, source_types


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _normalize_text(value)).strip("-")
    return slug[:96] or "keyword"


def _get_or_create_signal_node(
    db: Session,
    *,
    org_id: int | None,
    domain_id: str,
    label: str,
    entity_type: str,
    canonical_prefix: str,
    attrs: dict[str, Any],
) -> models.RawEntity:
    canonical_id = f"{canonical_prefix}:{_slug(label)}"
    query = db.query(models.RawEntity).filter(
        models.RawEntity.canonical_id == canonical_id,
        models.RawEntity.source == SIGNAL_NODE_SOURCE,
    )
    if org_id is None:
        query = query.filter(models.RawEntity.org_id.is_(None))
    else:
        query = query.filter(models.RawEntity.org_id == org_id)
    node = query.first()
    if node:
        existing = _safe_json(node.attributes_json)
        existing.update(attrs)
        node.attributes_json = json.dumps(existing, ensure_ascii=False, default=str)
        node.primary_label = label
        node.domain = domain_id
        return node

    node = models.RawEntity(
        org_id=org_id,
        domain=domain_id,
        entity_type=entity_type,
        primary_label=label,
        canonical_id=canonical_id,
        source=SIGNAL_NODE_SOURCE,
        validation_status="validated",
        enrichment_status="completed",
        attributes_json=json.dumps(attrs, ensure_ascii=False, default=str),
    )
    db.add(node)
    db.flush()
    return node


def _relationship_exists(
    db: Session,
    *,
    org_id: int | None,
    source_id: int,
    target_id: int,
    relation_type: str,
) -> bool:
    query = db.query(models.EntityRelationship.id).filter(
        models.EntityRelationship.source_id == source_id,
        models.EntityRelationship.target_id == target_id,
        models.EntityRelationship.relation_type == relation_type,
    )
    if org_id is None:
        query = query.filter(models.EntityRelationship.org_id.is_(None))
    else:
        query = query.filter(models.EntityRelationship.org_id == org_id)
    return query.first() is not None


def _create_signal_relationship(
    db: Session,
    *,
    org_id: int | None,
    source_id: int,
    target_id: int,
    relation_type: str,
    weight: float,
    notes: dict[str, Any],
) -> bool:
    if source_id == target_id or _relationship_exists(
        db,
        org_id=org_id,
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
    ):
        return False
    db.add(models.EntityRelationship(
        org_id=org_id,
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        weight=max(0.1, min(10.0, round(weight, 2))),
        notes=json.dumps(notes, ensure_ascii=False, default=str)[:500],
    ))
    return True


def _persist_signal_graph_relations(
    db: Session,
    *,
    org_id: int | None,
    domain_id: str,
    signals: list[dict[str, Any]],
    entity_by_id: dict[int, models.RawEntity],
) -> dict[str, int]:
    counts = {
        "keyword_nodes": 0,
        "external_signal_nodes": 0,
        "derived-keyword": 0,
        "external-signal-for": 0,
        "semantic-neighbor": 0,
        "emerging-from": 0,
    }
    keyword_nodes: dict[str, models.RawEntity] = {}
    for signal in signals:
        keyword = signal["keyword"]
        node = _get_or_create_signal_node(
            db,
            org_id=org_id,
            domain_id=domain_id,
            label=keyword,
            entity_type="semantic_keyword",
            canonical_prefix="semantic-keyword",
            attrs={
                "semantic_signal": {k: signal[k] for k in (
                    "keyword", "classification", "support_count", "external_support",
                    "opportunity_score", "source_fields", "external_source_types",
                )},
                "model_version": MODEL_VERSION,
            },
        )
        keyword_nodes[keyword] = node
        counts["keyword_nodes"] += 1
        for entity_id in signal["entity_ids"][:25]:
            source = entity_by_id.get(entity_id)
            if not source:
                continue
            created = _create_signal_relationship(
                db,
                org_id=org_id,
                source_id=source.id,
                target_id=node.id,
                relation_type="derived-keyword",
                weight=signal["opportunity_score"] / 10,
                notes={
                    "derived_by": MODEL_VERSION,
                    "keyword": keyword,
                    "source_fields": signal["source_fields"],
                },
            )
            counts["derived-keyword"] += int(created)

        if signal["external_support"] > 0:
            external_node = _get_or_create_signal_node(
                db,
                org_id=org_id,
                domain_id=domain_id,
                label=f"External support: {keyword}",
                entity_type="external_signal",
                canonical_prefix="external-signal",
                attrs={
                    "keyword": keyword,
                    "external_support": signal["external_support"],
                    "external_source_types": signal["external_source_types"],
                    "model_version": MODEL_VERSION,
                },
            )
            counts["external_signal_nodes"] += 1
            created = _create_signal_relationship(
                db,
                org_id=org_id,
                source_id=external_node.id,
                target_id=node.id,
                relation_type="external-signal-for",
                weight=min(10.0, 3 + signal["external_support"]),
                notes={
                    "derived_by": MODEL_VERSION,
                    "keyword": keyword,
                    "external_support": signal["external_support"],
                },
            )
            counts["external-signal-for"] += int(created)

    for left, right in combinations(signals[:25], 2):
        left_docs = set(left["entity_ids"])
        right_docs = set(right["entity_ids"])
        union = left_docs | right_docs
        if not union:
            continue
        overlap = len(left_docs & right_docs) / len(union)
        left_node = keyword_nodes.get(left["keyword"])
        right_node = keyword_nodes.get(right["keyword"])
        if left_node and right_node and overlap >= 0.2:
            created = _create_signal_relationship(
                db,
                org_id=org_id,
                source_id=left_node.id,
                target_id=right_node.id,
                relation_type="semantic-neighbor",
                weight=overlap * 10,
                notes={
                    "derived_by": MODEL_VERSION,
                    "shared_entity_ratio": round(overlap, 3),
                    "keywords": [left["keyword"], right["keyword"]],
                },
            )
            counts["semantic-neighbor"] += int(created)

        left_words = set(left["keyword"].split())
        right_words = set(right["keyword"].split())
        if left_node and right_node and left["classification"] == "long_tail" and right_words and right_words < left_words:
            created = _create_signal_relationship(
                db,
                org_id=org_id,
                source_id=left_node.id,
                target_id=right_node.id,
                relation_type="emerging-from",
                weight=7.0,
                notes={"derived_by": MODEL_VERSION, "emerging_keyword": left["keyword"], "base_keyword": right["keyword"]},
            )
            counts["emerging-from"] += int(created)
        elif left_node and right_node and right["classification"] == "long_tail" and left_words and left_words < right_words:
            created = _create_signal_relationship(
                db,
                org_id=org_id,
                source_id=right_node.id,
                target_id=left_node.id,
                relation_type="emerging-from",
                weight=7.0,
                notes={"derived_by": MODEL_VERSION, "emerging_keyword": right["keyword"], "base_keyword": left["keyword"]},
            )
            counts["emerging-from"] += int(created)
    return counts


def _tail_classification(term: str, support: int, doc_ratio: float, tfidf: float) -> str:
    length = len(term.split())
    if length >= 2 and (support <= 3 or tfidf >= 1.0):
        return "long_tail"
    if support >= 10 or doc_ratio >= 0.25:
        return "short_tail"
    return "mid_tail"


def materialize_keyword_signals(
    db: Session,
    domain_id: str,
    *,
    org_id: int | None,
    persist: bool = True,
    limit: int = 50,
) -> dict[str, Any]:
    query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
    if domain_id and domain_id != "all":
        if domain_id == "default":
            query = query.filter((models.RawEntity.domain == domain_id) | (models.RawEntity.domain.is_(None)))
        else:
            query = query.filter(models.RawEntity.domain == domain_id)
    entities = query.limit(2000).all()
    entity_by_id = {entity.id: entity for entity in entities}

    entity_terms: dict[int, set[str]] = {}
    entity_attrs: dict[int, dict[str, Any]] = {}
    term_tf: Counter[str] = Counter()
    term_docs: dict[str, set[int]] = defaultdict(set)
    source_fields: dict[str, set[str]] = defaultdict(set)

    for entity in entities:
        attrs = _safe_json(entity.attributes_json)
        entity_attrs[entity.id] = attrs
        terms: set[str] = set()
        for field, text in _extract_text_sources(entity, attrs).items():
            field_terms = _ngrams(_tokens(text))
            for term in field_terms:
                source_fields[term].add(field)
            terms.update(field_terms)
        if not terms:
            continue
        entity_terms[entity.id] = terms
        for term in terms:
            term_tf[term] += 1
            term_docs[term].add(entity.id)

    total_docs = max(1, len(entity_terms))
    signals = []
    for term, docs in term_docs.items():
        support = len(docs)
        if support < 1:
            continue
        idf = math.log((1 + total_docs) / (1 + support)) + 1
        tfidf = term_tf[term] * idf / total_docs
        doc_ratio = support / total_docs
        external_support = 0
        external_sources: set[str] = set()
        for entity_id in docs:
            mentions, sources = _external_mentions(entity_attrs.get(entity_id, {}), term)
            external_support += mentions
            external_sources.update(sources)
        tail = _tail_classification(term, support, doc_ratio, tfidf)
        opportunity_score = min(
            100.0,
            round((tfidf * 24) + (len(term.split()) * 5) + (external_support * 8) + (support * 2), 2),
        )
        signals.append({
            "keyword": term,
            "classification": tail,
            "support_count": support,
            "document_frequency_ratio": round(doc_ratio, 4),
            "tfidf": round(tfidf, 6),
            "external_support": external_support,
            "external_source_types": sorted(external_sources),
            "opportunity_score": opportunity_score,
            "source_fields": sorted(source_fields[term]),
            "entity_ids": sorted(docs),
            "evidence": {
                "algorithm": "tfidf_ngram_mvp",
                "model_version": MODEL_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    signals.sort(key=lambda row: (-row["opportunity_score"], row["classification"], row["keyword"]))
    top_signals = signals[:limit]

    if persist and top_signals:
        signals_by_entity: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for signal in top_signals:
            compact = {k: signal[k] for k in (
                "keyword", "classification", "support_count", "tfidf", "external_support",
                "opportunity_score", "source_fields", "evidence",
            )}
            for entity_id in signal["entity_ids"]:
                signals_by_entity[entity_id].append(compact)
        for entity in entities:
            assigned = signals_by_entity.get(entity.id)
            if not assigned:
                continue
            attrs = entity_attrs.get(entity.id, {})
            attrs["semantic_keyword_signals"] = assigned[:10]
            entity.attributes_json = json.dumps(attrs, ensure_ascii=False, default=str)
        graph_counts = _persist_signal_graph_relations(
            db,
            org_id=org_id,
            domain_id=domain_id,
            signals=top_signals,
            entity_by_id=entity_by_id,
        )
        db.commit()
    else:
        graph_counts = {}

    return {
        "domain_id": domain_id,
        "model_version": MODEL_VERSION,
        "corpus_size": len(entity_terms),
        "total_candidates": len(signals),
        "signals": top_signals,
        "graph_relations": graph_counts,
    }
