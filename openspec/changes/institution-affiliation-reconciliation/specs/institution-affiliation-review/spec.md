## ADDED Requirements

### Requirement: Ambiguous institution matches enter a review queue
Institution matches below the auto-accept threshold but above the unresolved threshold SHALL be visible in a review queue.

#### Scenario: Candidate requires review
- **WHEN** reconciliation returns a candidate with review-level confidence
- **THEN** the candidate appears in the institution affiliation review queue

#### Scenario: Reviewer accepts candidate
- **WHEN** an authorized reviewer accepts a candidate
- **THEN** UKIP persists the authority record and records the review decision

#### Scenario: Reviewer rejects candidate
- **WHEN** an authorized reviewer rejects a candidate
- **THEN** UKIP records the rejection and avoids auto-suggesting the same rejected match for the same source candidate

### Requirement: Review UI shows provenance and score evidence
The institution affiliation review UI SHALL show registry provenance and score evidence.

#### Scenario: Candidate shown in review UI
- **WHEN** a reviewer views an institution candidate
- **THEN** the UI shows candidate name, registry source, ROR/OpenAlex identifiers, country, confidence, and score breakdown
