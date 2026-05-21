## ADDED Requirements

### Requirement: Data-model specs declare governance role
Every UKIP spec that introduces or modifies data-model semantics SHALL declare its governance role relative to the canonical semantic data layer.

#### Scenario: New domain model spec is proposed
- **WHEN** a spec adds a new domain entity family
- **THEN** it declares whether it is a `canonical-specialization`, `source-adapter`, `authority-resolver`, `enrichment-provider`, `presentation`, or `governing` spec
- **AND** it identifies the canonical entities, relationships, identifiers, provenance rules, and confidence rules it affects

#### Scenario: Source-specific adapter spec is proposed
- **WHEN** a spec maps a provider payload into UKIP
- **THEN** it declares the source payload fields it consumes
- **AND** it declares how those fields map into canonical candidates without overwriting canonical identity silently

### Requirement: Subordinate specs preserve canonical boundaries
Subordinate data-model specs SHALL preserve the distinction between original source data, UKIP canonical identity, authority resolution, evidence-based enrichment, linked-data alignment, and presentation.

#### Scenario: Enrichment provider adds a DOI
- **WHEN** an enrichment provider supplies a DOI for a record
- **THEN** UKIP stores it as an enrichment observation unless a governed authority or mapping rule promotes it to canonical identity

#### Scenario: Authority resolver matches an institution
- **WHEN** an institution candidate is matched to a ROR authority record
- **THEN** UKIP records the authority link with resolver source, confidence, and evidence
- **AND** it keeps the original source affiliation value available

### Requirement: Canonical semantics govern executive intelligence
Executive intelligence outputs SHALL prefer governed canonical semantics over raw source or provider payloads when available.

#### Scenario: Report uses institution affiliation data
- **WHEN** a report includes institutional collaboration claims
- **THEN** it uses canonical or authority-resolved institution relationships when available
- **AND** it exposes evidence/provenance for the claim

#### Scenario: Report uses geographic data
- **WHEN** a report includes geographic distribution claims
- **THEN** it uses normalized geographic entities when available
- **AND** falls back to raw geographic text only with explicit provenance or confidence limitations
