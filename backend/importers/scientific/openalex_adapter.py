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

# Heavy fields stripped from raw_record before persisting to attributes_json
_STRIP_FROM_RAW = frozenset({
    "abstract_inverted_index",
    "referenced_works",
    "related_works",
    "ngrams_url",
    "counts_by_year",
})

# Minimum relevance score for OpenAlex concepts/topics
_CONCEPT_SCORE_THRESHOLD = 0.4


class OpenAlexJSONImportAdapter(ScientificImportAdapter):
    provider = "openalex"
    format = "openalex_json"

    def can_parse(self, filename: str, content: str) -> bool:
        if not filename.lower().endswith((".json", ".jsonl")):
            return False
        sample = _peek_first_work(filename, content)
        return isinstance(sample, dict) and str(sample.get("id", "")).startswith("https://openalex.org/")

    def parse(self, filename: str, content: str) -> ScientificImportResult:
        works = _parse_works(filename, content)
        records = [_openalex_work_to_canonical(work) for work in works]
        return ScientificImportResult(format=self.format, provider=self.provider, records=records)


def _parse_works(filename: str, content: str) -> list[dict[str, Any]]:
    """Parse works from JSON or JSONL content."""
    if filename.lower().endswith(".jsonl"):
        works = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    works.append(obj)
            except json.JSONDecodeError:
                continue
        return works
    payload = json.loads(content)
    return _iter_works(payload)


def _iter_works(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return [item for item in payload["results"] if isinstance(item, dict)]
        if payload.get("id"):
            return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _peek_first_work(filename: str, content: str) -> dict[str, Any] | None:
    """Read just the first work without fully parsing the file."""
    if filename.lower().endswith(".jsonl"):
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
        return None
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    works = _iter_works(payload)
    return works[0] if works else None


def _reconstruct_abstract(work: dict[str, Any]) -> str | None:
    """Reconstruct abstract text from OpenAlex abstract_inverted_index."""
    plain = work.get("abstract")
    if plain and isinstance(plain, str):
        return plain
    inv_index = work.get("abstract_inverted_index")
    if not inv_index or not isinstance(inv_index, dict):
        return None
    positions: list[tuple[int, str]] = []
    for word, indices in inv_index.items():
        if not isinstance(indices, list):
            continue
        for idx in indices:
            if isinstance(idx, int):
                positions.append((idx, word))
    if not positions:
        return None
    positions.sort()
    return " ".join(word for _, word in positions)


def _extract_concepts(work: dict[str, Any]) -> list[str]:
    """Extract concepts from concepts, topics, and keywords fields with score filtering."""
    concepts: list[str] = []
    seen: set[str] = set()

    # Legacy concepts field (may be deprecated but still present on older records)
    for concept in work.get("concepts") or []:
        name = concept.get("display_name")
        if name and concept.get("score", 0) >= _CONCEPT_SCORE_THRESHOLD:
            key = name.lower()
            if key not in seen:
                seen.add(key)
                concepts.append(name)

    # Newer topics field
    for topic in work.get("topics") or []:
        name = topic.get("display_name")
        if name and topic.get("score", 0) >= _CONCEPT_SCORE_THRESHOLD:
            key = name.lower()
            if key not in seen:
                seen.add(key)
                concepts.append(name)

    # Plain keywords field (no score filtering)
    for kw in work.get("keywords") or []:
        name = kw.get("display_name") if isinstance(kw, dict) else (kw if isinstance(kw, str) else None)
        if name:
            key = name.lower()
            if key not in seen:
                seen.add(key)
                concepts.append(name)

    return concepts


def _strip_raw_record(work: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the work dict without heavy fields."""
    return {k: v for k, v in work.items() if k not in _STRIP_FROM_RAW}


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
    concepts = _extract_concepts(work)
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
        abstract=_reconstruct_abstract(work),
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
        raw_record=_strip_raw_record(work),
    )
