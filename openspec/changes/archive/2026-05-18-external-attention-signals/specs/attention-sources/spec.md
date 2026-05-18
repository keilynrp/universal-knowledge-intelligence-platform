## ADDED Requirements

### Requirement: Source taxonomy
The system SHALL classify external attention observations into a controlled source taxonomy.

Initial source types SHALL include:

- `policy`
- `news`
- `wikipedia`
- `repository`
- `blog`
- `scholarly_web`
- `social_web`
- `other`

#### Scenario: Known source type
- **WHEN** an observation is imported with `source_type: "policy"`
- **THEN** the system SHALL store and score it as a policy observation

#### Scenario: Unknown source type
- **WHEN** an observation is imported with an unsupported source type
- **THEN** the system SHALL map it to `other` or reject it with a validation error, according to the import mode

### Requirement: Source breakdown
The system SHALL return source counts and weighted contribution for each active source type.

#### Scenario: Multi-source breakdown
- **WHEN** a scope has observations from news and policy sources
- **THEN** the response SHALL include both source types with `mentions`, `weighted_contribution`, and `share`

#### Scenario: Breakdown share consistency
- **WHEN** source breakdown contains active sources
- **THEN** the sum of `share` values SHALL be approximately 1.0, allowing only rounding variance
