"""
Geographic / Country analysis — extract country from affiliations,
aggregate per-country metrics, compute international collaboration rates.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import text

from backend.analyzers.topic_modeling import _validate_domain
from backend.database import engine
from backend.tenant_access import add_org_sql_filter

logger = logging.getLogger(__name__)

# ISO 3166-1 alpha-2 lookup: country name / abbreviation → code
# Covers official names + common abbreviations
_COUNTRY_MAP: dict[str, str] = {
    # Major countries with common abbreviations
    "united states": "US", "united states of america": "US", "usa": "US", "u.s.a.": "US", "u.s.": "US",
    "united kingdom": "GB", "uk": "GB", "u.k.": "GB", "england": "GB", "scotland": "GB", "wales": "GB",
    "china": "CN", "prc": "CN", "p.r. china": "CN", "p.r.china": "CN", "peoples republic of china": "CN",
    "japan": "JP", "germany": "DE", "france": "FR", "italy": "IT", "spain": "ES",
    "canada": "CA", "australia": "AU", "brazil": "BR", "india": "IN", "russia": "RU",
    "russian federation": "RU", "south korea": "KR", "republic of korea": "KR", "rok": "KR", "korea": "KR",
    "north korea": "KP", "dprk": "KP",
    "mexico": "MX", "netherlands": "NL", "holland": "NL", "belgium": "BE",
    "switzerland": "CH", "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI",
    "austria": "AT", "portugal": "PT", "greece": "GR", "poland": "PL", "czech republic": "CZ",
    "czechia": "CZ", "hungary": "HU", "romania": "RO", "ireland": "IE", "new zealand": "NZ",
    "singapore": "SG", "malaysia": "MY", "thailand": "TH", "indonesia": "ID", "philippines": "PH",
    "vietnam": "VN", "taiwan": "TW", "roc": "TW", "hong kong": "HK", "saudi arabia": "SA",
    "uae": "AE", "united arab emirates": "AE", "israel": "IL", "turkey": "TR", "turkiye": "TR",
    "egypt": "EG", "south africa": "ZA", "nigeria": "NG", "kenya": "KE", "morocco": "MA",
    "argentina": "AR", "chile": "CL", "colombia": "CO", "peru": "PE", "venezuela": "VE",
    "cuba": "CU", "iran": "IR", "iraq": "IQ", "pakistan": "PK", "bangladesh": "BD",
    "sri lanka": "LK", "nepal": "NP", "ukraine": "UA", "croatia": "HR", "serbia": "RS",
    "slovenia": "SI", "slovakia": "SK", "bulgaria": "BG", "estonia": "EE", "latvia": "LV",
    "lithuania": "LT", "luxembourg": "LU", "iceland": "IS", "malta": "MT", "cyprus": "CY",
    "qatar": "QA", "kuwait": "KW", "oman": "OM", "bahrain": "BH", "jordan": "JO", "lebanon": "LB",
    "ethiopia": "ET", "ghana": "GH", "tanzania": "TZ", "uganda": "UG", "cameroon": "CM",
    "senegal": "SN", "tunisia": "TN", "algeria": "DZ", "libya": "LY", "sudan": "SD",
    "ecuador": "EC", "uruguay": "UY", "paraguay": "PY", "bolivia": "BO", "costa rica": "CR",
    "panama": "PA", "dominican republic": "DO", "guatemala": "GT", "honduras": "HN",
    "el salvador": "SV", "nicaragua": "NI", "jamaica": "JM", "trinidad and tobago": "TT",
    "puerto rico": "PR",
}

# Reverse map: code → name (for display)
_CODE_TO_NAME: dict[str, str] = {}
for _name, _code in _COUNTRY_MAP.items():
    if _code not in _CODE_TO_NAME:
        # Use the longest name as the canonical display name
        _CODE_TO_NAME[_code] = _name.title()
# Override with cleaner names
_CODE_TO_NAME.update({
    "US": "United States", "GB": "United Kingdom", "CN": "China",
    "KR": "South Korea", "TW": "Taiwan", "HK": "Hong Kong",
    "RU": "Russia", "AE": "United Arab Emirates", "CZ": "Czech Republic",
    "NL": "Netherlands", "NZ": "New Zealand", "SA": "Saudi Arabia",
    "ZA": "South Africa", "TR": "Turkey",
})


def extract_country(affiliation: str | None) -> str | None:
    """
    Extract ISO alpha-2 country code from an affiliation string.
    Strategy: check each comma-separated segment against the lookup table,
    starting from the last segment (most likely to be the country).
    """
    if not affiliation:
        return None

    segments = [s.strip() for s in affiliation.split(",")]
    # Check from last to first (country is typically last)
    for segment in reversed(segments):
        normalized = segment.strip().lower()
        # Remove trailing periods and parenthetical content
        normalized = re.sub(r"\s*\(.*?\)\s*", "", normalized).strip().rstrip(".")
        if normalized in _COUNTRY_MAP:
            return _COUNTRY_MAP[normalized]

    # Fallback: check if any segment contains a country name
    full_text = affiliation.lower()
    for name, code in _COUNTRY_MAP.items():
        if len(name) > 3 and name in full_text:
            return code

    return None


def _load_entities_with_affiliations(
    domain_id: str, org_id: int | None = None,
) -> list[dict[str, Any]]:
    """Load entities with attributes_json for country extraction."""
    where_clauses: list[str] = []
    params: dict[str, object] = {}

    if domain_id not in ("all",):
        if domain_id == "default":
            where_clauses.append("(domain = :domain_id OR domain IS NULL)")
        else:
            where_clauses.append("domain = :domain_id")
        params["domain_id"] = domain_id
    add_org_sql_filter(where_clauses, params, org_id)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    sql = f"""
        SELECT id, attributes_json, enrichment_citation_count, primary_label
        FROM raw_entities
        {where_sql}
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return [dict(row._mapping) for row in rows]


