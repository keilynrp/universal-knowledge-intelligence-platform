# ADR-001: Entity Provenance Layering

## Status

Accepted

## Date

2026-05-24

## Context

Entities in UKIP pass through multiple processing stages: raw ingestion, normalization, external enrichment, and authority resolution. Without explicit layer separation, later stages silently overwrote earlier data, making it impossible to audit provenance, roll back enrichments, or trace how a canonical value was derived.

## Decision

Adopt a 4-layer provenance model for all entity data:

1. **Source** — Raw ingested values, immutable after import.
2. **Enrichment** — Values added by external providers (OpenAlex, WoS, Scholar). Cannot overwrite source.
3. **Canonical** — Normalized/reconciled values (deduplicated names, merged identifiers). Cannot overwrite source or enrichment.
4. **Authority** — Resolved values from authoritative registries (ORCID, ROR, Wikidata, VIAF). Cannot overwrite any prior layer.

Each layer is queryable independently. Rollback of a higher layer preserves all lower layers intact.

Layer assignment is determined by `classify_layer(field_name)` in `backend/services/layer_boundaries.py`. Enforcement is via `enforce_layer_boundaries(operation)` which validates mutations before persistence.

## Consequences

- **Easier:** Full audit trail, safe enrichment rollback, clear provenance badges in UI, conflict detection during authority promotion.
- **Harder:** Write operations require layer classification; updates must specify which layer they target; storage is slightly larger due to preserved history.

## References

- Spec: `entity-provenance-layering`
- Implementation: `backend/services/layer_boundaries.py`, `backend/services/entity_provenance.py`
- Tests: `tests/test_layer_boundaries.py` (31 tests), `tests/test_entity_provenance.py` (9 tests)
