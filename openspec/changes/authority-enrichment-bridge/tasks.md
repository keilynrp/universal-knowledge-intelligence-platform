## 1. Product and governance framing

- [ ] 1.1 Declare authority enrichment bridge as a subordinate capability of `canonical-semantic-data-governance`.
- [ ] 1.2 Document dependency on `entity-provenance-layering`, `institution-affiliation-reconciliation`, and `geographic-entity-semantic-layer`.
- [ ] 1.3 Define first implementation slice: enriched authors, ORCID hints, affiliations, DOI context, and institution candidates.
- [ ] 1.4 Define second implementation slice: places, venues, concepts, and broader identifier families.

## 2. Candidate extraction service

- [ ] 2.1 Add service to scan source and enrichment evidence from `RawEntity.attributes_json`.
- [ ] 2.2 Extract person candidates from `enrichment_authors`, `enrichment_author_orcids`, source author fields, and DOI/year context.
- [ ] 2.3 Extract institution candidates from structured affiliations, source affiliation fields, OpenAlex institution hints, and ROR-ready evidence.
- [ ] 2.4 Extract identifier candidates from DOI, ORCID, ROR, OpenAlex, Wikidata, ISBN, ISSN, and local canonical IDs.
- [ ] 2.5 Deduplicate candidates by authority identifier first, then normalized label/context.
- [ ] 2.6 Add tests for enriched, source-only, duplicate, sparse, and conflicting evidence.

## 3. Authority readiness status

- [ ] 3.1 Add domain/dataset authority readiness aggregation endpoint.
- [ ] 3.2 Return counts for extracted, resolved, review-required, rejected, failed, and stale candidates.
- [ ] 3.3 Detect stale candidates when source or enrichment evidence changes after extraction.
- [ ] 3.4 Include candidate family breakdowns for persons, institutions, identifiers, places, venues, and concepts.
- [ ] 3.5 Add backend tests for readiness state transitions.

## 4. Resolution and review integration

- [ ] 4.1 Feed extracted author candidates into the existing author authority review queue.
- [ ] 4.2 Feed extracted institution candidates into institution reconciliation and authority records.
- [ ] 4.3 Preserve evidence references that explain which source or enrichment fields produced each candidate.
- [ ] 4.4 Prevent rejected candidates from being recreated unless evidence changes.
- [ ] 4.5 Add tests for queue creation, review-required thresholds, reject reuse, and tenant scoping.

## 5. Canonical promotion

- [ ] 5.1 Define canonical promotion payload for accepted authority decisions.
- [ ] 5.2 Promote accepted person candidates into `canonical_authors` with identifiers, aliases, confidence, and provenance.
- [ ] 5.3 Promote accepted institution candidates into `canonical_affiliations` or `canonical_institutions` with ROR/OpenAlex/Wikidata IDs where available.
- [ ] 5.4 Promote accepted identifier candidates into `canonical_identifiers`.
- [ ] 5.5 Preserve original source and enrichment values without overwriting them.
- [ ] 5.6 Add tests proving graph/RAG/analytics can read promoted canonical values.

## 6. Authority UI

- [ ] 6.1 Add authority readiness card to `/authority`.
- [ ] 6.2 Add extraction CTA for enriched datasets and source-only datasets.
- [ ] 6.3 Show candidate origin: source, enrichment, prior authority, or manual.
- [ ] 6.4 Show evidence, confidence, review state, downstream impact, and stale/failed diagnostics.
- [ ] 6.5 Add EN/ES translations for readiness states, candidate families, and review provenance.
- [ ] 6.6 Add focused frontend tests for readiness rendering and candidate origin labels.

## 7. Downstream integration

- [ ] 7.1 Update graph materialization to prefer canonical authority-resolved authors and institutions.
- [ ] 7.2 Update RAG evidence labels to prefer accepted canonical authority labels when available.
- [ ] 7.3 Update author productivity, coauthorship, geographic analysis, and executive reporting to surface authority coverage.
- [ ] 7.4 Add regression tests for analytics behavior with source-only, enriched-unresolved, and authority-resolved datasets.

## 8. Validation

- [ ] 8.1 Run focused backend authority, enrichment, institution reconciliation, and graph materialization tests.
- [ ] 8.2 Run focused frontend Authority tests and lint/type checks.
- [ ] 8.3 Run `npx openspec validate authority-enrichment-bridge --strict`.
- [ ] 8.4 Manual smoke test: import/enrich a small dataset, extract candidates, review one accepted and one rejected candidate, and verify downstream canonical usage.
