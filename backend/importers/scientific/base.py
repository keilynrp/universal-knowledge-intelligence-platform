from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.parsers.science_mapper import science_record_to_entity
from backend.services.text_normalization import normalize_import_value


@dataclass(slots=True)
class CanonicalIdentifier:
    scheme: str
    value: str


@dataclass(slots=True)
class CanonicalAuthor:
    name: str
    order: int | None = None
    orcid: str | None = None
    external_id: str | None = None
    affiliations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CanonicalAffiliation:
    name: str
    country: str | None = None
    external_id: str | None = None


@dataclass(slots=True)
class CanonicalPublication:
    title: str | None
    provider: str
    provider_record_id: str | None = None
    doi: str | None = None
    year: int | None = None
    publication_type: str = "publication"
    source_title: str | None = None
    publisher: str | None = None
    abstract: str | None = None
    concepts: list[str] = field(default_factory=list)
    authors: list[CanonicalAuthor] = field(default_factory=list)
    affiliations: list[CanonicalAffiliation] = field(default_factory=list)
    identifiers: list[CanonicalIdentifier] = field(default_factory=list)
    citation_count: int | None = None
    reference_count: int | None = None
    raw_record: dict[str, Any] = field(default_factory=dict)
    mapping_version: str = "ukip-science-v1"

    def to_entity_kwargs(self, *, domain: str = "science") -> dict[str, Any]:
        record = {
            "title": self.title,
            "authors": "; ".join(author.name for author in self.authors if author.name) or None,
            "doi": self.doi,
            "keywords": ", ".join(self.concepts) if self.concepts else None,
            "year": str(self.year) if self.year else None,
            "abstract": self.abstract,
            "journal": self.source_title,
            "publisher": self.publisher,
            "entity_type": self.publication_type,
            "citation_count": self.citation_count,
            "reference_count": self.reference_count,
        }
        normalized_raw_record = normalize_import_value(self.raw_record)
        entity = science_record_to_entity({**normalized_raw_record, **{k: v for k, v in record.items() if v is not None}})
        entity["domain"] = domain
        entity["enrichment_source"] = self.provider
        if self.doi:
            entity["enrichment_doi"] = self.doi

        attrs = json.loads(entity.get("attributes_json") or "{}")
        attrs.update(
            {
                "provider": self.provider,
                "provider_record_id": self.provider_record_id,
                "mapping_version": self.mapping_version,
                "canonical_authors": [asdict(author) for author in self.authors],
                "canonical_affiliations": [asdict(affiliation) for affiliation in self.affiliations],
                "canonical_identifiers": [asdict(identifier) for identifier in self.identifiers],
                "raw_record": normalized_raw_record,
            }
        )
        entity["attributes_json"] = json.dumps(attrs, ensure_ascii=False)
        return entity


@dataclass(slots=True)
class ScientificImportResult:
    format: str
    provider: str
    records: list[CanonicalPublication]

    @property
    def total_rows(self) -> int:
        return len(self.records)

    def to_legacy_records(self) -> list[dict[str, Any]]:
        return [publication.raw_record for publication in self.records]


class ScientificImportAdapter(ABC):
    provider: str
    format: str

    @abstractmethod
    def can_parse(self, filename: str, content: str) -> bool:
        """Return whether this adapter understands the uploaded payload."""

    @abstractmethod
    def parse(self, filename: str, content: str) -> ScientificImportResult:
        """Parse provider payload into canonical UKIP publication records."""
