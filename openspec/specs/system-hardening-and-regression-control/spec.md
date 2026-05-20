## ADDED Requirements

### Requirement: System hardening plan is the source of truth
The system SHALL maintain this specification as the canonical planning layer for cross-cutting technical debt, regression control, and future hardening work. Feature-specific specs SHALL remain responsible for their own domain behavior, but this spec SHALL define the integration contracts and sequencing rules that prevent recurring regressions.

#### Scenario: New cross-cutting work is proposed
- **WHEN** a change affects domain scope, derived data freshness, enrichment, graph, RAG, executive dashboards, or entity detail presentation
- **THEN** the change is linked to this spec
- **AND** the affected feature spec is linked or created before implementation

#### Scenario: Future specs extend current capabilities
- **WHEN** a future spec introduces new analytics, graph, enrichment, RAG, or dashboard behavior
- **THEN** it declares which system contract it depends on: domain scope, derived data status, entity metadata view, graph materialization, semantic signal generation, RAG indexing, or delivery/reporting

### Requirement: Domain scope contract is explicit and shared
The system SHALL define one shared domain scope contract used by frontend state, backend APIs, analytics queries, graph queries, reports, enrichment views, and RAG context.

Supported domain scope values SHALL be:
- `all`: aggregate over all active domains available to the current tenant or global context
- `domain:{id}`: one concrete domain
- `legacy_default`: compatibility scope for historical records where the domain is `default` or null

Raw strings such as `default`, empty string, or ad hoc `all` handling SHALL NOT be interpreted independently by feature code after the contract exists.

#### Scenario: User authenticates with no ingested domains
- **WHEN** the authenticated workspace has no domains with active ingested records
- **THEN** the domain selector defaults to `all`
- **AND** all domain-aware views render empty or zero-state data without a blank selector

#### Scenario: User authenticates with ingested domains
- **WHEN** the authenticated workspace has one or more domains with active records
- **THEN** the domain selector exposes `all` plus the concrete domains
- **AND** the first concrete domain is ordered by earliest ingested entity
- **AND** any explicit user-selected scope is persisted only if it is still valid

#### Scenario: User changes domain scope
- **WHEN** the active domain scope changes
- **THEN** home, executive dashboard, graph, entity lists, reports, OLAP, RAG context, and analytics endpoints refresh from the new scope
- **AND** no view keeps stale values from the previous scope

### Requirement: Derived data freshness is observable
The system SHALL expose a derived data status contract for every tenant/domain/import/entity context that can depend on asynchronous or materialized computation.

The minimum tracked derived resources SHALL be:
- `enrichment`
- `graph`
- `semantic_keyword_signals`
- `rag_index`
- `executive_dashboard_snapshot`
- `report_readiness`

Each resource SHALL expose:
- `status`: `missing`, `pending`, `processing`, `ready`, `stale`, or `failed`
- `updated_at`
- `source_count`
- `derived_count`
- `last_error`
- `can_rebuild`
- `rebuild_endpoint` when applicable

#### Scenario: Enrichment completes
- **WHEN** enrichment completes for an entity or import batch
- **THEN** related graph, semantic signal, RAG index, executive dashboard, and report readiness statuses are marked `stale` or refreshed incrementally
- **AND** the UI can show progress without flicker or stale success indicators

#### Scenario: Executive dashboard has no visible progress
- **WHEN** enriched records exist but dashboard metrics are empty
- **THEN** derived data status explains whether the dashboard snapshot is missing, stale, failed, or blocked by scope mismatch

### Requirement: Entity metadata view normalizes detail fields
The system SHALL provide a canonical entity metadata view for UI and analytics reads. This view SHALL normalize DOI, canonical ID, entity type, affiliation, abstract/resumen, authors, journal/venue, year, document type, keywords, concepts, source, enrichment status, and quality status.

The UI SHALL consume this normalized view instead of re-implementing duplicate field cleanup per page or modal.

