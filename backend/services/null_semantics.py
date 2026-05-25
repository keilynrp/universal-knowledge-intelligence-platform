"""Entity Detail Null Semantics — Task 2.7.

Computes contextual reasons for null/missing field values in entity
details, providing meaningful display copy instead of raw blanks.
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class NullReason(str, Enum):
    NOT_PROVIDED = "not_provided"
    PENDING_NORMALIZATION = "pending_normalization"
    UNRESOLVED_ENRICHMENT = "unresolved_enrichment"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


# i18n keys for null reason display
_REASON_I18N: dict[NullReason, str] = {
    NullReason.NOT_PROVIDED: "null_reason.not_provided",
    NullReason.PENDING_NORMALIZATION: "null_reason.pending_normalization",
    NullReason.UNRESOLVED_ENRICHMENT: "null_reason.unresolved_enrichment",
    NullReason.NOT_APPLICABLE: "null_reason.not_applicable",
    NullReason.UNKNOWN: "null_reason.unknown",
}

# Fields that should be populated by enrichment
_ENRICHMENT_FIELDS = frozenset({
    "enrichment_doi", "enrichment_citation_count", "enrichment_concepts",
    "enrichment_source", "quality_score",
})

# Fields that come from normalization
_NORMALIZATION_FIELDS = frozenset({
    "canonical_id", "normalized_json",
})

# Fields that only apply to certain entity types
_TYPE_SPECIFIC_FIELDS: dict[str, set[str]] = {
    "enrichment_doi": {"publication", "article", "paper"},
    "enrichment_citation_count": {"publication", "article", "paper"},
}


def compute_field_null_reason(
    entity: dict[str, Any],
    field_name: str,
) -> tuple[NullReason, str]:
    """Compute why a field is null/missing and return (reason, i18n_key).

    ``entity`` is a dict-like representation of a RawEntity.
    """
    value = entity.get(field_name)

    # If the field has a value, no null reason needed
    if value is not None and value != "" and value != 0:
        return NullReason.UNKNOWN, ""

    entity_type = (entity.get("entity_type") or "").lower()

    # Check if field is not applicable for this entity type
    if field_name in _TYPE_SPECIFIC_FIELDS:
        applicable_types = _TYPE_SPECIFIC_FIELDS[field_name]
        if entity_type and entity_type not in applicable_types:
            reason = NullReason.NOT_APPLICABLE
            return reason, _REASON_I18N[reason]

    # Check if field is enrichment-sourced
    if field_name in _ENRICHMENT_FIELDS:
        enrichment_status = entity.get("enrichment_status", "none")
        if enrichment_status in ("none", "pending"):
            reason = NullReason.UNRESOLVED_ENRICHMENT
            return reason, _REASON_I18N[reason]
        if enrichment_status == "done":
            # Enrichment ran but didn't produce this field
            reason = NullReason.NOT_PROVIDED
            return reason, _REASON_I18N[reason]

    # Check if field is normalization-sourced
    if field_name in _NORMALIZATION_FIELDS:
        validation_status = entity.get("validation_status", "pending")
        if validation_status == "pending":
            reason = NullReason.PENDING_NORMALIZATION
            return reason, _REASON_I18N[reason]

    # Default: not provided at ingestion
    source = entity.get("source", "")
    if source in ("user", "upload", "demo"):
        reason = NullReason.NOT_PROVIDED
        return reason, _REASON_I18N[reason]

    reason = NullReason.UNKNOWN
    return reason, _REASON_I18N[reason]


def enrich_entity_with_null_reasons(
    entity: dict[str, Any],
    fields: list[str] | None = None,
) -> dict[str, dict[str, str]]:
    """Compute null reasons for all null fields in an entity.

    Returns a dict mapping field_name → {reason_code, display_key}.
    Only includes fields that are null/missing.
    """
    if fields is None:
        fields = list(entity.keys())

    result: dict[str, dict[str, str]] = {}
    for field_name in fields:
        value = entity.get(field_name)
        if value is None or value == "" or (isinstance(value, int) and value == 0 and field_name in _ENRICHMENT_FIELDS):
            reason, i18n_key = compute_field_null_reason(entity, field_name)
            if reason != NullReason.UNKNOWN or i18n_key:
                result[field_name] = {
                    "reason_code": reason.value,
                    "display_key": i18n_key,
                }

    return result
