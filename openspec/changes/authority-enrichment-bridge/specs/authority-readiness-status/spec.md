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

### Requirement: Readiness includes candidate family coverage
Authority readiness SHALL include person, institution, identifier, place, venue, and concept coverage when those candidate families are available.

#### Scenario: Dataset has authors and affiliations only
- **WHEN** a dataset has person and institution evidence but no place or venue evidence
- **THEN** UKIP reports person and institution coverage
- **AND** does not imply that unsupported families were resolved
