## Context

UKIP's authority module already covers several operational needs: generic resolution, author resolution, batch resolution, review queue management, normalization rules, and author-affiliation link review. In parallel, the enrichment pipeline stores high-value evidence in record attributes such as enriched authors, ORCID hints, affiliations, concepts, provider sources, DOI context, and citation metadata.

The missing product and architecture layer is a bridge that converts enrichment evidence into governed authority candidates. Without that bridge, authority control remains useful but too manual, and downstream modules cannot consistently know whether a dataset is source-only, enriched-but-unresolved, authority-reviewed, or canonically promoted.

## Goals / Non-Goals

**Goals:**

- Define authority resolution as a governed pipeline stage after ingestion and enrichment.
- Extract candidates from both source data and enrichment observations.
- Preserve provenance for every candidate, evidence field, provider, and review decision.
- Promote accepted authority decisions into canonical semantic fields and relationships.
- Expose authority readiness to product surfaces and downstream services.
- Keep manual review for ambiguous or high-impact identity decisions.

**Non-Goals:**

- Replace the existing authority router in one step.
- Treat OpenAlex, Crossref, ORCID, ROR, Wikidata, or any provider as universal truth.
- Auto-merge low-confidence person, institution, or place identities.
- Remove original source values after authority resolution.
- Require enrichment before any authority work can begin.

## Candidate Sources

Authority candidate extraction SHALL consider these evidence layers:

- Original source fields selected by mapping suggestions or user configuration.
- Normalized source fields produced by UKIP transformations.
- Enrichment observations such as authors, ORCID hints, affiliations, DOI metadata, concepts, sources, and identifiers.
- Previously accepted authority records and normalization rules.
- Domain-specific subordinate outputs such as institution reconciliation and geographic entity reconciliation.

## Candidate Families

The bridge SHOULD support these candidate families incrementally:

- `person`: authors, creators, contributors, researchers, reviewers.
- `institution`: affiliations, organizations, funders, publishers.
- `identifier`: DOI, ORCID, ROR, OpenAlex, Wikidata, ISBN, ISSN, local IDs.
- `place`: country, city, coordinates, institutional location, study area.
- `venue`: journal, conference, repository, publisher venue.
- `concept`: topics, keywords, controlled vocabulary terms.

## Authority Readiness States

Datasets and domains SHOULD expose a compact authority readiness state:

- `not_started`: no authority extraction has run.
- `source_candidates_ready`: source-derived candidates exist, but enrichment context is limited.
- `enrichment_candidates_ready`: enriched evidence is available for authority extraction.
- `review_required`: candidates exist and require review.
- `partially_resolved`: some candidates have accepted authority decisions.
- `resolved`: required authority candidates are accepted or intentionally dismissed.
- `stale`: source or enrichment evidence changed after the last authority extraction.
- `failed`: extraction or resolution failed with diagnostic details.

## Promotion Rules

Accepted authority decisions SHALL promote to canonical semantics only through explicit rules:

- Preserve original source values in source provenance.
- Preserve enrichment observations in enrichment provenance.
- Persist accepted authority identifiers and labels as canonical authority links.
- Create or update canonical relationship fields such as `canonical_authors`, `canonical_affiliations`, `canonical_institutions`, `canonical_places`, and `canonical_identifiers` only when the accepted decision is compatible with the target entity type.
- Attach confidence, resolver source, reviewer/action metadata, timestamps, and evidence references.
- Never auto-promote ambiguous or conflicting candidates without review.

## UI Decisions

### D1: Authority must show pipeline position

**Decision:** The Authority module SHALL show whether a candidate came from source ingestion, enrichment, prior authority records, or manual review.

**Rationale:** Research stakeholders need to understand why UKIP trusts a name, affiliation, or identifier.

### D2: Readiness is domain-level and record-level

**Decision:** Authority readiness SHALL be available as aggregate domain status and as drill-down candidate detail.

**Rationale:** Executive workflows need summary confidence, while data stewards need granular evidence.

### D3: Review does not equal enrichment

**Decision:** Authority review actions SHALL be distinct from enrichment refresh actions.

**Rationale:** Enrichment adds observations; authority review decides identity.

## Downstream Contracts

Downstream modules SHOULD consume authority-resolved fields when available:

- Author productivity uses canonical person IDs and accepted aliases.
- Coauthorship networks use canonical person relationships.
- Geographic analysis uses canonical institutions and places.
- RAG uses authority-resolved evidence labels and identifiers for grounded retrieval.
- Executive reports cite canonical authority links and provenance when making institution, author, or geography claims.

## Open Questions

- Which candidate families should be included in the first implementation slice: authors and institutions only, or identifiers too?
- Should candidate extraction run automatically after enrichment completion or be triggered from Authority UI first?
- What confidence thresholds are safe for auto-accept in tenant-controlled deployments?
- Should canonical promoted fields live in `attributes_json` initially or move into dedicated canonical tables?
- How should stale authority decisions be invalidated when provider enrichment changes?

## Rollout Plan

1. Define candidate extraction contracts for enriched authors, ORCID hints, affiliations, DOI, and institution evidence.
2. Add authority readiness aggregation for dataset/domain views.
3. Expose readiness and extraction actions in the Authority module.
4. Generate author and institution candidates from enriched records.
5. Promote accepted decisions into canonical semantic fields with provenance.
6. Wire canonical authority-resolved fields into graph, RAG, analytics, and executive reports.
7. Expand candidate families to places, venues, identifiers, and concepts.
