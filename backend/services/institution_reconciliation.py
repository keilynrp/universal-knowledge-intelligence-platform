from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any

import httpx

from backend.services.scientific_affiliations import (
    extract_institution_authority_candidates,
    normalize_ror_id,
)


ROR_API_URL = "https://api.ror.org/organizations"


@dataclass(slots=True)
class InstitutionCandidate:
    name: str
    ror: str | None = None
    openalex_id: str | None = None
    country_code: str | None = None
    type: str | None = None
    lineage: list[str] = field(default_factory=list)
    source_field: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RORRecord:
    ror_id: str
    name: str
    aliases: list[str] = field(default_factory=list)
    acronyms: list[str] = field(default_factory=list)
    country_code: str | None = None
    country_name: str | None = None
    types: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    external_ids: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def uri(self) -> str:
        return f"https://ror.org/{self.ror_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self) | {"uri": self.uri}


@dataclass(slots=True)
class ReconciliationMatch:
    candidate: InstitutionCandidate
    record: RORRecord
    score: float
    status: str
    auto_accept: bool
    breakdown: dict[str, float]
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "record": self.record.to_dict(),
            "score": self.score,
            "status": self.status,
            "auto_accept": self.auto_accept,
            "breakdown": self.breakdown,
            "evidence": self.evidence,
        }


