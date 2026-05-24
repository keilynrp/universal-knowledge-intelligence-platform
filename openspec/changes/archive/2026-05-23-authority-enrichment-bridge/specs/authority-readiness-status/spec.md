## ADDED Requirements

### Requirement: Authority readiness is exposed for datasets and domains
UKIP SHALL expose an authority readiness status that summarizes candidate extraction, review, resolution, rejection, failure, and staleness.

#### Scenario: Enrichment completed but authority extraction has not run
- **WHEN** a dataset has completed enrichment evidence but no extracted authority candidates
- **THEN** UKIP reports an authority readiness state of `enrichment_candidates_ready`
- **AND** exposes an action to extract candidates

#### Scenario: Candidates require review
- **WHEN** extracted candidates are ambiguous or below auto-accept thresholds
- **THEN** UKIP reports `review_required`
- **AND** returns counts by candidate family and review state

#### Scenario: Authority evidence changes after extraction
- **WHEN** source or enrichment evidence changes after candidate extraction
- **THEN** UKIP marks affected authority readiness as `stale`
- **AND** identifies the candidate families requiring refresh

#### Scenario: No authority extraction has run
- **WHEN** a dataset has no enrichment evidence and no authority candidates
- **THEN** UKIP reports `not_started`
- **AND** indicates whether enrichment should run before authority extraction

#### Scenario: Source-only candidates exist
- **WHEN** authority extraction has run on source data without enrichment
- **THEN** UKIP reports `source_candidates_ready`
- **AND** indicates that enrichment would improve candidate quality

#### Scenario: All required candidates are resolved
- **WHEN** all extracted candidates have been accepted, rejected, or dismissed
- **THEN** UKIP reports `resolved`
- **AND** returns summary counts of accepted, rejected, and dismissed decisions

#### Scenario: Extraction or resolution failed
- **WHEN** authority extraction or resolution encounters an error
- **THEN** UKIP reports `failed`
- **AND** includes diagnostic details: affected candidate families, error class, and retry guidance

#### Scenario: Some candidates are resolved while others are pending
- **WHEN** some candidates have been reviewed but others remain pending
- **THEN** UKIP reports `partially_resolved`
- **AND** returns separate counts for resolved and pending candidates by family

### Requirement: Readiness includes candidate family coverage
Authority readiness SHALL include person, institution, identifier, place, venue, and concept coverage when those candidate families are available.

#### Scenario: Dataset has authors and affiliations only
- **WHEN** a dataset has person and institution evidence but no place or venue evidence
- **THEN** UKIP reports person and institution coverage
- **AND** does not imply that unsupported families were resolved

#### Scenario: Dataset has all candidate families
- **WHEN** a dataset has evidence for person, institution, identifier, place, venue, and concept families
- **THEN** UKIP returns per-family counts: extracted, resolved, review-required, rejected, and stale

#### Scenario: Family breakdown distinguishes resolution states
- **WHEN** the readiness endpoint returns family coverage
- **THEN** each family reports extracted_count, resolved_count, review_required_count, rejected_count, failed_count, and stale_count

### Requirement: Readiness aggregation endpoint supports domain and dataset scope
UKIP SHALL provide a readiness aggregation endpoint that can report authority readiness at both domain and dataset granularity.

#### Scenario: Domain-level readiness aggregation
- **WHEN** a user requests authority readiness for an entire domain
- **THEN** UKIP aggregates readiness across all datasets in the domain
- **AND** returns the worst-case readiness state and per-family totals

#### Scenario: Dataset-level readiness detail
- **WHEN** a user requests authority readiness for a specific dataset
- **THEN** UKIP returns readiness state, per-family coverage, and candidate detail links

### Requirement: Stale detection identifies changed evidence
UKIP SHALL detect when source or enrichment evidence changes after the last authority extraction and mark affected candidates as stale.

#### Scenario: Re-ingestion changes source fields
- **WHEN** a source dataset is re-ingested with updated values after authority extraction
- **THEN** UKIP marks candidates derived from changed source fields as stale

#### Scenario: Enrichment refresh changes enrichment observations
- **WHEN** enrichment is refreshed and produces different observations
- **THEN** UKIP marks candidates derived from changed enrichment fields as stale

#### Scenario: Stale candidates surface in readiness endpoint
- **WHEN** stale candidates exist
- **THEN** the readiness endpoint reports them in the stale_count for affected families
- **AND** the overall readiness state transitions to `stale`

### Requirement: Readiness state transitions are tested
UKIP SHALL include backend tests for authority readiness state transitions.

#### Scenario: Test verifies not_started to enrichment_candidates_ready
- **WHEN** a test completes enrichment on a dataset with no prior authority extraction
- **THEN** readiness transitions from `not_started` to `enrichment_candidates_ready`

#### Scenario: Test verifies review_required to partially_resolved
- **WHEN** a test accepts some candidates but leaves others pending
- **THEN** readiness transitions from `review_required` to `partially_resolved`

#### Scenario: Test verifies stale detection after re-ingestion
- **WHEN** a test re-ingests source data after authority extraction
- **THEN** readiness transitions to `stale` for affected candidate families