def _get_affiliation_from_attrs(attributes_json: str | None) -> str | None:
    """Extract affiliation string from attributes_json."""
    if not attributes_json:
        return None
    try:
        attrs = json.loads(attributes_json)
    except (ValueError, TypeError):
        return None
    if not isinstance(attrs, dict):
        return None

    # Check common field names for affiliation
    for key in ("affiliation", "affiliations", "institution", "institutions", "organization"):
        val = attrs.get(key)
        if val:
            if isinstance(val, str):
                return val
            if isinstance(val, list):
                return "; ".join(str(v) for v in val if v)
            if isinstance(val, dict):
                return val.get("name") or val.get("display_name") or str(val)
    return None


def _get_structured_countries(attributes_json: str | None) -> set[str]:
    """Extract country codes from structured canonical affiliation metadata."""
    if not attributes_json:
        return set()
    try:
        attrs = json.loads(attributes_json)
    except (ValueError, TypeError):
        return set()
    if not isinstance(attrs, dict):
        return set()

    countries: set[str] = set()
    for affiliation in attrs.get("canonical_affiliations") or []:
        if not isinstance(affiliation, dict):
            continue
        code = affiliation.get("country_code")
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z]{2}", code.strip()):
            countries.add(code.strip().upper())
    return countries


def _get_extracted_country(attributes_json: str | None) -> str | None:
    """Check if country was already extracted and cached."""
    if not attributes_json:
        return None
    try:
        attrs = json.loads(attributes_json)
    except (ValueError, TypeError):
        return None
    if isinstance(attrs, dict):
        return attrs.get("extracted_country")
    return None


