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
