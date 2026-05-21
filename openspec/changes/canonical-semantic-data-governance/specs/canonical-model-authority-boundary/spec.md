## ADDED Requirements

### Requirement: Canonical identity is distinct from authority links and enrichment observations
UKIP SHALL model canonical identity, authority links, and enrichment observations as distinct concepts.

#### Scenario: Source provides a title and DOI
- **WHEN** a source record provides a title and DOI
- **THEN** UKIP can use those values as canonical candidates with source provenance
- **AND** later Crossref/DataCite/OpenAlex enrichment remains distinguishable from the original source values

#### Scenario: Authority record resolves an organization
- **WHEN** an organization candidate resolves to a ROR record
- **THEN** the authority link references the ROR record and match evidence
- **AND** the canonical organization retains provenance for its original source label

### Requirement: Enrichment cannot overwrite canonical identity without governed promotion
Evidence-based enrichment SHALL NOT overwrite canonical identity unless a governed promotion rule, confidence threshold, and provenance trail exist.

#### Scenario: Enrichment provides a different organization name
- **WHEN** an enrichment provider returns a name that differs from the canonical organization label
- **THEN** UKIP stores the provider value as an enrichment observation
- **AND** does not replace the canonical label unless an authority or review rule promotes it

#### Scenario: Enrichment provides missing metadata
- **WHEN** a canonical entity lacks optional metadata and enrichment supplies it
- **THEN** UKIP may attach the value as an enrichment observation with provider provenance
- **AND** may derive a canonical display value only when governance rules allow it
