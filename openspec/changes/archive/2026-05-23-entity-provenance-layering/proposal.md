## Why

Entity detail currently mixes fields from different data origins in one surface. This creates confusion:

- `source` can mean original ingestion source, while `enrichment_source` means external enrichment provider.
- `canonical_id` may be empty because it was not provided, not normalized, or not applicable.
- `entity_type` may be empty because the original data lacked it, because mapping failed, or because the provider does not expose that concept.
- Scientific enrichment fields from OpenAlex/Crossref/PubMed can appear alongside original user-imported fields without provenance.

For research stakeholders, this weakens trust. They need to know what came from the original dataset, what UKIP inferred, and what external registries added.

## What Changes

- **New**: Entity provenance layering contract for detail views.
- **New**: Separate display sections for original ingestion data, UKIP normalized identity, external enrichment, and audit/provenance.
- **New**: Field-state labels that explain nulls: not provided, pending normalization, unresolved enrichment, not applicable.
- **New**: Source terminology split: ingestion source vs enrichment provider vs authority source.
- **Modified**: Entity detail UI SHALL avoid rendering duplicate ambiguous labels like "Source" without context.
- **Modified**: API/detail serializer SHOULD expose provenance metadata or enough raw fields for the frontend to derive it safely.

## Capabilities

### New Capabilities

- `entity-provenance-layering`: Layered entity detail model separating original, normalized, enrichment, and authority data.
- `entity-detail-null-semantics`: User-facing field states that explain why a value is missing.
- `source-terminology-contract`: Standard labels for ingestion source, enrichment provider, and authority source.

### Modified Capabilities

- `entity-attribute-schema`: Attributes JSON should preserve original columns and enriched metadata without label collision.
- `scientific-affiliation-contract`: Structured scientific affiliation data appears under external enrichment, not original ingestion.

## Impact

- **Frontend**: Entity detail page sections and labels change. Existing values are reorganized, not removed.
- **Backend**: May require a serializer helper to provide layered field groups and null reasons.
- **Data model**: No immediate migration required; uses existing `RawEntity`, `attributes_json`, `normalized_json`, enrichment fields, and import batch metadata.
- **Tests**: Add detail rendering/API tests for source separation and null explanation.

## Success Criteria

- "Source" no longer appears ambiguously twice.
- Users can tell whether a field came from original ingestion, UKIP normalization, external enrichment, or authority resolution.
- Null canonical ID and entity type are explained with actionable state, not just `—`.
- Scientific providers like OpenAlex/Crossref are shown as enrichment providers, not confused with original data source.
- Original imported fields remain visible without being overwritten by enrichment fields.
