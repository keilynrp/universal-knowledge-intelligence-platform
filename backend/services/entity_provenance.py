"""Entity Provenance Layering — Task 2.6.

Provides the EntityDetailLayered schema and helpers to group entity
fields into 4 provenance layers for the detail view.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from backend.services.source_terminology import (
    SourceType,
    assign_field_to_layer,
    classify_field,
    group_fields_by_layer,
)


@dataclass
class ProvenanceBadge:
    """Visual badge metadata for a field's provenance."""
    source_type: SourceType
    label_key: str  # i18n key
    section: str    # section id


@dataclass
class EntityDetailLayered:
    """Entity detail grouped into 4 provenance layers."""
    entity_id: int
    original_ingestion: dict[str, Any] = field(default_factory=dict)
    normalized_identity: dict[str, Any] = field(default_factory=dict)
    external_enrichment: dict[str, Any] = field(default_factory=dict)
    authority_audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "original_ingestion": self.original_ingestion,
            "normalized_identity": self.normalized_identity,
            "external_enrichment": self.external_enrichment,
            "authority_audit": self.authority_audit,
        }


# ── Entity column → layer mapping ───────────────────────────────────────────

_INGESTION_COLUMNS = {
    "id", "org_id", "import_batch_id", "domain", "entity_type",
    "source", "attributes_json", "validation_status", "updated_at",
}

_NORMALIZED_COLUMNS = {
    "primary_label", "secondary_label", "canonical_id",
}

_ENRICHMENT_COLUMNS = {
    "enrichment_doi", "enrichment_citation_count", "enrichment_concepts",
    "enrichment_source", "enrichment_status", "enrichment_failure_reason",
    "quality_score", "normalized_json",
}


def build_layered_detail(
    entity_id: int,
    entity_dict: dict[str, Any],
    authority_records: list[dict[str, Any]] | None = None,
) -> EntityDetailLayered:
    """Build an EntityDetailLayered from a flat entity dict.

    ``entity_dict`` is the dict representation of a RawEntity row.
    ``authority_records`` is an optional list of serialized AuthorityRecord dicts.
    """
    ingestion: dict[str, Any] = {}
    normalized: dict[str, Any] = {}
    enrichment: dict[str, Any] = {}
    authority: dict[str, Any] = {}

    for key, value in entity_dict.items():
        if key in _NORMALIZED_COLUMNS:
            normalized[key] = value
        elif key in _ENRICHMENT_COLUMNS:
            enrichment[key] = value
        elif key in _INGESTION_COLUMNS:
            ingestion[key] = value
        else:
            # Attributes from attributes_json go to ingestion by default
            ingestion[key] = value

    # Expand attributes_json into the ingestion layer
    attrs_raw = entity_dict.get("attributes_json")
    if attrs_raw:
        try:
            attrs = json.loads(attrs_raw) if isinstance(attrs_raw, str) else attrs_raw
            if isinstance(attrs, dict):
                for k, v in attrs.items():
                    if k in ("canonical_affiliations", "author_affiliations"):
                        enrichment[k] = v
                    else:
                        ingestion[f"attr.{k}"] = v
        except (TypeError, ValueError):
            pass

    # Authority records
    if authority_records:
        authority["records"] = authority_records

    return EntityDetailLayered(
        entity_id=entity_id,
        original_ingestion=ingestion,
        normalized_identity=normalized,
        external_enrichment=enrichment,
        authority_audit=authority,
    )


def get_provenance_badge(field_name: str) -> ProvenanceBadge:
    """Return provenance badge metadata for a field."""
    source_type = classify_field(field_name)
    section = assign_field_to_layer(field_name)
    return ProvenanceBadge(
        source_type=source_type,
        label_key=f"provenance.source_type.{source_type.value}",
        section=section,
    )
