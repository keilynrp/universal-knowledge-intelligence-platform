## ADDED Requirements

### Requirement: Accepted authority decisions promote canonical semantics
UKIP SHALL promote accepted authority decisions into canonical semantic fields or relationships with provenance.

#### Scenario: Person authority candidate is accepted
- **WHEN** a person authority candidate is accepted
- **THEN** UKIP stores a canonical author identity with accepted label, aliases, identifiers, confidence, evidence references, and review metadata
- **AND** source and enrichment author values remain preserved

#### Scenario: Institution authority candidate is accepted
- **WHEN** an institution authority candidate is accepted
- **THEN** UKIP stores a canonical institution or affiliation identity with accepted registry identifiers and provenance
- **AND** downstream analytics can prefer the canonical institution over raw affiliation text

#### Scenario: Identifier authority candidate is accepted
- **WHEN** an identifier authority candidate is accepted (e.g., DOI, ORCID, ROR)
- **THEN** UKIP stores the canonical identifier with registry source, validation status, and provenance
- **AND** the identifier becomes available for deduplication and linked-data export

#### Scenario: Place authority candidate is accepted
- **WHEN** a place authority candidate is accepted
- **THEN** UKIP stores a canonical geographic entity link with ISO code, GeoNames ID, or Wikidata QID as applicable
- **AND** the canonical place becomes available for geographic analytics and relationship materialization

### Requirement: Canonical promotion preserves all prior data layers
UKIP SHALL preserve original source values and enrichment observations without overwriting them during canonical promotion.

#### Scenario: Promotion preserves source author values
- **WHEN** a person candidate is promoted to canonical identity
- **THEN** the original source author field remains accessible as source provenance
- **AND** the enrichment author observations remain accessible as enrichment provenance

#### Scenario: Promotion preserves enrichment observations
- **WHEN** an institution candidate is promoted using ROR evidence from enrichment
- **THEN** the enrichment-provided institution metadata remains as enrichment observations
- **AND** the canonical institution link is a separate artifact with its own provenance

### Requirement: Enrichment cannot auto-promote conflicting identity
UKIP SHALL NOT promote enrichment-provided identity values into canonical identity when they conflict with source or existing authority decisions unless a governed review or auto-accept rule permits it.

#### Scenario: Enrichment returns conflicting institution name
- **WHEN** enrichment returns an institution name that conflicts with a confirmed authority record
- **THEN** UKIP records the enrichment value as evidence
- **AND** does not overwrite the accepted canonical institution
- **AND** marks the conflict for review

#### Scenario: Enrichment returns conflicting person identity
- **WHEN** enrichment returns author metadata that conflicts with an accepted person authority record
- **THEN** UKIP stores the enrichment evidence as an observation
- **AND** creates a conflict review item rather than silently overwriting the accepted canonical person

#### Scenario: Auto-accept rule permits promotion for high-confidence matches
- **WHEN** a governed auto-accept policy exists and an enrichment-derived candidate exceeds the confidence threshold
- **THEN** UKIP may promote the candidate automatically
- **AND** records the auto-accept policy, confidence score, and evidence in the promotion audit trail

### Requirement: Rejected candidates remain auditable
Rejected authority candidates SHALL remain auditable and SHALL NOT be recreated for the same evidence unless the evidence changes.

#### Scenario: User rejects an ambiguous author candidate
- **WHEN** a reviewer rejects an author candidate
- **THEN** UKIP stores the rejection decision and reason
- **AND** suppresses the same candidate during future extraction runs until evidence changes

#### Scenario: Rejected candidate is resurfaced after evidence changes
- **WHEN** source re-ingestion or enrichment refresh provides new evidence for a previously rejected candidate
- **THEN** UKIP creates a new candidate with the updated evidence
- **AND** links it to the prior rejection record for review context

#### Scenario: Rejection audit trail is queryable
- **WHEN** a reviewer or administrator queries rejection history
- **THEN** UKIP returns the rejected candidate, rejection reason, reviewer identity, timestamp, and the evidence that was available at rejection time

### Requirement: Canonical promotion payload is well-defined
UKIP SHALL define a structured promotion payload for accepted authority decisions.

#### Scenario: Promotion payload includes required fields
- **WHEN** an authority decision is promoted
- **THEN** the promotion payload includes canonical entity type, accepted label, accepted identifiers, confidence score, evidence references, reviewer or auto-accept policy reference, and timestamp

#### Scenario: Promotion creates or updates canonical relationships
- **WHEN** an accepted authority decision implies a relationship (e.g., author affiliated with institution)
- **THEN** the promotion creates or updates the canonical relationship with provenance
- **AND** downstream modules (graph, RAG, analytics, reports) can consume the relationship

### Requirement: Downstream modules consume promoted canonical values
UKIP SHALL ensure that graph materialization, RAG, analytics, and executive reporting prefer canonical authority-resolved values when available.

#### Scenario: Graph materialization uses canonical authors and institutions
- **WHEN** graph materialization runs on a dataset with authority-resolved authors and institutions
- **THEN** it uses canonical identities for nodes and edges
- **AND** falls back to enrichment or source values only when no canonical identity exists

#### Scenario: RAG evidence labels use canonical authority labels
- **WHEN** RAG retrieves evidence from authority-resolved entities
- **THEN** evidence labels prefer accepted canonical labels over raw source or enrichment labels

#### Scenario: Analytics surface authority coverage
- **WHEN** author productivity, coauthorship, or geographic analytics run
- **THEN** they report authority resolution coverage (e.g., percentage of entities with canonical identity)
- **AND** distinguish authority-resolved results from source-only or enrichment-only results

#### Scenario: Regression tests cover all resolution states
- **WHEN** tests run analytics with source-only, enriched-unresolved, and authority-resolved datasets
- **THEN** each resolution state produces correct and distinguishable output
