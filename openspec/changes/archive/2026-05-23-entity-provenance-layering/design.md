## Context

UKIP's `RawEntity` is intentionally broad. It stores original ingestion fields, normalized labels, enrichment results, quality scores, and provider metadata. This is flexible but makes entity detail hard to interpret unless the UI separates provenance layers.

Current conceptual layers:

1. **Original ingestion data**
   - Source connector/file/demo/API import
   - Import batch/file/job
   - Original columns
   - User-provided identifiers such as SKU, local code, DOI, catalog ID

2. **UKIP normalized identity**
   - `primary_label`
   - `secondary_label`
   - `canonical_id`
   - `entity_type`
   - `domain`
   - `validation_status`
   - quality/confidence

3. **External enrichment**
   - `enrichment_source`
   - DOI resolved by provider
   - citation count
   - concepts/topics
   - authors
   - affiliations
   - publisher/venue
   - provider IDs

4. **Authority/provenance/audit**
   - authority records/links
   - resolver source
   - import batch metadata
   - timestamps

## Goals / Non-Goals

**Goals:**
- Make entity detail trustworthy and explainable.
- Separate ingestion source, enrichment provider, and authority source.
- Preserve original user/imported values even when UKIP normalizes or enriches them.
- Explain nulls with meaningful field states.
- Keep changes additive and compatible with existing entities.

**Non-Goals:**
- Immediate database migration.
- Rewriting the ingestion pipeline.
- Removing existing fields from APIs.
- Full lineage graph UI.

## Decisions

### D1: UI sections reflect provenance layers

**Decision:** Entity detail SHALL render grouped sections:

- Original ingestion
- UKIP normalized identity
- External enrichment
- Authority and audit

**Rationale:** This mirrors how stakeholders reason about data trust: input, interpretation, external evidence, and audit.

### D2: Rename labels, not database fields

**Decision:** Keep backend field names but use precise UI labels:

- `source` -> "Ingestion source"
- `enrichment_source` -> "Enrichment provider"
- authority record source -> "Authority source"

**Rationale:** Renaming DB fields is disruptive. Label clarity solves the immediate stakeholder problem.

### D3: Nulls need reason codes

**Decision:** Detail rendering should use field states:

- `not_provided`: absent from original ingestion
- `pending_normalization`: UKIP has not resolved it yet
- `unresolved_enrichment`: enrichment provider did not resolve it
- `not_applicable`: field does not apply to this entity/source
- `unknown`: missing without reliable reason

**Rationale:** A plain dash makes data look broken. A reason code makes the data lifecycle understandable.

### D4: Derived view can be built frontend-first, backend serializer later

**Decision:** Initial implementation may derive sections in the frontend from existing entity payload. Backend serializer is preferred if the logic becomes duplicated.

**Rationale:** The data already exists; the risk is presentation. A frontend-first implementation is fast, but tests should protect terminology and null semantics.

## Proposed Detail Sections

### Original Ingestion

- Ingestion source
- Import batch / file / connector
- Original identifier
- Original type/category
- Original labels
- Original columns

### UKIP Normalized Identity

- Primary label
- Secondary label
- Canonical ID
- Entity type
- Domain
- Validation status
- Quality score

### External Enrichment

- Enrichment provider
- DOI
- Citation count
- Concepts/topics
- Authors
- Affiliations
- Publisher/venue
- Provider-specific IDs

### Authority and Audit

- Authority source
- Canonical authority record
- Resolver confidence
- Import created/updated timestamps
- Review status

## Null Semantics Examples

- Canonical ID empty:
  - if original identifier exists but no normalized ID: "Pending normalization"
  - if no source identifier exists: "Not provided in original ingestion"

- Entity type empty:
  - if original type/category exists: "Pending type mapping"
  - if no original type/category exists: "Not provided in original ingestion"

- Enrichment DOI empty:
  - if enrichment source exists: "Not resolved by enrichment provider"
  - if no enrichment attempted: "Enrichment not run"

## Risks / Trade-offs

- **Risk: Frontend derivation duplicates backend semantics.** Mitigation: Move to serializer once field-state logic stabilizes.
- **Risk: Existing users expect old labels.** Mitigation: Keep values, improve labels and grouping.
- **Risk: Some old records lack import batch metadata.** Mitigation: Render "Legacy record" or "Unknown ingestion source" explicitly.

## Rollout Plan

1. Add field grouping helper for entity detail.
2. Add null-state helper.
3. Update detail UI labels and sections.
4. Add tests for source label separation and null explanations.
5. Consider backend serializer after first UI pass.
