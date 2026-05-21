## ADDED Requirements

### Requirement: GenAI is governed as a cross-cutting capability
UKIP SHALL treat GenAI as a transversal capability across ingestion, mapping, reconciliation, enrichment, analytics, reporting, UX, and architecture governance.

#### Scenario: GenAI suggests canonical mappings
- **WHEN** GenAI suggests mappings from an ingested source to the canonical model
- **THEN** UKIP records evidence, confidence, review status, and source provenance
- **AND** does not apply low-confidence mappings silently

#### Scenario: GenAI generates executive narrative
- **WHEN** GenAI generates report narrative or strategic interpretation
- **THEN** UKIP grounds the narrative in governed evidence and exposes provenance or review status as required

### Requirement: GenAI cannot replace governed evidence
GenAI-assisted outputs SHALL NOT be treated as authoritative data unless supported by governed evidence, confidence, and review rules.

#### Scenario: AI infers an institution from ambiguous affiliation text
- **WHEN** GenAI infers an institution identity from ambiguous text
- **THEN** UKIP treats the result as a candidate suggestion
- **AND** requires authority resolution or review before promoting it to canonical identity
