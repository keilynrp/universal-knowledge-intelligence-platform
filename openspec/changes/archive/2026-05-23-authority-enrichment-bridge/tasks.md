## 1. Product and governance framing

- [x] 1.1 Declare authority enrichment bridge as a subordinate capability of `canonical-semantic-data-governance`.
- [x] 1.2 Document dependency on `entity-provenance-layering`, `institution-affiliation-reconciliation`, and `geographic-entity-semantic-layer`.
- [x] 1.3 Define first implementation slice: enriched authors, ORCID hints, affiliations, DOI context, and institution candidates.
- [x] 1.4 Define second implementation slice: places, venues, concepts, and broader identifier families.

## 2. Candidate extraction service

- [x] 2.1 Add service to scan source and enrichment evidence from `RawEntity.attributes_json`.
- [x] 2.2 Extract person candidates from `enrichment_authors`, `enrichment_author_orcids`, source author fields, and DOI/year context.
- [x] 2.3 Extract institution candidates from structured affiliations, source affiliation fields, OpenAlex institution hints, and ROR-ready evidence.
- [x] 2.4 Extract identifier candidates from DOI, ORCID, ROR, OpenAlex, Wikidata, ISBN, ISSN, and local canonical IDs.
- [x] 2.5 Deduplicate candidates by authority identifier first, then normalized label/context.
- [x] 2.6 Add tests for enriched, source-only, duplicate, sparse, and conflicting evidence.

## 3. Authority readiness status

- [x] 3.1 Add domain/dataset authority readiness aggregation endpoint.
- [x] 3.2 Return counts for extracted, resolved, review-required, rejected, failed, and stale candidates.
- [x] 3.3 Detect stale candidates when source or enrichment evidence changes after extraction.
- [x] 3.4 Include candidate family breakdowns for persons, institutions, identifiers, places, venues, and concepts.
- [x] 3.5 Add backend tests for readiness state transitions.

## 4. Resolution and review integration

- [x] 4.1 Feed extracted author candidates into the existing author authority review queue.
- [x] 4.2 Feed extracted institution candidates into institution reconciliation and authority records.
- [x] 4.3 Preserve evidence references that explain which source or enrichment fields produced each candidate.
- [x] 4.4 Prevent rejected candidates from being recreated unless evidence changes.
- [x] 4.5 Add tests for queue creation, review-required thresholds, reject reuse, and tenant scoping.

## 5. Canonical promotion

- [x] 5.1 Define canonical promotion payload for accepted authority decisions.
- [x] 5.2 Promote accepted person candidates into `canonical_authors` with identifiers, aliases, confidence, and provenance.
- [x] 5.3 Promote accepted institution candidates into `canonical_affiliations` or `canonical_institutions` with ROR/OpenAlex/Wikidata IDs where available.
- [x] 5.4 Promote accepted identifier candidates into `canonical_identifiers`.
- [x] 5.5 Preserve original source and enrichment values without overwriting them.
- [x] 5.6 Add tests proving graph/RAG/analytics can read promoted canonical values.

## 6. Authority UI

- [x] 6.1 Add authority readiness card to `/authority`.
- [x] 6.2 Add extraction CTA for enriched datasets and source-only datasets.
- [x] 6.3 Show candidate origin: source, enrichment, prior authority, or manual.
- [x] 6.4 Show evidence, confidence, review state, downstream impact, and stale/failed diagnostics.
- [x] 6.5 Add EN/ES translations for readiness states, candidate families, and review provenance.
- [x] 6.6 Add focused frontend tests for readiness rendering and candidate origin labels.

## 7. Downstream integration

- [x] 7.1 Update graph materialization to prefer canonical authority-resolved authors and institutions.
- [x] 7.2 Update RAG evidence labels to prefer accepted canonical authority labels when available.
- [x] 7.3 Update author productivity, coauthorship, geographic analysis, and executive reporting to surface authority coverage.
- [x] 7.4 Add regression tests for analytics behavior with source-only, enriched-unresolved, and authority-resolved datasets.

## 8. Validation

- [x] 8.1 Run focused backend authority, enrichment, institution reconciliation, and graph materialization tests.
- [x] 8.2 Run focused frontend Authority tests and lint/type checks.
- [x] 8.3 Run `npx openspec validate authority-enrichment-bridge --strict`.
- [x] 8.4 Manual smoke test: import/enrich a small dataset, extract candidates, review one accepted and one rejected candidate, and verify downstream canonical usage.