def geographic_analysis(
    domain_id: str,
    *,
    sort_by: str = "entity_count",
    limit: int | None = None,
    include_collaboration: bool = False,
    org_id: int | None = None,
) -> dict[str, Any]:
    """Per-country aggregation with optional collaboration analysis."""
    _validate_domain(domain_id, org_id=org_id)

    rows = _load_entities_with_affiliations(domain_id, org_id=org_id)
    if not rows:
        result: dict[str, Any] = {
            "domain_id": domain_id,
            "coverage": 0.0,
            "total_entities": 0,
            "countries": [],
        }
        if include_collaboration:
            result["collaboration_rate"] = 0.0
            result["top_country_pairs"] = []
        return result

    total_entities = len(rows)
    country_stats: dict[str, dict[str, int]] = defaultdict(lambda: {
        "entity_count": 0, "citation_sum": 0,
    })
    entities_with_country = 0

    # For collaboration analysis
    entity_countries: list[set[str]] = [] if include_collaboration else []

    for row in rows:
        attrs_json = row.get("attributes_json")
        structured_countries = _get_structured_countries(attrs_json)
        # Check cached extraction first
        country_code = _get_extracted_country(attrs_json)
        if structured_countries:
            country_code = sorted(structured_countries)[0]
        elif not country_code:
            affiliation = _get_affiliation_from_attrs(attrs_json)
            country_code = extract_country(affiliation)

        if country_code:
            entities_with_country += 1
            country_stats[country_code]["entity_count"] += 1
            country_stats[country_code]["citation_sum"] += (row.get("enrichment_citation_count") or 0)

            if include_collaboration:
                entity_countries.append(structured_countries or {country_code})

    coverage = round(entities_with_country / total_entities, 4) if total_entities else 0.0

    # Build country list
    countries: list[dict[str, Any]] = []
    for code, stats in country_stats.items():
        countries.append({
            "country_code": code,
            "country_name": _CODE_TO_NAME.get(code, code),
            "entity_count": stats["entity_count"],
            "citation_sum": stats["citation_sum"],
            "percentage": round(stats["entity_count"] / total_entities * 100, 2) if total_entities else 0.0,
        })

    # Sort
    valid_sorts = {"entity_count", "citation_sum"}
    sort_key = sort_by if sort_by in valid_sorts else "entity_count"
    countries.sort(key=lambda c: c[sort_key], reverse=True)

    # Apply limit with "others" bucket
    if limit is not None and len(countries) > limit:
        top = countries[:limit]
        rest = countries[limit:]
        others_entity_count = sum(c["entity_count"] for c in rest)
        others_citation_sum = sum(c["citation_sum"] for c in rest)
        top.append({
            "country_code": "OTHER",
            "country_name": "Others",
            "entity_count": others_entity_count,
            "citation_sum": others_citation_sum,
            "percentage": round(others_entity_count / total_entities * 100, 2) if total_entities else 0.0,
        })
        countries = top

    result: dict[str, Any] = {
        "domain_id": domain_id,
        "coverage": coverage,
        "total_entities": total_entities,
        "countries": countries,
    }

    # Collaboration analysis
    if include_collaboration:
        multi_country = sum(1 for cs in entity_countries if len(cs) > 1)
        collaboration_rate = round(multi_country / entities_with_country * 100, 2) if entities_with_country else 0.0

        # Top country pairs
        pair_counter: Counter[tuple[str, str]] = Counter()
        for cs in entity_countries:
            if len(cs) >= 2:
                sorted_codes = sorted(cs)
                for i in range(len(sorted_codes)):
                    for j in range(i + 1, len(sorted_codes)):
                        pair_counter[(sorted_codes[i], sorted_codes[j])] += 1

        top_pairs = [
            {
                "country_a": a,
                "country_b": b,
                "country_a_name": _CODE_TO_NAME.get(a, a),
                "country_b_name": _CODE_TO_NAME.get(b, b),
                "count": count,
            }
            for (a, b), count in pair_counter.most_common(10)
        ]

        result["collaboration_rate"] = collaboration_rate
        result["top_country_pairs"] = top_pairs

    return result


def geographic_heatmap(domain_id: str, org_id: int | None = None) -> list[dict[str, Any]]:
    """Return lightweight heatmap data for the dashboard."""
    result = geographic_analysis(domain_id, org_id=org_id)
    return [
        {
            "country_code": c["country_code"],
            "country_name": c["country_name"],
            "value": c["entity_count"],
        }
        for c in result.get("countries", [])
        if c["country_code"] != "OTHER"
    ]
