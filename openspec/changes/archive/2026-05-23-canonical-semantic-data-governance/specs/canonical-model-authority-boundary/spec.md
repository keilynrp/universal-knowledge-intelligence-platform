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

### Requirement: All four data layers remain distinguishable after complete processing
UKIP SHALL preserve the distinction between original source data, canonical identity, authority link, and enrichment observation at every stage of the processing pipeline, including after all operations have completed.

#### Scenario: Original source values survive canonical promotion
- **WHEN** a source record provides `affiliation: "MIT"` and a mapping promotes it to canonical `Organization.display_name: "Massachusetts Institute of Technology"`
- **THEN** the original source value `"MIT"` remains accessible as source provenance on the canonical entity
- **AND** querying the entity's source layer returns the original value, not the canonical label

#### Scenario: Canonical identity survives authority resolution
- **WHEN** a canonical organization `"Massachusetts Institute of Technology"` is resolved to ROR authority `https://ror.org/042nb2s44`
- **THEN** the canonical identity retains its own label, creation provenance, and mapping history
- **AND** the authority link is a separate artifact referencing the ROR record, match confidence, and resolver source
- **AND** deleting or rejecting the authority link does not alter the canonical identity

#### Scenario: Authority link survives enrichment additions
- **WHEN** an enrichment provider adds metadata such as `country: "United States"` and `type: "Education"` to an authority-resolved organization
- **THEN** each enrichment value is stored as an enrichment observation with provider provenance
- **AND** the authority link (ROR ID, confidence, resolver source) is unmodified by the enrichment
- **AND** the enrichment observations do not appear as authority evidence

#### Scenario: All four layers are queryable independently on a single entity
- **WHEN** an entity has progressed through source ingestion, canonical mapping, authority resolution, and enrichment
- **THEN** a governance query can retrieve the original source values, the canonical identity fields, the authority links, and the enrichment observations as four separate collections
- **AND** each collection carries its own provenance chain (source, mapping rule, resolver, provider respectively)

#### Scenario: Rollback of enrichment does not affect canonical or authority layers
- **WHEN** an administrator rolls back or deletes enrichment observations on an entity
- **THEN** the canonical identity and authority links remain intact and unchanged
- **AND** the entity reverts to its pre-enrichment state without losing source or canonical provenance

#### Scenario: Re-ingestion of same source preserves layer boundaries
- **WHEN** the same source dataset is re-ingested with updated values
- **THEN** UKIP updates or versions the source layer with the new values
- **AND** existing canonical identity, authority links, and enrichment observations are not silently overwritten
- **AND** conflicts between re-ingested source values and existing canonical identity trigger governed resolution
