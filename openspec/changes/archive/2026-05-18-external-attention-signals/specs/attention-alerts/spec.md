## ADDED Requirements

### Requirement: Emerging attention alerts
The system SHALL raise rule-based alerts for meaningful external attention changes.

Initial alert types SHALL include:

- `new_attention`
- `attention_spike`
- `policy_mention`
- `cross_source_momentum`

#### Scenario: New attention alert
- **WHEN** a scope receives its first external attention observation
- **THEN** the system SHALL create or return a `new_attention` alert

#### Scenario: Attention spike alert
- **WHEN** current-period attention exceeds the rolling baseline threshold and minimum observation count
- **THEN** the system SHALL return an `attention_spike` alert with severity and confidence

#### Scenario: Policy mention alert
- **WHEN** policy observations are present
- **THEN** the system SHALL return a `policy_mention` alert

#### Scenario: Cross-source momentum alert
- **WHEN** at least three source types are active in the current period
- **THEN** the system SHALL return a `cross_source_momentum` alert

### Requirement: Alert ordering
The system SHALL order attention alerts by severity, confidence, and recency.

#### Scenario: Dashboard alert limit
- **WHEN** executive dashboard requests attention alerts
- **THEN** the system SHALL return at most three alerts for the primary dashboard surface
