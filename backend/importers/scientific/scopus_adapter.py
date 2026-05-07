from __future__ import annotations

import json
from typing import Any

from backend.importers.scientific.base import (
    CanonicalAuthor,
    CanonicalIdentifier,
    CanonicalPublication,
    ScientificImportAdapter,
    ScientificImportResult,
)


class ScopusJSONImportAdapter(ScientificImportAdapter):
    provider = "scopus"
    format = "scopus_json"

    def can_parse(self, filename: str, content: str) -> bool:
        if not filename.lower().endswith(".json"):
            return False
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return False
        sample = _first_entry(payload)
        return isinstance(sample, dict) and any(key in sample for key in ("dc:identifier", "eid", "prism:doi"))

    def parse(self, filename: str, content: str) -> ScientificImportResult:
        payload = json.loads(content)
        records = [_scopus_entry_to_canonical(entry) for entry in _iter_entries(payload)]
        return ScientificImportResult(format=self.format, provider=self.provider, records=records)


def _iter_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        entries = ((payload.get("search-results") or {}).get("entry") or payload.get("entry"))
        if isinstance(entries, list):
            return [entry for entry in entries if isinstance(entry, dict)]
        if payload.get("dc:identifier") or payload.get("eid"):
            return [payload]
    if isinstance(payload, list):
        return [entry for entry in payload if isinstance(entry, dict)]
    return []


def _first_entry(payload: Any) -> dict[str, Any] | None:
    entries = _iter_entries(payload)
    return entries[0] if entries else None


def _scopus_entry_to_canonical(entry: dict[str, Any]) -> CanonicalPublication:
    raw_authors = entry.get("author") if isinstance(entry.get("author"), list) else []
    authors = [
        CanonicalAuthor(
            name=author.get("authname") or author.get("given-name") or author.get("surname"),
            order=index + 1,
            external_id=author.get("authid"),
        )
        for index, author in enumerate(raw_authors)
        if isinstance(author, dict) and (author.get("authname") or author.get("surname"))
    ]
    doi = entry.get("prism:doi")
    scopus_id = entry.get("eid") or entry.get("dc:identifier")
    return CanonicalPublication(
        title=entry.get("dc:title"),
        provider="scopus",
        provider_record_id=scopus_id,
        doi=doi,
        year=_year(entry.get("prism:coverDate")),
        publication_type=entry.get("subtypeDescription") or entry.get("subtype") or "publication",
        source_title=entry.get("prism:publicationName"),
        publisher=entry.get("dc:publisher"),
        authors=authors,
        identifiers=[
            identifier
            for identifier in (
                CanonicalIdentifier("scopus", scopus_id) if scopus_id else None,
                CanonicalIdentifier("doi", doi) if doi else None,
            )
            if identifier is not None
        ],
        citation_count=_int(entry.get("citedby-count")),
        raw_record=entry,
    )


def _year(value: Any) -> int | None:
    if not value:
        return None
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
