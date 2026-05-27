from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from itertools import combinations
from typing import Any

from sqlalchemy.orm import Session

from backend import models
from backend.services.entity_query import entity_base_q


_AUTHOR_NAME_KEYS = ("author_name", "authorName", "name", "display_name", "displayName")
_AUTHOR_ORCID_KEYS = ("author_orcid", "authorOrcid", "orcid", "orcid_id", "orcidId")
_AUTHOR_OPENALEX_KEYS = ("author_openalex_id", "authorOpenalexId", "openalex_id", "openalexId")
_TEXT_FIELDS = (
    "title",
    "name",
    "primary_label",
    "secondary_label",
    "abstract",
    "abstract_text",
    "summary",
    "description",
    "keywords",
    "keyword",
    "concepts",
    "enrichment_concepts",
)
_YEAR_FIELDS = ("year", "publication_year", "published_year", "publicationYear", "publishedYear")
_COUNTRY_KEYS = ("country", "country_code", "countryCode", "countries")
_INSTITUTION_KEYS = ("institution", "institution_name", "institutionName", "organization", "organization_name", "affiliation", "raw_affiliation_string")


def _parse_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_clean_text(item) for item in value if _clean_text(item)).strip()
    if isinstance(value, dict):
        return " ".join(_clean_text(v) for v in value.values() if _clean_text(v)).strip()
    return str(value).strip()


