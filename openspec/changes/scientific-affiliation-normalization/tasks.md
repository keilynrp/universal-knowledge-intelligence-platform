## 1. Normalized enrichment schema

- [x] 1.1 Add `CanonicalAffiliation` and `AuthorAffiliation` Pydantic models to `backend/schemas_enrichment.py`.
- [x] 1.2 Add optional `canonical_affiliations` and `author_affiliations` fields to `EnrichedRecord`.
- [x] 1.3 Preserve backwards compatibility for existing adapters that only set `affiliations`.
- [x] 1.4 Add schema tests for empty, text-only, and structured affiliation records.

## 2. OpenAlex affiliation mapping

- [x] 2.1 Parse `authorships[].author.id`, `display_name`, `orcid`, `author_position`, and raw order.
- [x] 2.2 Parse `authorships[].institutions[]` fields: `id`, `display_name`, `ror`, `country_code`, `type`, and `lineage`.
- [x] 2.3 Build `author_affiliations` preserving author-to-institution relationships.
- [x] 2.4 Build `canonical_affiliations` deduplicated by ROR, OpenAlex ID, then normalized name/country.
- [x] 2.5 Populate legacy `affiliations` strings from canonical affiliations for old consumers.
- [x] 2.6 Add OpenAlex fixture test with multiple authors, duplicate institutions, one ROR-backed institution, and one institution without ROR.

## 3. Persistence contract

- [x] 3.1 Update `_ingest_records` to persist `canonical_affiliations` and `author_affiliations` into `attributes_json`.
- [x] 3.2 Continue storing simple `affiliation` and `affiliations` keys for geographic fallback and backwards compatibility.
- [x] 3.3 Ensure JSON serialization handles Pydantic v1/v2 model dumps and plain dicts.
- [x] 3.4 Add ingestion persistence test from `EnrichedRecord` to `RawEntity.attributes_json`.

## 4. ROR-ready authority integration

- [x] 4.1 Define identifier normalization rules for ROR URLs vs bare ROR IDs.
- [x] 4.2 Add helper to extract institution authority candidates from persisted affiliation attributes.
- [x] 4.3 Ensure candidate shape can feed existing authority affiliation flow without reparsing raw OpenAlex JSON.
- [x] 4.4 Add tests for ROR-backed and OpenAlex-only institution candidates.

## 5. Analytics consumers

- [x] 5.1 Update geographic extraction to prefer `canonical_affiliations[].country_code`.
- [x] 5.2 Keep existing affiliation text parsing as fallback.
- [x] 5.3 Add geographic test proving country extraction works from structured affiliation metadata.
- [x] 5.4 Review dashboard/report copy for institution-level evidence opportunities.

## 6. Documentation and validation

- [x] 6.1 Add codemap note documenting the scientific affiliation contract.
- [x] 6.2 Run focused scientific connector/enrichment tests.
- [x] 6.3 Run `npx openspec validate scientific-affiliation-normalization --strict`.
- [x] 6.4 Run `pytest backend/tests/test_scientific_connectors.py backend/tests/test_sprint63.py -q` or equivalent focused suite.