def normalize_institution_name(value: str | None) -> str:
    if not value:
        return ""
    text = value.casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\b(the|of|and|for|de|del|la|el|y)\b", " ", text)
    text = re.sub(r"\b(university|universidad|institute|instituto|college|school|center|centre)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _legacy_affiliation_candidates(attrs: dict[str, Any]) -> list[InstitutionCandidate]:
    raw = attrs.get("affiliations") or attrs.get("affiliation") or attrs.get("institution") or attrs.get("institutions")
    values: list[str] = []
    if isinstance(raw, str):
        values = [part.strip() for part in re.split(r";|\n", raw) if part.strip()]
    elif isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
    candidates: list[InstitutionCandidate] = []
    for value in values:
        name = value.split(",")[0].strip()
        if name:
            candidates.append(InstitutionCandidate(name=name, source_field="legacy_affiliations"))
    return candidates


def extract_institution_candidates(attributes_json: str | dict[str, Any] | None) -> list[InstitutionCandidate]:
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

    raw_candidates = extract_institution_authority_candidates(attrs)
    candidates = [
        InstitutionCandidate(
            name=item["name"],
            ror=item.get("ror"),
            openalex_id=item.get("openalex_id"),
            country_code=item.get("country_code"),
            type=item.get("type"),
            lineage=item.get("lineage") or [],
            source_field=item.get("source_field") or "canonical_affiliations",
        )
        for item in raw_candidates
    ]
    if not candidates:
        candidates = _legacy_affiliation_candidates(attrs)

    deduped: dict[tuple[str, str], InstitutionCandidate] = {}
    for candidate in candidates:
        if candidate.ror:
            key = ("ror", normalize_ror_id(candidate.ror) or "")
        elif candidate.openalex_id:
            key = ("openalex", candidate.openalex_id.strip().lower())
        else:
            key = ("name_country", f"{normalize_institution_name(candidate.name)}|{candidate.country_code or ''}")
        deduped.setdefault(key, candidate)
    return list(deduped.values())


class RORAdapter:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def lookup(self, ror_id: str) -> RORRecord | None:
        normalized = normalize_ror_id(ror_id)
        if not normalized:
            return None
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{ROR_API_URL}/{normalized}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return parse_ror_record(response.json())

    def search(self, name: str, country_code: str | None = None, limit: int = 5) -> list[RORRecord]:
        params: dict[str, Any] = {"query": name}
        if country_code:
            params["filter"] = f"country.country_code:{country_code.upper()}"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(ROR_API_URL, params=params)
            response.raise_for_status()
            payload = response.json()
        items = payload.get("items") if isinstance(payload, dict) else []
        return [parse_ror_record(item) for item in (items or [])[:limit] if isinstance(item, dict)]


def parse_ror_record(raw: dict[str, Any]) -> RORRecord:
    names = raw.get("names") if isinstance(raw.get("names"), list) else []
    primary_name = raw.get("name")
    aliases: list[str] = list(raw.get("aliases") or [])
    acronyms: list[str] = list(raw.get("acronyms") or [])
    for item in names:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if not value:
            continue
        types = item.get("types") or []
        if "ror_display" in types or "label" in types:
            primary_name = primary_name or value
        elif "alias" in types:
            aliases.append(value)
        elif "acronym" in types:
            acronyms.append(value)

    country = raw.get("country") or {}
    return RORRecord(
        ror_id=normalize_ror_id(raw.get("id")) or str(raw.get("id") or "").strip(),
        name=primary_name or str(raw.get("id") or "Unknown organization"),
        aliases=sorted(set(aliases)),
        acronyms=sorted(set(acronyms)),
        country_code=country.get("country_code"),
        country_name=country.get("country_name"),
        types=list(raw.get("types") or []),
        links=[
            link.get("value") if isinstance(link, dict) else str(link)
            for link in (raw.get("links") or [])
            if link
        ],
        external_ids=raw.get("external_ids") or {},
        raw=raw,
    )


def score_institution_match(candidate: InstitutionCandidate, record: RORRecord) -> ReconciliationMatch:
    evidence: list[str] = []
    breakdown = {"identifier": 0.0, "openalex": 0.0, "name": 0.0, "alias": 0.0, "country": 0.0, "penalty": 0.0}

    if candidate.ror and normalize_ror_id(candidate.ror) == record.ror_id:
        breakdown["identifier"] = 1.0
        evidence.append("exact_ror_match")
    if candidate.openalex_id and _external_id_values(record.external_ids, "openalex"):
        external_values = {value.lower() for value in _external_id_values(record.external_ids, "openalex")}
        if candidate.openalex_id.lower() in external_values:
            breakdown["openalex"] = 1.0
            evidence.append("openalex_id_match")

    candidate_name = normalize_institution_name(candidate.name)
    record_name = normalize_institution_name(record.name)
    name_score = SequenceMatcher(None, candidate_name, record_name).ratio() if candidate_name and record_name else 0.0
    breakdown["name"] = round(name_score, 3)
    if name_score >= 0.92:
        evidence.append("strong_name_match")

    alias_score = 0.0
    for alias in [*record.aliases, *record.acronyms]:
        alias_norm = normalize_institution_name(alias)
        if alias_norm:
            alias_score = max(alias_score, SequenceMatcher(None, candidate_name, alias_norm).ratio())
    breakdown["alias"] = round(alias_score, 3)
    if alias_score >= 0.92:
        evidence.append("alias_or_acronym_match")

    if candidate.country_code and record.country_code:
        if candidate.country_code.upper() == record.country_code.upper():
            breakdown["country"] = 1.0
            evidence.append("country_match")
        else:
            breakdown["penalty"] = -0.25
            evidence.append("country_mismatch")

    generic = candidate_name in {"university", "institute", "college", "school", "lab", "laboratory"}
    if generic:
        breakdown["penalty"] -= 0.2
        evidence.append("generic_name_penalty")

    if breakdown["identifier"] == 1.0:
        score = 0.98
    elif breakdown["openalex"] == 1.0:
        score = 0.94
    else:
        score = (
            0.58 * max(breakdown["name"], breakdown["alias"])
            + 0.22 * breakdown["country"]
            + 0.20 * (1.0 if record.ror_id else 0.0)
            + breakdown["penalty"]
        )
    score = round(max(0.0, min(1.0, score)), 3)
    status = "exact_match" if score >= 0.9 else "probable_match" if score >= 0.7 else "unresolved"
    return ReconciliationMatch(
        candidate=candidate,
        record=record,
        score=score,
        status=status,
        auto_accept=score >= 0.9 and ("exact_ror_match" in evidence or "strong_name_match" in evidence),
        breakdown=breakdown,
        evidence=evidence,
    )


def _external_id_values(external_ids: dict[str, Any], key: str) -> list[str]:
    raw = external_ids.get(key) or external_ids.get(key.upper()) or external_ids.get(key.capitalize())
    if isinstance(raw, dict):
        raw = raw.get("all") or raw.get("preferred") or raw.get("value")
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if raw:
        return [str(raw).strip()]
    return []
