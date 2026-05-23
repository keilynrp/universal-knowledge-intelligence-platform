## ADDED Requirements

### Requirement: Mapping suggestions are explicit reviewable artifacts
UKIP SHALL represent mapping suggestions as explicit artifacts that can be accepted, rejected, reviewed, or superseded.

#### Scenario: High-confidence mapping is suggested
- **WHEN** a source field strongly matches a canonical field or entity role
- **THEN** UKIP can mark the mapping suggestion as auto-acceptable according to governed thresholds
- **AND** the suggestion includes evidence samples and confidence

#### Scenario: Low-confidence mapping is suggested
- **WHEN** a source field has ambiguous values or multiple plausible canonical targets
- **THEN** UKIP marks the suggestion as review-required
- **AND** it does not apply the mapping silently

### Requirement: Mapping suggestions preserve source evidence
Mapping suggestions SHALL preserve source field names, original values, transformation rules, and confidence evidence.

#### Scenario: Mapping transforms a local identifier
- **WHEN** a source field is mapped to a canonical identifier
- **THEN** UKIP preserves the original source identifier value
- **AND** records any normalization or transformation rule used

#### Scenario: Mapping conflicts with existing canonical identity
- **WHEN** a suggested mapping conflicts with an existing canonical field
- **THEN** UKIP records the conflict
- **AND** requires governed resolution before overwriting or superseding the canonical value

### Requirement: Mapping suggestion lifecycle transitions are tested across accept, reject, and review-required states
UKIP SHALL correctly transition mapping suggestions through accepted, rejected, and review-required states with full evidence and provenance preservation.

#### Scenario: Accepted mapping is applied and recorded
- **WHEN** a reviewer accepts a high-confidence mapping suggestion that maps source field `author_name` to canonical entity role `Person.display_name`
- **THEN** UKIP applies the mapping to incoming and existing records
- **AND** the accepted mapping artifact records the reviewer identity, acceptance timestamp, confidence at acceptance, and the evidence samples that supported the suggestion

#### Scenario: Rejected mapping is preserved with rationale
- **WHEN** a reviewer rejects a mapping suggestion that proposed mapping source field `notes` to canonical entity role `Work.abstract`
- **THEN** UKIP marks the suggestion as rejected without applying it
- **AND** the rejected artifact preserves the original suggestion, rejection rationale, reviewer identity, and timestamp
- **AND** the rejected mapping is available for audit and does not reappear as a new suggestion for the same source-field-to-canonical-target pair unless the source profile changes materially

#### Scenario: Review-required mapping awaits human decision
- **WHEN** UKIP generates a mapping suggestion with confidence below the auto-accept threshold for source field `dept` with two plausible canonical targets (`Organization.department_name` and `Organization.display_name`)
- **THEN** UKIP marks the suggestion as review-required and does not apply either mapping
- **AND** both candidate targets are presented with their respective confidence scores and evidence samples
- **AND** the suggestion remains pending until a reviewer explicitly accepts one target or rejects the suggestion

#### Scenario: Accepted mapping is later superseded
- **WHEN** a previously accepted mapping is superseded by a new mapping suggestion with higher confidence or updated evidence
- **THEN** UKIP marks the original mapping as superseded with a reference to its replacement
- **AND** records already mapped under the original suggestion retain provenance linking them to the superseded mapping version

#### Scenario: Bulk mapping suggestions for a new source are triaged
- **WHEN** UKIP profiles a new source and generates multiple mapping suggestions simultaneously
- **THEN** each suggestion is an independent reviewable artifact with its own confidence, evidence, and lifecycle state
- **AND** accepting or rejecting one suggestion does not silently alter the state of other suggestions for the same source
