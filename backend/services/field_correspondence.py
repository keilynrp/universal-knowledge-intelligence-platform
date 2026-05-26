"""Field correspondence layer for source-agnostic imports.

This module resolves heterogeneous source headers into UKIP canonical targets
with a small amount of semantic context. It intentionally separates the
question "what concept is this field?" from "which storage column should get
the value?" so fields such as "Tipo de Identificador" do not get mistaken for
the identifier value itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


CanonicalTarget = Literal[
    "primary_label",
    "secondary_label",
    "canonical_id",
    "entity_type",
    "domain",
    "validation_status",
    "enrichment_doi",
    "enrichment_citation_count",
    "enrichment_concepts",
    "enrichment_source",
]


@dataclass(frozen=True)
class FieldCorrespondence:
    source_field: str
    semantic_concept: str
    canonical_target: CanonicalTarget | None
    confidence: float
    evidence: tuple[str, ...] = field(default_factory=tuple)
    identifier_scheme: str | None = None
    requires_review: bool = False


def _norm(value: str) -> str:
    return " ".join(
        value.strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace(":", " ")
        .split()
    )


_PRIMARY_LABEL_HEADERS = {
    "name", "title", "label", "primary label", "display name", "nombre", "titulo", "título",
}

_SECONDARY_LABEL_HEADERS = {
    "author", "authors", "creator", "institution", "organization", "publisher",
    "venue", "source", "secondary label", "autor", "autores", "institucion",
    "institución", "organizacion", "organización", "editorial", "fuente",
}

_IDENTIFIER_VALUE_HEADERS: dict[str, str | None] = {
    "id": None,
    "uid": None,
    "identifier": None,
    "identificador": None,
    "identificador unico": None,
    "identificador único": None,
    "id unico": None,
    "id único": None,
    "code": None,
    "codigo": None,
    "código": None,
    "doi": "doi",
    "doi number": "doi",
    "orcid": "orcid",
    "orcid id": "orcid",
    "ror": "ror",
    "ror id": "ror",
    "isbn": "isbn",
    "issn": "issn",
    "pmid": "pmid",
    "pubmed": "pmid",
    "pubmed id": "pmid",
    "wos id": "wos",
    "ut unique wos id": "wos",
    "scopus id": "scopus",
    "eid": "scopus",
    "openalex id": "openalex",
    "accession number": "accession",
    "record id": "local",
    "local id": "local",
}

_IDENTIFIER_SCHEME_HEADERS = {
    "identifier type", "type of identifier", "tipo de identificador",
    "tipo identificador", "scheme", "identifier scheme", "id type",
}

_ENTITY_TYPE_HEADERS = {
    "type", "tipo", "tipo de entidad", "category", "categoria", "categoría",
    "clase", "class", "kind", "document type", "tipo de documento",
    "publication type", "tipo de publicacion", "tipo de publicación", "subtype",
    "entity type",
}

_DOMAIN_HEADERS = {"domain", "dominio"}
_VALIDATION_HEADERS = {"status", "validation status", "estado", "estado validacion", "estado validación"}

_ENRICHMENT_HEADERS: dict[str, CanonicalTarget] = {
    "enrichment doi": "enrichment_doi",
    "citations": "enrichment_citation_count",
    "citation count": "enrichment_citation_count",
    "enrichment citation count": "enrichment_citation_count",
    "concepts": "enrichment_concepts",
    "keywords": "enrichment_concepts",
    "topics": "enrichment_concepts",
    "enrichment concepts": "enrichment_concepts",
    "enrichment source": "enrichment_source",
}

_DIRECT_TARGETS: set[CanonicalTarget] = {
    "primary_label",
    "secondary_label",
    "canonical_id",
    "entity_type",
    "domain",
    "validation_status",
    "enrichment_doi",
    "enrichment_citation_count",
    "enrichment_concepts",
    "enrichment_source",
}


def resolve_field_correspondence(
    source_field: str,
    *,
    sample_values: list[Any] | None = None,
    domain: str | None = None,
    source_schema: str | None = None,
) -> FieldCorrespondence | None:
    """Resolve a source header to a canonical target.

    ``sample_values`` and source context are accepted now so callers can evolve
    toward higher-confidence, value-aware matching without changing the API.
    """
    del sample_values, domain, source_schema  # Reserved for value-aware rules.
    key = _norm(source_field)

    if key in _DIRECT_TARGETS:
        return FieldCorrespondence(source_field, key, key, 1.0, ("direct_target",))

    if key in _PRIMARY_LABEL_HEADERS:
        return FieldCorrespondence(source_field, "entity_label", "primary_label", 0.95, ("header_alias",))

    if key in _SECONDARY_LABEL_HEADERS:
        return FieldCorrespondence(source_field, "entity_subtitle", "secondary_label", 0.9, ("header_alias",))

    if key in _IDENTIFIER_SCHEME_HEADERS:
        return FieldCorrespondence(
            source_field,
            "identifier_scheme",
            None,
            0.95,
            ("identifier_scheme_header",),
            requires_review=False,
        )

    if key in _IDENTIFIER_VALUE_HEADERS:
        scheme = _IDENTIFIER_VALUE_HEADERS[key]
        return FieldCorrespondence(
            source_field,
            "persistent_identifier",
            "canonical_id",
            0.95 if scheme else 0.78,
            ("identifier_value_header",) if scheme else ("generic_identifier_header",),
            identifier_scheme=scheme,
            requires_review=scheme is None,
        )

    if key in _ENTITY_TYPE_HEADERS:
        return FieldCorrespondence(source_field, "entity_type", "entity_type", 0.9, ("entity_type_header",))

    if key in _DOMAIN_HEADERS:
        return FieldCorrespondence(source_field, "domain", "domain", 0.95, ("header_alias",))

    if key in _VALIDATION_HEADERS:
        return FieldCorrespondence(source_field, "validation_status", "validation_status", 0.85, ("header_alias",))

    if key in _ENRICHMENT_HEADERS:
        target = _ENRICHMENT_HEADERS[key]
        return FieldCorrespondence(source_field, target, target, 0.9, ("enrichment_header",))

    return None


def resolve_field_mapping(source_field: str, **kwargs: Any) -> CanonicalTarget | None:
    correspondence = resolve_field_correspondence(source_field, **kwargs)
    return correspondence.canonical_target if correspondence else None


def build_legacy_column_mapping() -> dict[str, CanonicalTarget]:
    """Expose target-only aliases for older import paths and tests.

    Fields that describe metadata about an identifier, such as
    "Tipo de Identificador", intentionally do not appear here because they are
    not identifier values.
    """
    headers = (
        *_PRIMARY_LABEL_HEADERS,
        *_SECONDARY_LABEL_HEADERS,
        *_IDENTIFIER_VALUE_HEADERS.keys(),
        *_ENTITY_TYPE_HEADERS,
        *_DOMAIN_HEADERS,
        *_VALIDATION_HEADERS,
        *_ENRICHMENT_HEADERS.keys(),
    )
    result: dict[str, CanonicalTarget] = {}
    for header in headers:
        target = resolve_field_mapping(header)
        if target:
            result[header] = target
            title_header = " ".join(word.capitalize() for word in header.split())
            result[title_header] = target
    # Preserve common exact casing used in existing exports/import examples.
    result.update({
        "DOI": "canonical_id",
        "DOI Number": "canonical_id",
        "ORCID": "canonical_id",
        "ORCID ID": "canonical_id",
        "ROR": "canonical_id",
        "ROR ID": "canonical_id",
        "PMID": "canonical_id",
        "PubMed ID": "canonical_id",
        "UID": "canonical_id",
        "ID": "canonical_id",
        "Id": "canonical_id",
        "EID": "canonical_id",
        "Identificador único": "canonical_id",
        "Identificador unico": "canonical_id",
        "ID único": "canonical_id",
        "ID unico": "canonical_id",
        "Código": "canonical_id",
        "Codigo": "canonical_id",
        "WoS ID": "canonical_id",
        "WOS ID": "canonical_id",
        "OpenAlex ID": "canonical_id",
        "Scopus ID": "canonical_id",
        "Local ID": "canonical_id",
        "Record ID": "canonical_id",
        "Document Type": "entity_type",
        "Publication Type": "entity_type",
        "Tipo de entidad": "entity_type",
        "Tipo de documento": "entity_type",
        "Tipo de publicación": "entity_type",
    })
    return result
