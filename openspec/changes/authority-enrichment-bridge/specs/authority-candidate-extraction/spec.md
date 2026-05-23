## ADDED Requirements

### Requirement: Enriched evidence produces authority candidates
UKIP SHALL extract authority candidates from enriched dataset evidence without treating enrichment payloads as canonical identity.

#### Scenario: Enriched authors include ORCID hints
- **WHEN** a record has enriched authors and ORCID hints
- **THEN** UKIP creates person authority candidates with ORCID evidence, source record references, and confidence metadata
- **AND** the original source author field remains available separately

#### Scenario: Enriched affiliations include institutional context
- **WHEN** a record has enriched affiliation evidence
- **THEN** UKIP creates institution authority candidates with affiliation labels, available identifiers, country/location hints, and provider provenance
- **AND** ambiguous candidates are marked for review instead of being auto-promoted

### Requirement: Source-only evidence produces lower-context authority candidates
UKIP SHALL support authority candidate extraction before enrichment by using mapped source fields with lower-confidence context.

#### Scenario: Dataset has raw author field but no enrichment
- **WHEN** authority extraction runs on a source-only dataset
- **THEN** UKIP creates source-derived person candidates
- **AND** marks the candidate origin as `source`
- **AND** indicates that enrichment context is unavailable

### Requirement: Candidate extraction deduplicates evidence
UKIP SHALL deduplicate extracted candidates across source and enrichment layers while preserving all evidence references.

#### Scenario: Same ORCID appears in source and enrichment
- **WHEN** the same ORCID appears in original source metadata and enrichment metadata
- **THEN** UKIP creates one person authority candidate
- **AND** attaches both source and enrichment evidence references to the candidate
