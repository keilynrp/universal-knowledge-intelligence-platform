from __future__ import annotations

import json
import re
from typing import Any


def normalize_ror_id(value: str | None) -> str | None:
    """Normalize ROR URLs and bare IDs to the bare lowercase ROR identifier."""
    if not value:
        return None
    text = str(value).strip().lower()
    text = text.removeprefix("https://ror.org/").removeprefix("http://ror.org/")
    text = text.strip("/")
    return text or None


def _institution_key(institution: dict[str, Any]) -> tuple[str, str]:
    ror = normalize_ror_id(institution.get("ror"))
    if ror:
        return ("ror", ror)
    openalex_id = str(institution.get("openalex_id") or institution.get("id") or "").strip().lower()
    if openalex_id:
        return ("openalex", openalex_id)
    name = re.sub(r"\s+", " ", str(institution.get("name") or institution.get("display_name") or "")).strip().casefold()
    country = str(institution.get("country_code") or "").strip().upper()
    return ("name_country", f"{name}|{country}")


def extract_institution_authority_candidates(attributes_json: str | dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract ROR/OpenAlex-ready institution candidates from persisted affiliation metadata."""
    if not attributes_json:
        return []
    if isinstance(attributes_json, str):
        try:
            attrs = json.loads(attributes_json)
        except (TypeError, ValueError):
            return []
    else:
        attrs = attributes_json
    if not isinstance(attrs, dict):
        return []

    candidates: dict[tuple[str, str], dict[str, Any]] = {}

    def add_institution(raw: Any, source_field: str) -> None:
        if not isinstance(raw, dict):
            return
        name = raw.get("name") or raw.get("display_name")
        if not name:
            return
        candidate = {
            "name": name,
            "ror": normalize_ror_id(raw.get("ror")),
            "ror_url": f"https://ror.org/{normalize_ror_id(raw.get('ror'))}" if normalize_ror_id(raw.get("ror")) else None,
            "openalex_id": raw.get("openalex_id") or raw.get("id"),
            "country_code": raw.get("country_code"),
            "type": raw.get("type"),
            "lineage": raw.get("lineage") or [],
            "source_field": source_field,
        }
        candidates.setdefault(_institution_key(candidate), candidate)

    for institution in attrs.get("canonical_affiliations") or []:
        add_institution(institution, "canonical_affiliations")

    for author_affiliation in attrs.get("author_affiliations") or []:
        if not isinstance(author_affiliation, dict):
            continue
        for institution in author_affiliation.get("institutions") or []:
            add_institution(institution, "author_affiliations.institutions")

    return list(candidates.values())
