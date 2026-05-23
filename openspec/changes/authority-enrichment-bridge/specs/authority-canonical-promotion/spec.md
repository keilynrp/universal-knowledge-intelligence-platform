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

### Requirement: Enrichment cannot auto-promote conflicting identity
UKIP SHALL NOT promote enrichment-provided identity values into canonical identity when they conflict with source or existing authority decisions unless a governed review or auto-accept rule permits it.

#### Scenario: Enrichment returns conflicting institution name
- **WHEN** enrichment returns an institution name that conflicts with a confirmed authority record
- **THEN** UKIP records the enrichment value as evidence
- **AND** does not overwrite the accepted canonical institution
- **AND** marks the conflict for review

### Requirement: Rejected candidates remain auditable
Rejected authority candidates SHALL remain auditable and SHALL NOT be recreated for the same evidence unless the evidence changes.

#### Scenario: User rejects an ambiguous author candidate
- **WHEN** a reviewer rejects an author candidate
- **THEN** UKIP stores the rejection decision and reason
- **AND** suppresses the same candidate during future extraction runs until evidence changes
