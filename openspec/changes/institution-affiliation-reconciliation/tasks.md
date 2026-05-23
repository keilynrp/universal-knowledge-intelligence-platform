## 1. Registry adapters

- [x] 1.1 Add ROR adapter with lookup by ROR ID and search by name/country.
- [x] 1.2 Normalize ROR URLs and bare ROR IDs into one comparable representation.
- [x] 1.3 Parse ROR candidate fields: id, name, aliases, acronyms, country, type, links, external IDs.
- [x] 1.4 Add adapter tests with representative ROR payloads.
- [x] 1.5 Define optional OpenAlex/Wikidata support hooks without making them mandatory.

## 2. Candidate extraction

- [x] 2.1 Add helper to extract institution candidates from `RawEntity.attributes_json`.
- [x] 2.2 Support `canonical_affiliations` as primary input.
- [x] 2.3 Support `author_affiliations[].institutions[]` as secondary input.
- [x] 2.4 Fall back to legacy `affiliations` text when structured data is unavailable.
- [x] 2.5 Deduplicate extracted candidates by ROR, OpenAlex ID, then normalized name/country.

## 3. Reconciliation scoring

- [x] 3.1 Implement name normalization for institution strings, aliases, acronyms, and punctuation.
- [x] 3.2 Score exact ROR matches as high confidence.
- [x] 3.3 Score OpenAlex ID matches as high confidence when candidate links to same institution.
- [x] 3.4 Score name/alias/country/domain signals with explainable breakdown.
- [x] 3.5 Penalize country mismatch and generic/ambiguous organization names.
- [x] 3.6 Add tests for exact, alias, ambiguous, and mismatch scenarios.

## 4. Persistence and authority links

- [x] 4.1 Map accepted institution matches into existing authority records or add minimal institution metadata support.
- [x] 4.2 Persist canonical institution authority source and IDs (`ror`, `openalex`, `wikidata` where available).
- [x] 4.3 Persist accepted/rejected review decisions.
- [x] 4.4 Persist author/publication affiliation links where existing link model supports them.
- [x] 4.5 Add tests proving accepted matches are reused for future imports.

## 5. API endpoints

- [x] 5.1 Add preview endpoint for institution reconciliation candidates.
- [x] 5.2 Add apply endpoint for auto-accepting safe matches.
- [x] 5.3 Add review queue endpoint for ambiguous matches.
- [x] 5.4 Add accept/reject review actions.
- [x] 5.5 Require editor+ for preview and admin/editor roles for review decisions according to existing authority permissions.

## 6. UI

- [x] 6.1 Add compact institution reconciliation panel or queue under Authority.
- [x] 6.2 Show candidate evidence: name match, alias, country, ROR, OpenAlex ID, and score breakdown.
- [x] 6.3 Allow accept/reject with visible confidence and provenance.
- [x] 6.4 Link resolved institutions back to affected authors/publications where available.

## 7. Validation

- [x] 7.1 Add focused backend tests for ROR adapter, scoring, persistence, and API auth.
- [x] 7.2 Add frontend smoke test or component test for review queue rendering.
- [x] 7.3 Run `npx openspec validate institution-affiliation-reconciliation --strict`.
- [x] 7.4 Run focused authority and scientific affiliation tests.
