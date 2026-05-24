## Context

The preceding `scientific-affiliation-normalization` change makes affiliation data structurally available. This change defines how UKIP should reconcile those normalized affiliation candidates to canonical international organization records.

The main target registry is **Research Organization Registry (ROR)** because it is open, research-focused, globally used, and designed to identify research organizations. OpenAlex institutions and Wikidata can provide supporting identifiers, aliases, and context.

## Goals / Non-Goals

**Goals:**
- Resolve institution affiliation candidates to canonical authority records.
- Use ROR as the primary standard when available.
- Use OpenAlex and Wikidata as supporting evidence.
- Score candidates transparently.
- Avoid unsafe auto-linking for ambiguous institutions.
- Persist accepted/rejected decisions for reuse.

**Non-Goals:**
- Full organization hierarchy management.
- Paid/proprietary sources such as Ringgold, Scopus Affiliation ID, or WoS Organization Enhanced in the first pass.
- Reprocessing the entire historical corpus automatically.
- Replacing author authority resolution.
- Making external registry calls mandatory during normal dashboard rendering.

## Registry Strategy

### Primary: ROR

Use ROR for:

- Stable organization ID
- Canonical name
- aliases / acronyms / labels
- country
- organization type
- website/domain when available
- external identifiers when available

### Secondary: OpenAlex Institutions

Use OpenAlex institutions for:

- Provider-native institution ID
- institution display name
- country code
- related works/authors context
- lineage when present
- ROR passthrough when OpenAlex already provides it

### Tertiary: Wikidata

Use Wikidata for:

- multilingual aliases
- country/city enrichment
- institutional relationships
- fallback disambiguation when ROR/OpenAlex are ambiguous

## Candidate Scoring

Candidate score SHOULD be explainable. Initial scoring:

- exact ROR match: strong automatic confidence
- OpenAlex ID match: strong provider confidence
- normalized name similarity
- alias/acronym match
- country match
- city/location match
- domain/website match
- co-occurring author/work context
- negative signal for country mismatch
- negative signal for weak generic names

Suggested thresholds:

- `>= 0.90`: auto-accept if identifier-backed or unambiguous
- `0.70 - 0.89`: review
- `< 0.70`: unresolved / no-link

## Proposed Flow

1. Scientific import/enrichment persists structured affiliations.
2. Resolver extracts institution candidates from `attributes_json`.
3. If candidate has ROR, look up/normalize by ROR.
4. If candidate lacks ROR, search ROR by name + country.
5. Optionally enrich candidate set with OpenAlex/Wikidata.
6. Score candidates and produce ranked match list.
7. Auto-accept high-confidence identifier-backed matches.
8. Queue ambiguous matches for review.
9. Persist accepted canonical institution as authority record.
10. Persist affiliation link from author/publication context to institution authority record.

## Persistence

Prefer reusing existing authority models if they can represent:

- field name: `affiliation` or `institution`
- canonical label
- authority source: `ror`, `openalex`, `wikidata`, `internal_nil`
- authority ID
- aliases
- confidence/status
- external IDs payload

If existing models cannot represent institution-specific metadata cleanly, add a small metadata JSON field or normalized helper table.

## API Shape

Potential endpoints:

- `POST /authority/institutions/reconcile/preview`
- `POST /authority/institutions/reconcile/apply`
- `GET /authority/institutions/review-queue`
- `POST /authority/institutions/review-queue/{id}/accept`
- `POST /authority/institutions/review-queue/{id}/reject`
- `GET /authority/institutions/{id}`

## Risks / Trade-offs

- **Risk: False positive institution merge.** Mitigation: auto-accept only identifier-backed or very high-confidence matches; otherwise review.
- **Risk: External registry availability.** Mitigation: cache registry results and never require live registry calls during dashboard rendering.
- **Risk: International name variants.** Mitigation: use aliases/acronyms/country and allow manual review.
- **Risk: Existing authority tables do not fit institutions perfectly.** Mitigation: reuse first where possible, add minimal metadata only if needed.

## Rollout Plan

1. Implement ROR adapter and parser.
2. Implement institution candidate extraction from normalized affiliation metadata.
3. Implement scoring and explainability.
4. Persist authority records and links.
5. Add preview/apply APIs.
6. Add review queue UI.
7. Feed canonical institution IDs into analytics in a later change.
