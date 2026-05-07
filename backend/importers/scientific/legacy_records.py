from __future__ import annotations

import re
from typing import Any

from backend.importers.scientific.base import CanonicalAuthor, CanonicalIdentifier, CanonicalPublication


def _split_people(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace(" and ", ";")
    return [part.strip() for part in normalized.split(";") if part.strip()]


def _split_concepts(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[;,]", value) if part.strip()]


def _parse_year(value: Any) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"\d{4}", str(value))
    return int(match.group(0)) if match else None


def _identifier(scheme: str, value: Any) -> CanonicalIdentifier | None:
    if value in (None, ""):
        return None
    return CanonicalIdentifier(scheme=scheme, value=str(value).strip())


def canonical_publication_from_legacy_record(
    record: dict[str, Any],
    *,
    provider: str,
    provider_record_id: str | None = None,
    mapping_version: str = "ukip-science-v1",
) -> CanonicalPublication:
    doi = record.get("doi")
    identifiers = [
        identifier
        for identifier in (
            _identifier("doi", doi),
            _identifier("pubmed", record.get("pubmed_id")),
            _identifier("issn", record.get("issn")),
            _identifier("eissn", record.get("eissn")),
            _identifier("source_record", provider_record_id),
        )
        if identifier is not None
    ]
    authors = [
        CanonicalAuthor(name=name, order=index + 1)
        for index, name in enumerate(_split_people(record.get("authors")))
    ]

    return CanonicalPublication(
        title=record.get("title"),
        provider=provider,
        provider_record_id=provider_record_id,
        doi=doi,
        year=_parse_year(record.get("year")),
        publication_type=record.get("entity_type") or "publication",
        source_title=record.get("journal"),
        publisher=record.get("publisher"),
        abstract=record.get("abstract"),
        concepts=_split_concepts(record.get("keywords")),
        authors=authors,
        identifiers=identifiers,
        citation_count=record.get("citation_count"),
        reference_count=record.get("reference_count"),
        raw_record=record,
        mapping_version=mapping_version,
    )
