# ADR-002: Canonical Semantic Data Governance

## Status

Accepted

## Date

2026-05-24

## Context

The platform ingests data from heterogeneous sources (CSV uploads, REST APIs, OpenAlex, Crossref) with varying field names and semantics. Without governance, field mappings were ad hoc, canonical identifiers inconsistent, and linked-data exports unreliable.

## Decision

Implement a governed canonical data pipeline:

1. **Source Profiling** — Automatically analyze ingested data to infer field types, semantic roles, and candidate identifiers (`backend/services/source_profiler.py`).
2. **Mapping Suggestions** — Generate field-to-canonical mapping proposals with confidence scores. Low-confidence suggestions require human review (`backend/services/mapping_suggestions.py`).
3. **Canonical Model Boundary** — Enforce that only validated, reviewed mappings can promote data into the canonical layer. GenAI-assisted mappings follow the same governance path.
4. **Linked-Data Output** — Export governed canonical data as JSON-LD aligned to standard vocabularies (schema.org, BIBFRAME, EDM, DCAT).

## Consequences

- **Easier:** Consistent canonical identifiers across sources, reliable linked-data exports, audit trail for every mapping decision.
- **Harder:** New sources require profiling + review before canonical integration; mapping suggestions add a review step for low-confidence fields.

## References

- Spec: `canonical-semantic-data-governance`
- Implementation: `backend/services/source_profiler.py`, `backend/services/mapping_suggestions.py`, `backend/exporters/jsonld_exporter.py`
