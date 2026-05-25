"""Canonical Model Authority Boundary — Task 3.8.

Enforces layer boundary rules: enrichment cannot overwrite source,
authority cannot overwrite enrichment, canonical promotion preserves
source, and re-ingestion versions the source layer.
"""
from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class LayerViolationError(Exception):
    """Raised when a layer boundary is violated."""
    pass


@dataclass
class LayerSnapshot:
    """Immutable snapshot of an entity's data layers."""
    source: dict[str, Any]
    enrichment: dict[str, Any]
    canonical: dict[str, Any]
    authority: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "enrichment": self.enrichment,
            "canonical": self.canonical,
            "authority": self.authority,
        }


_SOURCE_FIELDS = frozenset({
    "primary_label", "secondary_label", "domain", "entity_type",
    "source", "import_batch_id", "attributes_json", "validation_status",
})

_ENRICHMENT_FIELDS = frozenset({
    "enrichment_doi", "enrichment_citation_count", "enrichment_concepts",
    "enrichment_source", "enrichment_status", "enrichment_failure_reason",
    "quality_score", "normalized_json",
})

_CANONICAL_FIELDS = frozenset({
    "canonical_id",
})

_AUTHORITY_FIELDS = frozenset({
    "authority_source", "authority_id", "canonical_label",
    "confidence", "resolution_status", "score_breakdown",
    "evidence", "merged_sources",
})


def classify_layer(field_name: str) -> str:
    """Classify a field into its data layer."""
    if field_name in _AUTHORITY_FIELDS:
        return "authority"
    if field_name in _CANONICAL_FIELDS:
        return "canonical"
    if field_name in _ENRICHMENT_FIELDS:
        return "enrichment"
    return "source"


def snapshot_entity(entity: dict[str, Any]) -> LayerSnapshot:
    """Create a layer snapshot from an entity dict."""
    source: dict[str, Any] = {}
    enrichment: dict[str, Any] = {}
    canonical: dict[str, Any] = {}
    authority: dict[str, Any] = {}

    for key, value in entity.items():
        layer = classify_layer(key)
        if layer == "authority":
            authority[key] = value
        elif layer == "canonical":
            canonical[key] = value
        elif layer == "enrichment":
            enrichment[key] = value
        else:
            source[key] = value

    return LayerSnapshot(
        source=source,
        enrichment=enrichment,
        canonical=canonical,
        authority=authority,
    )


def validate_enrichment_apply(
    before: LayerSnapshot,
    updates: dict[str, Any],
) -> list[str]:
    """Validate that enrichment apply doesn't overwrite source or canonical.

    Returns list of violation messages. Empty = valid.
    """
    violations: list[str] = []
    for field_name in updates:
        layer = classify_layer(field_name)
        if layer == "source":
            violations.append(f"Enrichment cannot overwrite source field '{field_name}'")
        elif layer == "canonical":
            violations.append(f"Enrichment cannot overwrite canonical field '{field_name}'")
        elif layer == "authority":
            violations.append(f"Enrichment cannot overwrite authority field '{field_name}'")
    return violations


def validate_authority_apply(
    before: LayerSnapshot,
    updates: dict[str, Any],
) -> list[str]:
    """Validate that authority resolution doesn't overwrite enrichment.

    Returns list of violation messages. Empty = valid.
    """
    violations: list[str] = []
    for field_name in updates:
        layer = classify_layer(field_name)
        if layer == "enrichment":
            violations.append(f"Authority cannot overwrite enrichment field '{field_name}'")
        elif layer == "source":
            violations.append(f"Authority cannot overwrite source field '{field_name}'")
    return violations


def validate_promotion(
    before: LayerSnapshot,
    updates: dict[str, Any],
) -> list[str]:
    """Validate that canonical promotion preserves source layer.

    Returns list of violation messages. Empty = valid.
    """
    violations: list[str] = []
    for field_name in updates:
        layer = classify_layer(field_name)
        if layer == "source":
            violations.append(f"Canonical promotion cannot destroy source field '{field_name}'")
    return violations


def validate_reingestion(
    before: LayerSnapshot,
    new_source: dict[str, Any],
) -> list[str]:
    """Validate that re-ingestion versions source without overwriting canonical/authority.

    Returns list of violation messages. Empty = valid.
    """
    violations: list[str] = []
    for field_name in new_source:
        layer = classify_layer(field_name)
        if layer == "canonical":
            violations.append(f"Re-ingestion cannot overwrite canonical field '{field_name}'")
        elif layer == "authority":
            violations.append(f"Re-ingestion cannot overwrite authority field '{field_name}'")
    return violations


def safe_enrichment_rollback(
    entity: dict[str, Any],
) -> dict[str, Any]:
    """Remove enrichment fields without affecting canonical or authority.

    Returns new dict with enrichment fields cleared.
    """
    result = dict(entity)
    for field_name in _ENRICHMENT_FIELDS:
        if field_name in result:
            result[field_name] = None
    return result


def enforce_layer_boundaries(
    operation: str,
    before: LayerSnapshot,
    updates: dict[str, Any],
) -> None:
    """Enforce layer boundaries. Raises LayerViolationError if invalid.

    operation: 'enrichment' | 'authority' | 'promotion' | 'reingestion'
    """
    validators = {
        "enrichment": validate_enrichment_apply,
        "authority": validate_authority_apply,
        "promotion": validate_promotion,
        "reingestion": validate_reingestion,
    }
    validator = validators.get(operation)
    if not validator:
        raise ValueError(f"Unknown operation: {operation}")

    violations = validator(before, updates)
    if violations:
        raise LayerViolationError(
            f"Layer boundary violation(s) in {operation}: " + "; ".join(violations)
        )
