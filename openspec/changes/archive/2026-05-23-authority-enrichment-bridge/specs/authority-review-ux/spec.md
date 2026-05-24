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

#### Scenario: Candidate came from prior authority record
- **WHEN** a candidate references a previously accepted authority record
- **THEN** the UI labels its origin as prior authority
- **AND** shows the original acceptance decision and confidence

#### Scenario: Candidate was manually created
- **WHEN** a candidate was created by manual user input
- **THEN** the UI labels its origin as manual input
- **AND** records the user identity and creation timestamp

### Requirement: Authority UI shows readiness before review
The Authority module SHALL show aggregate authority readiness before asking users to review individual candidates.

#### Scenario: Dataset has no extracted candidates
- **WHEN** the user opens the Authority module for a dataset with enrichment evidence but no candidates
- **THEN** the UI shows an extraction-ready state
- **AND** provides a clear action to create authority candidates

#### Scenario: Dataset has extracted candidates pending review
- **WHEN** the user opens the Authority module for a dataset with pending candidates
- **THEN** the UI shows the readiness card with per-family counts
- **AND** provides navigation to the review queue

#### Scenario: Dataset is fully resolved
- **WHEN** the user opens the Authority module for a dataset with all candidates resolved
- **THEN** the UI shows a resolved readiness state with summary statistics

### Requirement: Authority UI explains downstream impact
The Authority module SHALL indicate which downstream capabilities benefit from resolving a candidate.

#### Scenario: Institution candidate is pending review
- **WHEN** an institution candidate appears in the review queue
- **THEN** the UI indicates that accepting it can improve geographic analysis, coauthorship networks, RAG grounding, and executive reporting

#### Scenario: Person candidate is pending review
- **WHEN** a person candidate appears in the review queue
- **THEN** the UI indicates that accepting it can improve author productivity analysis, coauthorship networks, and entity deduplication

#### Scenario: Identifier candidate is pending review
- **WHEN** an identifier candidate (e.g., DOI, ORCID) appears in the review queue
- **THEN** the UI indicates that accepting it can improve deduplication, linked-data export, and cross-reference resolution

### Requirement: Authority UI shows evidence, confidence, and review state
The Authority module SHALL display evidence details, confidence scores, review state, and stale/failed diagnostics for each candidate.

#### Scenario: Candidate evidence is displayed
- **WHEN** a user expands a candidate in the review queue
- **THEN** the UI shows all evidence references: source fields, enrichment observations, provider identifiers, and prior authority links

#### Scenario: Confidence score is displayed
- **WHEN** a candidate has a computed confidence score
- **THEN** the UI shows the score with a visual indicator (e.g., bar or badge)
- **AND** indicates whether the score is above or below auto-accept thresholds

#### Scenario: Stale candidate shows diagnostic
- **WHEN** a candidate is marked as stale
- **THEN** the UI shows which evidence changed and when
- **AND** provides an action to re-extract or refresh the candidate

#### Scenario: Failed candidate shows diagnostic
- **WHEN** a candidate extraction or resolution failed
- **THEN** the UI shows the error class and suggests retry or escalation

### Requirement: Authority UI provides extraction CTA for enriched and source-only datasets
The Authority module SHALL provide extraction actions appropriate to the dataset evidence state.

#### Scenario: Enriched dataset shows extraction CTA
- **WHEN** a dataset has enrichment evidence but no authority candidates
- **THEN** the UI shows an "Extract authority candidates" action
- **AND** indicates that enrichment context is available for higher-quality extraction

#### Scenario: Source-only dataset shows extraction CTA
- **WHEN** a dataset has source data but no enrichment
- **THEN** the UI shows an "Extract source-only candidates" action
- **AND** recommends running enrichment first for better results

### Requirement: Authority UI translations cover all provenance labels
The Authority module SHALL provide EN/ES translations for readiness states, candidate families, origin labels, and review provenance.

#### Scenario: English translations exist
- **WHEN** the UI locale is English
- **THEN** all readiness states, candidate family labels, origin labels, and review action copy are defined in the EN translation file

#### Scenario: Spanish translations exist
- **WHEN** the UI locale is Spanish
- **THEN** equivalent Spanish labels are defined for all authority UI copy

### Requirement: Authority UI is testable
UKIP SHALL include focused frontend tests for readiness rendering and candidate origin labels.

#### Scenario: Test verifies readiness card rendering
- **WHEN** a test provides a dataset readiness payload
- **THEN** the readiness card renders the correct state, per-family counts, and CTA

#### Scenario: Test verifies candidate origin label rendering
- **WHEN** a test provides candidates with different origins (source, enrichment, prior authority, manual)
- **THEN** each candidate renders the correct origin label and provenance context
