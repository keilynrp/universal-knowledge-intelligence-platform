## ADDED Requirements

### Requirement: Authority UI explains candidate origin
The Authority module SHALL show whether each candidate originated from source data, enrichment evidence, prior authority records, or manual input.

#### Scenario: Candidate came from enrichment
- **WHEN** a candidate was extracted from enriched metadata
- **THEN** the UI labels its origin as enrichment evidence
- **AND** shows provider/source context when available

#### Scenario: Candidate came from source-only data
- **WHEN** a candidate was extracted from original source fields
- **THEN** the UI labels its origin as source data
- **AND** communicates that additional enrichment may improve confidence

### Requirement: Authority UI shows readiness before review
The Authority module SHALL show aggregate authority readiness before asking users to review individual candidates.

#### Scenario: Dataset has no extracted candidates
- **WHEN** the user opens the Authority module for a dataset with enrichment evidence but no candidates
- **THEN** the UI shows an extraction-ready state
- **AND** provides a clear action to create authority candidates

### Requirement: Authority UI explains downstream impact
The Authority module SHALL indicate which downstream capabilities benefit from resolving a candidate.

#### Scenario: Institution candidate is pending review
- **WHEN** an institution candidate appears in the review queue
- **THEN** the UI indicates that accepting it can improve geographic analysis, coauthorship networks, RAG grounding, and executive reporting
