## ADDED Requirements

### Requirement: Institution reconciliation resolves affiliation candidates
UKIP SHALL provide a service that resolves extracted institution affiliation candidates to canonical institution authority candidates.

#### Scenario: Candidate has ROR ID
- **WHEN** an affiliation candidate includes a ROR ID
- **THEN** the reconciliation service returns a high-confidence ROR-backed candidate

#### Scenario: Candidate has only name and country
- **WHEN** an affiliation candidate includes institution name and country but no ROR
- **THEN** the service searches supported registries and returns ranked candidates

#### Scenario: Candidate is ambiguous
- **WHEN** multiple candidates have similar confidence
- **THEN** the service marks the candidate for review instead of auto-accepting

### Requirement: Reconciliation explains candidate scores
Institution reconciliation results SHALL include score breakdown evidence.

#### Scenario: Candidate matched by alias and country
- **WHEN** a candidate score uses alias and country signals
- **THEN** the result includes those signals in the score breakdown
