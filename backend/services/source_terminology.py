"""Source Terminology Contract — Task 1.5.

Defines the three provenance source types and provides helper functions
to map field names and value types to the correct provenance layer.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class SourceType(str, Enum):
    """Three distinct provenance layers for entity data."""

    INGESTION_SOURCE = "ingestion_source"
    ENRICHMENT_PROVIDER = "enrichment_provider"
    AUTHORITY_SOURCE = "authority_source"


# ── Field-to-layer mapping ──────────────────────────────────────────────────

_INGESTION_FIELDS = frozenset({
    "primary_label", "secondary_label", "domain", "entity_type",
    "source", "import_batch_id", "attributes_json",
    "canonical_id", "validation_status",
})

_ENRICHMENT_FIELDS = frozenset({
    "enrichment_doi", "enrichment_citation_count", "enrichment_concepts",
    "enrichment_source", "enrichment_status", "enrichment_failure_reason",
    "quality_score", "normalized_json",
})

_AUTHORITY_FIELDS = frozenset({
    "authority_source", "authority_id", "canonical_label",
    "confidence", "resolution_status", "score_breakdown",
    "evidence", "merged_sources",
})

# Section display order
PROVENANCE_SECTIONS = (
    ("original_ingestion", SourceType.INGESTION_SOURCE),
    ("normalized_identity", SourceType.INGESTION_SOURCE),
    ("external_enrichment", SourceType.ENRICHMENT_PROVIDER),
    ("authority_audit", SourceType.AUTHORITY_SOURCE),
)


def classify_field(field_name: str) -> SourceType:
    """Return the provenance layer a field belongs to."""
    if field_name in _AUTHORITY_FIELDS:
        return SourceType.AUTHORITY_SOURCE
    if field_name in _ENRICHMENT_FIELDS:
        return SourceType.ENRICHMENT_PROVIDER
    return SourceType.INGESTION_SOURCE


def get_source_label(field_name: str, value_type: str | None = None) -> str:
    """Return the i18n key for a source label.

    ``value_type`` can be used to override the classification when the
    caller knows better (e.g. an enrichment value stored under a
    generic field name).
    """
    if value_type:
        try:
            source = SourceType(value_type)
        except ValueError:
            source = classify_field(field_name)
    else:
        source = classify_field(field_name)

    return f"provenance.source_type.{source.value}"


def get_section_key(section_id: str) -> str:
    """Return the i18n key for a provenance section header."""
    return f"provenance.section.{section_id}"


def assign_field_to_layer(field_name: str) -> str:
    """Return the section id a field should render under in the detail view."""
    if field_name in _AUTHORITY_FIELDS:
        return "authority_audit"
    if field_name in _ENRICHMENT_FIELDS:
        return "external_enrichment"
    if field_name in {"primary_label", "secondary_label", "canonical_id"}:
        return "normalized_identity"
    return "original_ingestion"


def group_fields_by_layer(fields: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Split a flat dict of fields into the 4 provenance sections."""
    grouped: dict[str, dict[str, Any]] = {
        "original_ingestion": {},
        "normalized_identity": {},
        "external_enrichment": {},
        "authority_audit": {},
    }
    for key, value in fields.items():
        section = assign_field_to_layer(key)
        grouped[section][key] = value
    return grouped
