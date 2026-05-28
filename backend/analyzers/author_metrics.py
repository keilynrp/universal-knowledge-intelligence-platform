"""
Author Productivity & H-index analyzer.

Computes per-author bibliometric metrics from AuthorityRecord + RawEntity data:
- H-index
- Total publications, total citations, average citations
- Publications per year timeline
"""
from __future__ import annotations

import json
import logging
import zlib
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import text

from backend.analyzers.topic_modeling import _extract_record_year, _validate_domain
from backend.database import engine
from backend.tenant_access import add_org_sql_filter

logger = logging.getLogger(__name__)


_AUTHOR_NAME_KEYS = ("name", "author_name", "display_name", "full_name")


def compute_h_index(citation_counts: list[int]) -> int:
    """Compute h-index: largest h such that at least h papers have >= h citations."""
    sorted_counts = sorted(citation_counts, reverse=True)
    h = 0
    for i, c in enumerate(sorted_counts):
        if c >= i + 1:
            h = i + 1
    return h


def _author_record_id(author_name: str) -> int:
    """Return a deterministic synthetic ID for authors without authority records."""
    return -int(zlib.crc32(author_name.casefold().encode("utf-8")))


def _author_names_from_payload(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        separator = ";" if ";" in raw else ","
        return [part.strip() for part in raw.replace("|", separator).split(separator) if part.strip()]
    if isinstance(raw, dict):
        name = next((raw.get(key) for key in _AUTHOR_NAME_KEYS if raw.get(key)), None)
        return [str(name).strip()] if name and str(name).strip() else []
    if isinstance(raw, list):
        authors: list[str] = []
        for item in raw:
            authors.extend(_author_names_from_payload(item))
        return list(dict.fromkeys(authors))
    return []


def _extract_author_names(attrs_json: str | None, secondary_label: str | None) -> list[str]:
    attrs: dict[str, Any] = {}
    if attrs_json:
        try:
            parsed = json.loads(attrs_json) or {}
            if isinstance(parsed, dict):
                attrs = parsed
        except (ValueError, TypeError):
            attrs = {}

    candidates: list[Any] = [
        attrs.get("canonical_authors"),
        attrs.get("enrichment_authors"),
        attrs.get("author_affiliations"),
        attrs.get("authors"),
        attrs.get("full_authors"),
        attrs.get("author"),
    ]
    raw_record = attrs.get("raw_record")
    if isinstance(raw_record, dict):
        candidates.extend([
            raw_record.get("authors"),
            raw_record.get("author"),
            raw_record.get("AU"),
            raw_record.get("AF"),
        ])
    candidates.append(secondary_label)

    authors: list[str] = []
    for candidate in candidates:
        for name in _author_names_from_payload(candidate):
            if name not in authors:
                authors.append(name)
    return authors


def _load_author_entities(domain_id: str, org_id: int | None = None) -> list[dict[str, Any]]:
    """
    Load entities with their authority-linked authors.
    Joins authority_records (field_name='author', status='confirmed') with raw_entities.
    """
    where_clauses = ["1 = 1"]
    params: dict[str, object] = {}

    if domain_id not in ("all", "default"):
        where_clauses.append("re.domain = :domain_id")
        params["domain_id"] = domain_id
    elif domain_id == "default":
        where_clauses.append("(re.domain = :domain_id OR re.domain IS NULL)")
        params["domain_id"] = domain_id

    add_org_sql_filter(where_clauses, params, org_id, column_name="re.org_id")

    sql = f"""
        SELECT
            re.id AS entity_id,
            re.enrichment_citation_count,
            re.attributes_json,
            re.primary_label,
            re.secondary_label
        FROM raw_entities re
        WHERE {' AND '.join(where_clauses)}
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    expanded: list[dict[str, Any]] = []
    for row in rows:
        row_dict = dict(row._mapping)
        for author_name in _extract_author_names(
            row_dict.get("attributes_json"),
            row_dict.get("secondary_label"),
        ):
            expanded.append({
                **row_dict,
                "record_id": _author_record_id(author_name),
                "canonical_label": author_name,
                "original_value": author_name,
            })
    return expanded


def author_rankings(
    domain_id: str,
    *,
    sort_by: str = "h_index",
    limit: int = 20,
    org_id: int | None = None,
) -> dict[str, Any]:
    """Return ranked list of authors with productivity metrics."""
    _validate_domain(domain_id, org_id=org_id)

    rows = _load_author_entities(domain_id, org_id=org_id)
    if not rows:
        return {
            "domain_id": domain_id,
            "total_analyzed": 0,
            "authors": [],
        }

    # Group entities by author (canonical_label)
    author_data: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "record_id": None,
        "citations": [],
        "entity_ids": set(),
        "years": Counter(),
    })

    for row in rows:
        label = row["canonical_label"]
        entity_id = row["entity_id"]
        data = author_data[label]
        if data["record_id"] is None:
            data["record_id"] = row["record_id"]

        if entity_id in data["entity_ids"]:
            continue
        data["entity_ids"].add(entity_id)

        citations = row["enrichment_citation_count"] or 0
        data["citations"].append(citations)

        year = _extract_record_year(
            row.get("attributes_json"),
            row.get("primary_label"),
            row.get("secondary_label"),
        )
        if year is not None:
            data["years"][year] += 1

    # Compute metrics per author
    authors: list[dict[str, Any]] = []
    for label, data in author_data.items():
        citation_list = data["citations"]
        total_pubs = len(citation_list)
        total_citations = sum(citation_list)
        h = compute_h_index(citation_list)
        avg_citations = round(total_citations / total_pubs, 2) if total_pubs else 0.0

        authors.append({
            "canonical_label": label,
            "record_id": data["record_id"],
            "h_index": h,
            "total_publications": total_pubs,
            "total_citations": total_citations,
            "avg_citations": avg_citations,
            "publications_per_year": dict(sorted(data["years"].items())),
        })

    # Sort
    valid_sorts = {"h_index", "total_publications", "total_citations"}
    sort_key = sort_by if sort_by in valid_sorts else "h_index"
    authors.sort(key=lambda a: a[sort_key], reverse=True)
    authors = authors[:limit]

    return {
        "domain_id": domain_id,
        "total_analyzed": len(author_data),
        "authors": authors,
    }


def author_detail(
    domain_id: str,
    record_id: int,
    *,
    org_id: int | None = None,
) -> dict[str, Any] | None:
    """Return full productivity detail for a single author by authority record ID."""
    _validate_domain(domain_id, org_id=org_id)

    rows = _load_author_entities(domain_id, org_id=org_id)
    # Filter to target record_id
    author_rows = [r for r in rows if r["record_id"] == record_id]
    if not author_rows:
        return None

    label = author_rows[0]["canonical_label"]
    citation_list: list[int] = []
    years: Counter[int] = Counter()
    entity_ids: set[int] = set()
    top_entities: list[dict[str, Any]] = []

    for row in author_rows:
        eid = row["entity_id"]
        if eid in entity_ids:
            continue
        entity_ids.add(eid)
        citations = row["enrichment_citation_count"] or 0
        citation_list.append(citations)

        year = _extract_record_year(
            row.get("attributes_json"),
            row.get("primary_label"),
            row.get("secondary_label"),
        )
        if year is not None:
            years[year] += 1

        top_entities.append({
            "entity_id": eid,
            "primary_label": row.get("primary_label"),
            "citations": citations,
        })

    total_pubs = len(citation_list)
    total_citations = sum(citation_list)
    h = compute_h_index(citation_list)
    avg_citations = round(total_citations / total_pubs, 2) if total_pubs else 0.0

    # Top-cited entities (up to 10)
    top_entities.sort(key=lambda e: e["citations"], reverse=True)
    top_entities = top_entities[:10]

    return {
        "record_id": record_id,
        "canonical_label": label,
        "domain_id": domain_id,
        "h_index": h,
        "total_publications": total_pubs,
        "total_citations": total_citations,
        "avg_citations": avg_citations,
        "publications_per_year": dict(sorted(years.items())),
        "top_entities": top_entities,
    }