#### Scenario: Duplicate DOI fields exist
- **WHEN** DOI appears in `canonical_id`, `enrichment_doi`, or `attributes_json`
- **THEN** the metadata view emits one canonical DOI value
- **AND** duplicate DOI rows are not rendered in detail views

#### Scenario: Affiliation candidate is thematic
- **WHEN** a candidate affiliation equals a journal, venue, source, concept, or thematic label
- **THEN** the metadata view does not emit it as a physical/geographic affiliation
- **AND** the raw value remains available in provenance for audit

#### Scenario: Entity type is missing
- **WHEN** `entity_type` is null but source metadata identifies publication, author, institution, journal, concept, product, or other known type
- **THEN** the metadata view emits a best-effort normalized type with evidence

### Requirement: Analytics and graph read models are separated from routers
The system SHALL keep HTTP routers thin. Domain calculations for executive dashboards, graph visualization, stats, RAG indexing, and entity detail metadata SHALL live in services or read-model modules with unit tests.

#### Scenario: Dashboard KPI changes
- **WHEN** a dashboard KPI formula changes
- **THEN** the formula is implemented in a service/read model
- **AND** tests verify the formula without rendering the React page

#### Scenario: Graph visualization changes
- **WHEN** graph filters, visual weight, communities, semantic relation toggles, or focus modes change
- **THEN** backend graph data shaping and frontend rendering state are tested separately

### Requirement: Regression tests cover critical workflows
The system SHALL maintain a minimal set of workflow tests that protect the areas where regressions have occurred repeatedly.

The minimum workflow coverage SHALL include:
- authentication initializes domain scope correctly
- changing domain scope changes scoped metrics
- enrichment completion updates derived data status
- graph materialization updates graph readiness and visualization
- semantic keyword signals do not render object serialization artifacts
- entity detail metadata is deduplicated and language-consistent
- executive dashboard reflects enriched data and active domain scope

#### Scenario: Pull request changes dashboard, graph, enrichment, domain, or entity detail behavior
- **WHEN** CI runs
- **THEN** the relevant workflow tests run in addition to unit tests
- **AND** the PR is considered incomplete if the affected workflow has no regression test

### Requirement: README reflects current system reality
The project README SHALL describe the current platform honestly and briefly. It SHALL prioritize what exists today, how to run and test it, where specs live, and what is still being hardened.

The README SHALL NOT serve as a historical sprint inventory, sales deck, or exhaustive feature claim list.

#### Scenario: A capability is partial or aspirational
- **WHEN** the README mentions it
- **THEN** it is labeled as implemented, partial, experimental, or planned
- **AND** deeper detail links to specs or product docs instead of expanding the README indefinitely

### Requirement: Progressive hardening sequence is explicit
Hardening work SHALL be sequenced to reduce regressions before expanding new functionality.

The default sequence SHALL be:
1. Domain scope contract
2. Derived data status contract
3. Entity metadata view
4. Dashboard and graph read-model extraction
5. Workflow regression tests
6. README/docs cleanup
7. Larger architectural refactors

#### Scenario: A new feature competes with hardening work
- **WHEN** a new feature depends on an unstable contract listed above
- **THEN** the contract stabilization is planned first or included as part of the feature implementation

## RELATED Specs

- `openspec/specs/enrichment-progress-tracking/spec.md`
- `openspec/specs/enrichment-failure-details/spec.md`
- `openspec/specs/bibliometric-graph-engine/spec.md`
- `openspec/specs/semantic-keyword-signal-engine/spec.md`
- `openspec/specs/epistemic-analytics-ui/spec.md`
- `openspec/specs/epistemic-classification-engine/spec.md`
- `openspec/specs/concept-tree-materialization/spec.md`
- `openspec/specs/concept-hierarchy-ui/spec.md`

## FUTURE Specs To Create

- `domain-scope-contract`
- `derived-data-status`
- `entity-metadata-view`
- `executive-dashboard-read-model`
- `graph-visualization-read-model`
- `rag-index-freshness`
- `workflow-regression-suite`
- `documentation-truth-model`
