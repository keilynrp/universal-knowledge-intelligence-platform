# ADR-003: Authority Resolution Pipeline

## Status

Accepted

## Date

2026-05-24

## Context

Entities often refer to the same real-world person, institution, or concept using different names or identifiers. Without a resolution layer, duplicates proliferate and data quality degrades. External authority registries (ORCID, ROR, Wikidata, VIAF, OpenAlex) provide canonical identifiers but require orchestration, scoring, and human review for ambiguous cases.

## Decision

Implement a multi-stage authority resolution pipeline:

1. **Candidate Extraction** — Extract candidates from source and enrichment layers across 6 families: person, institution, identifier, place, venue, concept (`backend/services/authority_candidate_extraction.py`).
2. **Readiness Tracking** — State machine per dataset tracking extraction, resolution, review, and staleness per family (`backend/services/authority_readiness.py`).
3. **Multi-Source Resolution** — Parallel queries to ORCID, ROR, Wikidata, VIAF, DBpedia, OpenAlex with weighted scoring (`backend/authority/`).
4. **Canonical Promotion** — Resolved candidates can be promoted to canonical layer with conflict detection. Auto-accept for high-confidence + governed policy; manual review otherwise (`backend/services/authority_promotion.py`).
5. **Layer Boundary Enforcement** — Promotions never overwrite source or enrichment data.

## Consequences

- **Easier:** Deduplicated entities with authoritative identifiers, sameAs URIs for linked data, confidence-based automation reduces manual work.
- **Harder:** Pipeline complexity; stale detection requires re-evaluation when evidence changes; conflict resolution needs human judgment.

## References

- Specs: `authority-enrichment-bridge`, `institution-affiliation-reconciliation`
- Implementation: `backend/authority/`, `backend/services/authority_candidate_extraction.py`, `backend/services/authority_readiness.py`, `backend/services/authority_promotion.py`
