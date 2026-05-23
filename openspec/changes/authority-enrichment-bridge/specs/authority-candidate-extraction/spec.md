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

#### Scenario: Enriched DOI provides identifier and venue context
- **WHEN** a record has an enriched DOI with resolved metadata
- **THEN** UKIP creates identifier authority candidates for the DOI
- **AND** extracts venue, publisher, and journal authority candidates when the DOI metadata includes them

#### Scenario: Enriched concepts produce concept candidates
- **WHEN** a record has enriched concepts or topic annotations from a provider
- **THEN** UKIP creates concept authority candidates with provider source, vocabulary alignment, and confidence
- **AND** distinguishes controlled vocabulary concepts from free-text topic strings

### Requirement: Source-only evidence produces lower-context authority candidates
UKIP SHALL support authority candidate extraction before enrichment by using mapped source fields with lower-confidence context.

#### Scenario: Dataset has raw author field but no enrichment
- **WHEN** authority extraction runs on a source-only dataset
- **THEN** UKIP creates source-derived person candidates
- **AND** marks the candidate origin as `source`
- **AND** indicates that enrichment context is unavailable

#### Scenario: Dataset has raw affiliation field but no enrichment
- **WHEN** authority extraction runs on a source-only dataset with affiliation text
- **THEN** UKIP creates source-derived institution candidates with lower confidence
- **AND** marks them as suitable for enrichment-assisted refinement

#### Scenario: Dataset has local identifiers but no enrichment
- **WHEN** authority extraction runs on a source-only dataset with SKU, ISBN, ISSN, or local IDs
- **THEN** UKIP creates identifier authority candidates with source provenance
- **AND** marks them as source-only without external registry validation

### Requirement: Candidate extraction deduplicates evidence
UKIP SHALL deduplicate extracted candidates across source and enrichment layers while preserving all evidence references.

#### Scenario: Same ORCID appears in source and enrichment
- **WHEN** the same ORCID appears in original source metadata and enrichment metadata
- **THEN** UKIP creates one person authority candidate
- **AND** attaches both source and enrichment evidence references to the candidate

#### Scenario: Same institution appears with different labels across sources
- **WHEN** the same institution appears as "MIT" in source and "Massachusetts Institute of Technology" in enrichment
- **THEN** UKIP creates one institution authority candidate
- **AND** preserves both labels as evidence with their respective provenance

#### Scenario: Conflicting identifiers from different sources
- **WHEN** source and enrichment provide different identifiers for what appears to be the same entity
- **THEN** UKIP preserves both identifiers as evidence on the candidate
- **AND** marks the candidate as review-required due to identifier conflict

### Requirement: Candidate extraction covers defined candidate families
UKIP SHALL support extraction for person, institution, identifier, place, venue, and concept candidate families.

#### Scenario: Person candidates are extracted from enriched authors
- **WHEN** enrichment provides author metadata with names, ORCID hints, and affiliation context
- **THEN** UKIP extracts person authority candidates with DOI/year context for disambiguation

#### Scenario: Institution candidates are extracted from structured affiliations
- **WHEN** enrichment or institution reconciliation provides structured affiliation data
- **THEN** UKIP extracts institution authority candidates with ROR-ready evidence, OpenAlex institution hints, and country context

#### Scenario: Place candidates are extracted from geographic evidence
- **WHEN** geographic entity reconciliation or institution resolution produces place evidence
- **THEN** UKIP extracts place authority candidates with ISO codes, GeoNames IDs, or coordinate evidence

#### Scenario: Venue candidates are extracted from publication metadata
- **WHEN** enrichment provides journal, conference, or repository metadata
- **THEN** UKIP extracts venue authority candidates with ISSN, publisher, and provider source

### Requirement: Candidate extraction tests cover representative evidence shapes
UKIP SHALL include tests for enriched, source-only, duplicate, sparse, and conflicting evidence scenarios.

#### Scenario: Test verifies extraction from fully enriched record
- **WHEN** a test provides a record with enriched authors, ORCID hints, affiliations, DOI, and concepts
- **THEN** extraction produces person, institution, identifier, and concept candidates with correct provenance

#### Scenario: Test verifies extraction from source-only record
- **WHEN** a test provides a record with only source author and affiliation fields
- **THEN** extraction produces source-derived candidates with lower confidence and source origin

#### Scenario: Test verifies deduplication across layers
- **WHEN** a test provides overlapping evidence from source and enrichment
- **THEN** extraction produces deduplicated candidates with merged evidence references

#### Scenario: Test verifies sparse evidence handling
- **WHEN** a test provides a record with minimal metadata (e.g., title only)
- **THEN** extraction produces no candidates or only low-confidence candidates
- **AND** does not fabricate authority evidence
