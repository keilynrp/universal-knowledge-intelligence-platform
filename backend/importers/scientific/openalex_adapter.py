from __future__ import annotations

import json
from typing import Any

from backend.importers.scientific.base import (
    CanonicalAffiliation,
    CanonicalAuthor,
    CanonicalIdentifier,
    CanonicalPublication,
    ScientificImportAdapter,
    ScientificImportResult,
)


class OpenAlexJSONImportAdapter(ScientificImportAdapter):
    provider = "openalex"
    format = "openalex_json"

    def can_parse(self, filename: str, content: str) -> bool:
        if not filename.lower().endswith((".json", ".jsonl")):
            return False
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return False
        sample = _first_work(payload)
        return isinstance(sample, dict) and str(sample.get("id", "")).startswith("https://openalex.org/")

    def parse(self, filename: str, content: str) -> ScientificImportResult:
        payload = json.loads(content)
        records = [_openalex_work_to_canonical(work) for work in _iter_works(payload)]
        return ScientificImportResult(format=self.format, provider=self.provider, records=records)


def _iter_works(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return [item for item in payload["results"] if isinstance(item, dict)]
        if payload.get("id"):
            return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _first_work(payload: Any) -> dict[str, Any] | None:
    works = _iter_works(payload)
    return works[0] if works else None


def _openalex_work_to_canonical(work: dict[str, Any]) -> CanonicalPublication:
    authors: list[CanonicalAuthor] = []
    affiliations: list[CanonicalAffiliation] = []
    for order, authorship in enumerate(work.get("authorships") or [], start=1):
        author = authorship.get("author") or {}
        institution_names: list[str] = []
        for institution in authorship.get("institutions") or []:
            name = institution.get("display_name")
            if name:
                institution_names.append(name)
                affiliations.append(
                    CanonicalAffiliation(
                        name=name,
                        country=institution.get("country_code"),
                        external_id=institution.get("id"),
                    )
                )
        if author.get("display_name"):
            authors.append(
                CanonicalAuthor(
                    name=author["display_name"],
                    order=order,
                    orcid=author.get("orcid"),
                    external_id=author.get("id"),
                    affiliations=institution_names,
                )
            )

    source = ((work.get("primary_location") or {}).get("source") or {})
    concepts = [
        concept.get("display_name")
        for concept in work.get("concepts") or []
        if concept.get("display_name")
    ]
    doi = (work.get("doi") or "").removeprefix("https://doi.org/") or None
    return CanonicalPublication(
        title=work.get("display_name") or work.get("title"),
        provider="openalex",
        provider_record_id=work.get("id"),
        doi=doi,
        year=work.get("publication_year"),
        publication_type=work.get("type") or "publication",
        source_title=source.get("display_name"),
        publisher=source.get("host_organization_name"),
        abstract=work.get("abstract"),
        concepts=concepts,
        authors=authors,
        affiliations=affiliations,
        identifiers=[
            identifier
            for identifier in (
                CanonicalIdentifier("openalex", work["id"]) if work.get("id") else None,
                CanonicalIdentifier("doi", doi) if doi else None,
            )
            if identifier is not None
        ],
        citation_count=work.get("cited_by_count"),
        raw_record=work,
    )