def _tokenize_query(topic: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", topic.lower()) if len(token) >= 2]


def _field_value(record: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _clean_text(record.get(key))
        if value:
            return value
    return None


def _as_author_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        records: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, dict):
                if _field_value(item, _AUTHOR_NAME_KEYS) or _field_value(item, _AUTHOR_ORCID_KEYS):
                    records.append(item)
            elif isinstance(item, str) and item.strip():
                records.append({"name": item.strip()})
        return records
    if isinstance(value, str) and value.strip():
        separators = ";" if ";" in value else ","
        return [{"name": part.strip()} for part in value.split(separators) if part.strip()]
    return []


def _extract_authors(attrs: dict[str, Any], normalized: dict[str, Any], entity: models.RawEntity) -> list[dict[str, Any]]:
    candidates = [
        normalized.get("author_affiliations"),
        normalized.get("authors"),
        normalized.get("full_authors"),
        attrs.get("author_affiliations"),
        attrs.get("authors"),
        attrs.get("full_authors"),
        attrs.get("author"),
    ]
    authors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        for record in _as_author_records(candidate):
            name = _field_value(record, _AUTHOR_NAME_KEYS)
            if not name:
                continue
            orcid = _field_value(record, _AUTHOR_ORCID_KEYS)
            openalex_id = _field_value(record, _AUTHOR_OPENALEX_KEYS)
            key = (orcid or openalex_id or name).lower()
            if key in seen:
                continue
            seen.add(key)
            authors.append({
                "name": name,
                "orcid": orcid,
                "openalex_id": openalex_id,
            })
    if not authors and entity.secondary_label:
        authors.extend(_as_author_records(entity.secondary_label))
    return authors


def _topic_text(attrs: dict[str, Any], normalized: dict[str, Any], entity: models.RawEntity) -> str:
    values: list[str] = [
        _clean_text(entity.primary_label),
        _clean_text(entity.secondary_label),
        _clean_text(entity.enrichment_concepts),
    ]
    for source in (attrs, normalized):
        for field in _TEXT_FIELDS:
            values.append(_clean_text(source.get(field)))
        raw_record = source.get("raw_record")
        if isinstance(raw_record, dict):
            for field in _TEXT_FIELDS:
                values.append(_clean_text(raw_record.get(field)))
    return " ".join(value for value in values if value).lower()


def _topic_match_score(topic: str, searchable_text: str) -> float:
    topic_normalized = topic.strip().lower()
    if not topic_normalized:
        return 0.0
    exact = 1.0 if topic_normalized in searchable_text else 0.0
    tokens = _tokenize_query(topic)
    if not tokens:
        return exact
    token_hits = sum(1 for token in tokens if token in searchable_text)
    token_score = token_hits / len(tokens)
    return max(exact, token_score * 0.75)


def _extract_year(attrs: dict[str, Any], normalized: dict[str, Any], entity: models.RawEntity) -> int | None:
    for source in (attrs, normalized):
        for field in _YEAR_FIELDS:
            value = source.get(field)
            if isinstance(value, int) and 1800 <= value <= 2100:
                return value
            if isinstance(value, str):
                match = re.search(r"\b(18|19|20)\d{2}\b", value)
                if match:
                    return int(match.group(0))
        raw_record = source.get("raw_record")
        if isinstance(raw_record, dict):
            for field in _YEAR_FIELDS:
                value = raw_record.get(field)
                if isinstance(value, int) and 1800 <= value <= 2100:
                    return value
                if isinstance(value, str):
                    match = re.search(r"\b(18|19|20)\d{2}\b", value)
                    if match:
                        return int(match.group(0))
    timestamp = getattr(entity, "created_at", None) or getattr(entity, "updated_at", None)
    if timestamp:
        return timestamp.year
    return None


def _source_text(attrs: dict[str, Any], normalized: dict[str, Any], entity: models.RawEntity) -> str:
    values = [
        entity.enrichment_source,
        attrs.get("source"),
        attrs.get("provider"),
        attrs.get("source_name"),
        normalized.get("source"),
        normalized.get("provider"),
    ]
    return _clean_text(values).lower()


def _field_text(attrs: dict[str, Any], normalized: dict[str, Any], keys: tuple[str, ...]) -> str:
    values: list[Any] = []
    for source in (attrs, normalized):
        for key in keys:
            values.append(source.get(key))
        for container_key in ("author_affiliations", "affiliations", "institutions", "normalized_affiliations"):
            container = source.get(container_key)
            if isinstance(container, list):
                for item in container:
                    if isinstance(item, dict):
                        for key in keys:
                            values.append(item.get(key))
            elif isinstance(container, dict):
                for key in keys:
                    values.append(container.get(key))
    return _clean_text(values).lower()


def _matches_filters(
    attrs: dict[str, Any],
    normalized: dict[str, Any],
    entity: models.RawEntity,
    *,
    source: str | None,
    year_from: int | None,
    year_to: int | None,
    country: str | None,
    institution: str | None,
    min_citations: int,
) -> bool:
    citations = int(entity.enrichment_citation_count or 0)
    if citations < min_citations:
        return False
    year = _extract_year(attrs, normalized, entity)
    if year_from is not None and (year is None or year < year_from):
        return False
    if year_to is not None and (year is None or year > year_to):
        return False
    if source and source.lower() not in _source_text(attrs, normalized, entity):
        return False
    if country and country.lower() not in _field_text(attrs, normalized, _COUNTRY_KEYS):
        return False
    if institution and institution.lower() not in _field_text(attrs, normalized, _INSTITUTION_KEYS):
        return False
    return True


def _evidence_item(entity: models.RawEntity) -> dict[str, Any]:
    return {
        "entity_id": entity.id,
        "title": entity.primary_label,
        "secondary_label": entity.secondary_label,
        "citations": entity.enrichment_citation_count or 0,
    }


def _executive_summary(
    *,
    topic: str,
    records_analyzed: int,
    ranked: list[dict[str, Any]],
    relationship_count: int | None = None,
) -> dict[str, Any]:
    top = ranked[0] if ranked else None
    high_confidence = sum(1 for item in ranked if int(item.get("topic_score") or 0) >= 70)
    total_citations = sum(int(item.get("citation_count") or 0) for item in ranked)
    coverage = min(100, records_analyzed * 10)
    density = min(100, int((relationship_count or 0) / max(len(ranked), 1) * 20)) if relationship_count is not None else None
    confidence = round(
        min(
            100,
            (coverage * 0.35)
            + (min(100, len(ranked) * 8) * 0.25)
            + (min(100, high_confidence * 20) * 0.25)
            + (min(100, math.log1p(total_citations) / math.log1p(10000) * 100) * 0.15),
        )
    )
    return {
        "topic": topic,
        "confidence": confidence,
        "coverage_score": coverage,
        "network_density_score": density,
        "high_confidence_researchers": high_confidence,
        "total_citations": total_citations,
        "top_researcher": top,
        "headline": (
            f"{top['name']} lidera la evidencia sobre {topic} con score {top['topic_score']}."
            if top
            else f"No hay suficiente evidencia para mapear investigadores sobre {topic}."
        ),
        "stakeholder_value": (
            "Mapa accionable de expertos y colaboraciones listo para briefing."
            if confidence >= 70
            else "Senal preliminar: conviene validar fuentes, filtros y cobertura antes de usarlo en decisiones."
        ),
    }


def researchers_by_topic(
    db: Session,
    *,
    domain_id: str,
    org_id: int | None,
    topic: str,
    limit: int = 25,
    source: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    country: str | None = None,
    institution: str | None = None,
    min_citations: int = 0,
) -> dict[str, Any]:
    query = entity_base_q(db, domain_id, org_id).order_by(models.RawEntity.id.asc()).limit(3000)
    rows = query.all()
    researchers: dict[str, dict[str, Any]] = {}
    records_analyzed = 0

    for entity in rows:
        attrs = _parse_json(entity.attributes_json)
        normalized = _parse_json(entity.normalized_json)
        if not _matches_filters(
            attrs,
            normalized,
            entity,
            source=source,
            year_from=year_from,
            year_to=year_to,
            country=country,
            institution=institution,
            min_citations=min_citations,
        ):
            continue
        match_score = _topic_match_score(topic, _topic_text(attrs, normalized, entity))
        if match_score <= 0:
            continue
        authors = _extract_authors(attrs, normalized, entity)
        if not authors:
            continue
        records_analyzed += 1
        citations = int(entity.enrichment_citation_count or 0)
        citation_signal = min(100.0, math.log1p(citations) / math.log1p(5000) * 100.0)
        year = _extract_year(attrs, normalized, entity)
        recency_signal = 50.0
        if year:
            recency_signal = max(20.0, min(100.0, 100.0 - max(0, 2026 - year) * 6.0))
        quality_signal = (
            25.0
            + (20.0 if entity.enrichment_status == "completed" else 0.0)
            + (20.0 if entity.enrichment_source else 0.0)
            + (20.0 if _clean_text(entity.enrichment_concepts) else 0.0)
            + (15.0 if citations > 0 else 0.0)
        )
        for author in authors:
            key = (author.get("orcid") or author.get("openalex_id") or author["name"]).lower()
            researcher = researchers.setdefault(key, {
                "name": author["name"],
                "orcid": author.get("orcid"),
                "openalex_id": author.get("openalex_id"),
                "records_count": 0,
                "citation_count": 0,
                "topic_score_raw": 0.0,
                "match_total": 0.0,
                "citation_signal_total": 0.0,
                "recency_signal_total": 0.0,
                "quality_signal_total": 0.0,
                "evidence": [],
            })
            authority_signal = 100.0 if researcher["orcid"] and researcher["openalex_id"] else 85.0 if researcher["orcid"] or researcher["openalex_id"] else 45.0
            researcher["records_count"] += 1
            researcher["citation_count"] += citations
            researcher["match_total"] += match_score * 100.0
            researcher["citation_signal_total"] += citation_signal
            researcher["recency_signal_total"] += recency_signal
            researcher["quality_signal_total"] += quality_signal
            researcher["topic_score_raw"] += (
                match_score * 42.0
                + min(30.0, math.log1p(researcher["records_count"]) / math.log1p(12) * 30.0)
                + citation_signal * 0.14
                + recency_signal * 0.07
                + authority_signal * 0.04
                + quality_signal * 0.03
            )
            if len(researcher["evidence"]) < 5:
                researcher["evidence"].append(_evidence_item(entity))

    ranked = []
    max_raw = max((item["topic_score_raw"] for item in researchers.values()), default=1.0)
    for researcher in researchers.values():
        count = max(int(researcher["records_count"]), 1)
        drivers = {
            "topic_match": round(researcher["match_total"] / count),
            "publication_signal": round(min(100.0, math.log1p(researcher["records_count"]) / math.log1p(12) * 100.0)),
            "citation_signal": round(researcher["citation_signal_total"] / count),
            "recency_signal": round(researcher["recency_signal_total"] / count),
            "authority_signal": 100 if researcher["orcid"] and researcher["openalex_id"] else 85 if researcher["orcid"] or researcher["openalex_id"] else 45,
            "quality_signal": round(researcher["quality_signal_total"] / count),
        }
        ranked.append({
            "name": researcher["name"],
            "orcid": researcher["orcid"],
            "openalex_id": researcher["openalex_id"],
            "records_count": researcher["records_count"],
            "citation_count": researcher["citation_count"],
            "topic_score": round((researcher["topic_score_raw"] / max_raw) * 100),
            "drivers": drivers,
            "evidence": researcher["evidence"],
        })
    ranked.sort(key=lambda item: (item["topic_score"], item["records_count"], item["citation_count"]), reverse=True)
    return {
        "domain_id": domain_id,
        "topic": topic,
        "filters": {
            "source": source,
            "year_from": year_from,
            "year_to": year_to,
            "country": country,
            "institution": institution,
            "min_citations": min_citations,
        },
        "records_analyzed": records_analyzed,
        "researcher_count": len(ranked),
        "researchers": ranked[:limit],
        "executive_summary": _executive_summary(topic=topic, records_analyzed=records_analyzed, ranked=ranked[:limit]),
    }


def topic_researcher_graph(
    db: Session,
    *,
    domain_id: str,
    org_id: int | None,
    topic: str,
    limit: int = 50,
    min_weight: int = 1,
    source: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    country: str | None = None,
    institution: str | None = None,
    min_citations: int = 0,
) -> dict[str, Any]:
    ranking = researchers_by_topic(
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
    allowed = {
        (item.get("orcid") or item.get("openalex_id") or item["name"]).lower()
        for item in ranking["researchers"]
    }
    nodes: dict[str, dict[str, Any]] = {
        f"topic:{topic.lower()}": {"id": f"topic:{topic.lower()}", "type": "topic", "label": topic, "score": 100}
    }
    edges_counter: Counter[tuple[str, str, str]] = Counter()
    author_scores = {
        (item.get("orcid") or item.get("openalex_id") or item["name"]).lower(): item["topic_score"]
        for item in ranking["researchers"]
    }

    for item in ranking["researchers"]:
        node_id = item.get("orcid") or item.get("openalex_id") or item["name"]
        nodes[node_id] = {
            "id": node_id,
            "type": "researcher",
            "label": item["name"],
            "orcid": item.get("orcid"),
            "openalex_id": item.get("openalex_id"),
            "score": item["topic_score"],
            "records_count": item["records_count"],
            "citation_count": item["citation_count"],
        }
        edges_counter[(node_id, f"topic:{topic.lower()}", "works_on_topic")] += item["records_count"]

    query = entity_base_q(db, domain_id, org_id).order_by(models.RawEntity.id.asc()).limit(3000)
    for entity in query.all():
        attrs = _parse_json(entity.attributes_json)
        normalized = _parse_json(entity.normalized_json)
        if not _matches_filters(
            attrs,
            normalized,
            entity,
            source=source,
            year_from=year_from,
            year_to=year_to,
            country=country,
            institution=institution,
            min_citations=min_citations,
        ):
            continue
        if _topic_match_score(topic, _topic_text(attrs, normalized, entity)) <= 0:
            continue
        authors = []
        for author in _extract_authors(attrs, normalized, entity):
            author_id = author.get("orcid") or author.get("openalex_id") or author["name"]
            if author_id.lower() in allowed:
                authors.append(author_id)
        for edge_source, edge_target in combinations(sorted(set(authors)), 2):
            edges_counter[(edge_source, edge_target, "coauthor_with")] += 1

    edges = [
        {"source": source, "target": target, "type": relation, "weight": weight}
        for (source, target, relation), weight in edges_counter.items()
        if weight >= min_weight
    ]
    edges.sort(key=lambda item: item["weight"], reverse=True)
    return {
        "domain_id": domain_id,
        "topic": topic,
        "nodes": sorted(nodes.values(), key=lambda item: (item["type"] != "topic", -int(item.get("score") or 0), item["label"])),
        "edges": edges,
        "summary": {
            "researcher_count": len(ranking["researchers"]),
            "relationship_count": len(edges),
            "records_analyzed": ranking["records_analyzed"],
            "top_researcher": ranking["researchers"][0] if ranking["researchers"] else None,
            "executive_summary": _executive_summary(
                topic=topic,
                records_analyzed=ranking["records_analyzed"],
                ranked=ranking["researchers"],
                relationship_count=len(edges),
            ),
        },
        "scoring": {
            "topic_score": "Normaliza coincidencia tema-texto, cantidad de registros y señal de citas a una escala 0-100.",
            "coauthor_weight": "Número de registros del tema en los que aparece el par de investigadores.",
        },
    }
