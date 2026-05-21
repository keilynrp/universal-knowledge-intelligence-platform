## Why

UKIP's scientific enrichment tests cover the enrichment process, but the data contract still loses important institutional semantics. OpenAlex provides author-level institutional affiliations, OpenAlex institution IDs, ROR IDs, country codes, and institution metadata inside `authorships[].institutions[]`. Today UKIP mostly preserves authors and raw responses, while affiliation data is either missing, flattened, or only usable as free text.

That weakens strategic research use cases:

- Institutional portfolio benchmarking
- Research Organization Registry (ROR) integration
- Author-institution authority linking
- Geographic and collaboration analytics
- Evidence-backed stakeholder briefs
- Institution-level impact/readiness reporting

The platform needs a normalized affiliation contract that preserves the relationship:

```
publication -> author -> institution -> ROR/OpenAlex/country
```

## What Changes

- **New**: Structured affiliation fields on the normalized scientific enrichment object.
- **New**: OpenAlex parser support for `authorships[].institutions[]`, including ROR and OpenAlex institution IDs.
- **New**: Persistence contract for author affiliations and canonical affiliations in `RawEntity.attributes_json`.
- **New**: ROR-ready identifiers and institution aliases that downstream authority resolution can consume.
- **Modified**: Scientific import/enrichment ingestion must persist affiliations as structured data, not only as a semicolon-delimited string.
- **Modified**: Geographic and institutional analytics should prefer structured affiliation objects before text fallback.

## Capabilities

### New Capabilities

- `scientific-affiliation-contract`: Normalized scientific affiliation schema covering author-level and canonical institution-level affiliations.
- `openalex-affiliation-mapping`: OpenAlex adapter mapping for institutions, ROR IDs, countries, and author-affiliation relationships.
- `affiliation-persistence-contract`: Persistence rules for storing affiliation structures in `attributes_json`.
- `ror-ready-institution-identifiers`: Stable institution identifier contract prepared for ROR authority resolution.

### Modified Capabilities

- `semantic-scholar-adapter`, `pubmed-cascade-integration`, and future scientific connectors should remain compatible with the enriched affiliation fields, even when they only provide text affiliation.
- `dashboard-summary` and geographic analysis should consume structured institution/country data when available.

## Impact

- **Backend schema**: Extend `EnrichedRecord` with structured affiliation fields.
- **OpenAlex adapter**: Parse author-level institutions from `authorships`.
- **Ingestion**: Persist structured affiliations in `RawEntity.attributes_json`.
- **Analytics**: Prefer `canonical_affiliations` and author-affiliation metadata for country/institution extraction.
- **Tests**: Add contract tests from realistic OpenAlex fixture through normalized object and persisted entity attributes.

## Success Criteria

- Given an OpenAlex work with `authorships[].institutions[].ror`, UKIP preserves the ROR ID in normalized enrichment output.
- Given multiple authors with different institutions, UKIP preserves author-to-institution relationships.
- Given duplicate institutions across authors, UKIP stores one canonical institution entry and references it from author affiliations.
- Geographic analytics can use structured institution country codes without relying on brittle text parsing.
- Future ROR resolution can consume the stored identifiers without reparsing OpenAlex raw JSON.
