"""Pure OpenAlex-work -> normalized rows.

No I/O, no DuckDB: given one work dict (from the API or the snapshot — same
shape), return the fact/dim rows it contributes. This is the analytical core and
is exhaustively unit-tested; the puller and snapshot loader are thin I/O around
it.
"""
from __future__ import annotations

from typing import Any, Optional


def _short_id(url: Optional[str]) -> Optional[str]:
    """OpenAlex ids are URLs ('https://openalex.org/W123'); keep the tail."""
    if not url or not isinstance(url, str):
        return None
    return url.rstrip("/").rsplit("/", 1)[-1] or None


def _bare_doi(doi: Optional[str]) -> Optional[str]:
    if not doi or not isinstance(doi, str):
        return None
    return doi.replace("https://doi.org/", "").replace("http://doi.org/", "").lower() or None


def _bare_orcid(orcid: Optional[str]) -> Optional[str]:
    if not orcid or not isinstance(orcid, str):
        return None
    return orcid.replace("https://orcid.org/", "").replace("http://orcid.org/", "") or None


def _bare_ror(ror: Optional[str]) -> Optional[str]:
    if not ror or not isinstance(ror, str):
        return None
    return ror.replace("https://ror.org/", "").replace("http://ror.org/", "") or None


def _field_int(field_obj: Optional[dict]) -> Optional[int]:
    """OpenAlex field id is a URL '.../fields/27'; return the int."""
    short = _short_id((field_obj or {}).get("id"))
    if short and short.isdigit():
        return int(short)
    return None


def _topic_facets(topic: dict) -> dict[str, Any]:
    field_obj = topic.get("field") or {}
    domain_obj = topic.get("domain") or {}
    subfield_obj = topic.get("subfield") or {}
    return {
        "subfield": subfield_obj.get("display_name"),
        "field_id": _field_int(field_obj),
        "field": field_obj.get("display_name"),
        "domain": domain_obj.get("display_name"),
    }


def transform_source(rec: dict) -> Optional[dict]:
    """OpenAlex source snapshot record -> dim_source row."""
    source_id = _short_id(rec.get("id"))
    if not source_id:
        return None
    return {
        "source_id": source_id,
        "issn_l": rec.get("issn_l"),
        "display_name": rec.get("display_name"),
        "host_org": rec.get("host_organization_name"),
        "is_in_doaj": rec.get("is_in_doaj"),
        "type": rec.get("type"),
        "country_code": rec.get("country_code"),
    }


def transform_institution(rec: dict) -> Optional[dict]:
    """OpenAlex institution snapshot record -> dim_institution row."""
    institution_id = _short_id(rec.get("id"))
    if not institution_id:
        return None
    return {
        "institution_id": institution_id,
        "ror": _bare_ror(rec.get("ror")),
        "display_name": rec.get("display_name"),
        "country_code": rec.get("country_code"),
        "type": rec.get("type"),
    }


def transform_topic(rec: dict) -> Optional[dict]:
    """OpenAlex topic snapshot record -> dim_topic row."""
    topic_id = _short_id(rec.get("id"))
    if not topic_id:
        return None
    facets = _topic_facets(rec)
    return {
        "topic_id": topic_id,
        "display_name": rec.get("display_name"),
        "subfield": facets.get("subfield"),
        "field_id": facets.get("field_id"),
        "field": facets.get("field"),
        "domain": facets.get("domain"),
    }


# Dimension entity -> (transform fn, target table).
DIMENSION_TRANSFORMS = {
    "sources": (transform_source, "dim_source"),
    "institutions": (transform_institution, "dim_institution"),
    "topics": (transform_topic, "dim_topic"),
}


