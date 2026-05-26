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

    def to_provenance(self) -> dict[str, Any]:
        return {
            "target": self.canonical_target,
            "concept": self.semantic_concept,
            "scheme": self.identifier_scheme,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "requires_review": self.requires_review,
        }


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

_SOURCE_SCHEMA_RULES: dict[str, dict[str, FieldCorrespondence]] = {
    "wos": {
        "ti": FieldCorrespondence("TI", "entity_label", "primary_label", 0.98, ("wos_schema_rule",)),
        "so": FieldCorrespondence("SO", "entity_subtitle", "secondary_label", 0.9, ("wos_schema_rule",)),
        "di": FieldCorrespondence("DI", "persistent_identifier", "canonical_id", 0.99, ("wos_schema_rule",), "doi"),
        "ut": FieldCorrespondence("UT", "persistent_identifier", "canonical_id", 0.96, ("wos_schema_rule",), "wos"),
        "dt": FieldCorrespondence("DT", "entity_type", "entity_type", 0.98, ("wos_schema_rule",)),
        "py": FieldCorrespondence("PY", "publication_year", None, 0.9, ("wos_schema_rule",)),
        "tc": FieldCorrespondence("TC", "citation_count", "enrichment_citation_count", 0.95, ("wos_schema_rule",)),
    },
    "ris": {
        "ti": FieldCorrespondence("TI", "entity_label", "primary_label", 0.98, ("ris_schema_rule",)),
        "t1": FieldCorrespondence("T1", "entity_label", "primary_label", 0.98, ("ris_schema_rule",)),
        "au": FieldCorrespondence("AU", "creator", "secondary_label", 0.9, ("ris_schema_rule",)),
        "do": FieldCorrespondence("DO", "persistent_identifier", "canonical_id", 0.99, ("ris_schema_rule",), "doi"),
        "ty": FieldCorrespondence("TY", "entity_type", "entity_type", 0.98, ("ris_schema_rule",)),
        "kw": FieldCorrespondence("KW", "concepts", "enrichment_concepts", 0.9, ("ris_schema_rule",)),
    },
    "bibtex": {
        "title": FieldCorrespondence("title", "entity_label", "primary_label", 0.98, ("bibtex_schema_rule",)),
        "author": FieldCorrespondence("author", "creator", "secondary_label", 0.9, ("bibtex_schema_rule",)),
        "doi": FieldCorrespondence("doi", "persistent_identifier", "canonical_id", 0.99, ("bibtex_schema_rule",), "doi"),
        "entrytype": FieldCorrespondence("ENTRYTYPE", "entity_type", "entity_type", 0.98, ("bibtex_schema_rule",)),
        "_entry_type": FieldCorrespondence("_entry_type", "entity_type", "entity_type", 0.98, ("bibtex_schema_rule",)),
        "keywords": FieldCorrespondence("keywords", "concepts", "enrichment_concepts", 0.9, ("bibtex_schema_rule",)),
    },
    "openalex": {
        "display_name": FieldCorrespondence("display_name", "entity_label", "primary_label", 0.98, ("openalex_schema_rule",)),
        "doi": FieldCorrespondence("doi", "persistent_identifier", "canonical_id", 0.99, ("openalex_schema_rule",), "doi"),
        "id": FieldCorrespondence("id", "external_authority_id", None, 0.96, ("openalex_schema_rule",), "openalex"),
        "type": FieldCorrespondence("type", "entity_type", "entity_type", 0.95, ("openalex_schema_rule",)),
        "cited_by_count": FieldCorrespondence("cited_by_count", "citation_count", "enrichment_citation_count", 0.95, ("openalex_schema_rule",)),
    },
    "pubmed": {
        "pmid": FieldCorrespondence("PMID", "persistent_identifier", "canonical_id", 0.96, ("pubmed_schema_rule",), "pmid"),
        "articleid doi": FieldCorrespondence("ArticleId doi", "persistent_identifier", "canonical_id", 0.99, ("pubmed_schema_rule",), "doi"),
        "articletitle": FieldCorrespondence("ArticleTitle", "entity_label", "primary_label", 0.98, ("pubmed_schema_rule",)),
        "publicationtype": FieldCorrespondence("PublicationType", "entity_type", "entity_type", 0.95, ("pubmed_schema_rule",)),
    },
    "scopus": {
        "eid": FieldCorrespondence("EID", "persistent_identifier", "canonical_id", 0.96, ("scopus_schema_rule",), "scopus"),
        "prism doi": FieldCorrespondence("prism:doi", "persistent_identifier", "canonical_id", 0.99, ("scopus_schema_rule",), "doi"),
        "dc title": FieldCorrespondence("dc:title", "entity_label", "primary_label", 0.98, ("scopus_schema_rule",)),
        "subtype": FieldCorrespondence("subtype", "entity_type", "entity_type", 0.95, ("scopus_schema_rule",)),
        "citedby count": FieldCorrespondence("citedby-count", "citation_count", "enrichment_citation_count", 0.95, ("scopus_schema_rule",)),
    },
}

_SOURCE_SCHEMA_ALIASES = {
    "wos": "wos",
    "web_of_science": "wos",
    "web of science": "wos",
    "wos_plaintext": "wos",
    "wos plaintext": "wos",
    "ris": "ris",
    "bib": "bibtex",
    "bibtex": "bibtex",
    "openalex": "openalex",
    "pubmed": "pubmed",
    "scopus": "scopus",
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
    del sample_values, domain  # Reserved for value-aware rules.
    key = _norm(source_field)

    schema_key = _SOURCE_SCHEMA_ALIASES.get(_norm(source_schema or ""))
    if schema_key:
        schema_match = _SOURCE_SCHEMA_RULES.get(schema_key, {}).get(key)
        if schema_match:
            return FieldCorrespondence(
                source_field,
                schema_match.semantic_concept,
                schema_match.canonical_target,
                schema_match.confidence,
                schema_match.evidence,
                schema_match.identifier_scheme,
                schema_match.requires_review,
            )

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


def infer_source_schema(source_name: str | None = None, fields: list[str] | set[str] | None = None) -> str | None:
    """Infer a known source schema from a filename/provider label and fields."""
    name = _norm(source_name or "")
    for marker, schema in (
        ("web of science", "wos"),
        ("wos", "wos"),
        ("ris", "ris"),
        ("bibtex", "bibtex"),
        ("bib", "bibtex"),
        ("openalex", "openalex"),
        ("pubmed", "pubmed"),
        ("scopus", "scopus"),
    ):
        if marker in name:
            return schema

    normalized_fields = {_norm(field) for field in (fields or [])}
    if {"pt", "au", "ti", "so", "di", "dt"} & normalized_fields and {"er", "ef", "fn", "vr"} & normalized_fields:
        return "wos"
    if {"ty", "au", "ti", "do", "er"} & normalized_fields:
        return "ris"
    if {"_entry_type", "cite_key"} & normalized_fields or {"entrytype", "bibtexkey"} & normalized_fields:
        return "bibtex"
    if {"display name", "cited by count"} & normalized_fields:
        return "openalex"
    if {"pmid", "articletitle"} & normalized_fields:
        return "pubmed"
    if {"eid", "prism doi", "dc title"} & normalized_fields:
        return "scopus"
    return None


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