def transform_work(work: dict, *, include_citations: bool = False) -> dict[str, list[dict]]:
    """Return {table_name: [row, ...]} for a single OpenAlex work.

    Missing/partial fields are tolerated (snapshot works are frequently sparse).
    Derived dimension rows (author/institution/topic/source) are emitted so the
    lake is queryable before the full snapshot dimensions are loaded.
    """
    rows: dict[str, list[dict]] = {
        "fact_works": [],
        "fact_work_counts_by_year": [],
        "fact_authorship": [],
        "fact_work_topic": [],
        "fact_citation": [],
        "dim_source": [],
        "dim_institution": [],
        "dim_author": [],
        "dim_topic": [],
    }

    work_id = _short_id(work.get("id"))
    if not work_id:
        return rows  # unusable without an id

    source = ((work.get("primary_location") or {}).get("source")) or {}
    source_id = _short_id(source.get("id"))
    source_issn_l = source.get("issn_l")

    primary_topic = work.get("primary_topic") or {}
    p_facets = _topic_facets(primary_topic) if primary_topic else {}
    open_access = work.get("open_access") or {}
    referenced = [r for r in (work.get("referenced_works") or []) if r]

    rows["fact_works"].append({
        "work_id": work_id,
        "doi": _bare_doi(work.get("doi")),
        "title": work.get("title") or work.get("display_name"),
        "publication_year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "type": work.get("type"),
        "source_issn_l": source_issn_l,
        "source_id": source_id,
        "cited_by_count": work.get("cited_by_count"),
        "is_oa": open_access.get("is_oa"),
        "oa_status": open_access.get("oa_status"),
        "primary_topic_id": _short_id(primary_topic.get("id")),
        "field_id": p_facets.get("field_id"),
        "field": p_facets.get("field"),
        "domain": p_facets.get("domain"),
        "referenced_count": len(referenced),
        "updated_date": work.get("updated_date"),
    })

    # Derive a minimal source dim from the work (snapshot sync will enrich it).
    if source_id:
        rows["dim_source"].append({
            "source_id": source_id,
            "issn_l": source_issn_l,
            "display_name": source.get("display_name"),
            "host_org": source.get("host_organization_name"),
            "is_in_doaj": source.get("is_in_doaj"),
            "type": source.get("type"),
            "country_code": source.get("country_code"),
        })

    for c in work.get("counts_by_year") or []:
        year = c.get("year")
        if year is None:
            continue
        rows["fact_work_counts_by_year"].append({
            "work_id": work_id,
            "year": year,
            "cited_by_count": c.get("cited_by_count"),
        })

    seen_authorship: set[tuple] = set()
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        author_id = _short_id(author.get("id"))
        if not author_id:
            continue
        orcid = _bare_orcid(author.get("orcid"))
        rows["dim_author"].append({
            "author_id": author_id,
            "orcid": orcid,
            "display_name": author.get("display_name"),
        })
        institutions = authorship.get("institutions") or [{}]
        position = authorship.get("author_position")
        for inst in institutions:
            institution_id = _short_id(inst.get("id")) or ""
            key = (work_id, author_id, institution_id)
            if key in seen_authorship:
                continue
            seen_authorship.add(key)
            rows["fact_authorship"].append({
                "work_id": work_id,
                "author_position": position,
                "author_id": author_id,
                "orcid": orcid,
                "institution_ror": _bare_ror(inst.get("ror")),
                "institution_id": institution_id,
                "country_code": inst.get("country_code"),
            })
            if institution_id:
                rows["dim_institution"].append({
                    "institution_id": institution_id,
                    "ror": _bare_ror(inst.get("ror")),
                    "display_name": inst.get("display_name"),
                    "country_code": inst.get("country_code"),
                    "type": inst.get("type"),
                })

    primary_topic_id = _short_id(primary_topic.get("id"))
    for topic in work.get("topics") or []:
        topic_id = _short_id(topic.get("id"))
        if not topic_id:
            continue
        rows["fact_work_topic"].append({
            "work_id": work_id,
            "topic_id": topic_id,
            "score": topic.get("score"),
            "is_primary": topic_id == primary_topic_id,
        })
        facets = _topic_facets(topic)
        rows["dim_topic"].append({
            "topic_id": topic_id,
            "display_name": topic.get("display_name"),
            "subfield": facets.get("subfield"),
            "field_id": facets.get("field_id"),
            "field": facets.get("field"),
            "domain": facets.get("domain"),
        })

    if include_citations:
        for ref in referenced:
            ref_id = _short_id(ref)
            if ref_id:
                rows["fact_citation"].append({
                    "work_id": work_id,
                    "referenced_work_id": ref_id,
                })

    return rows
