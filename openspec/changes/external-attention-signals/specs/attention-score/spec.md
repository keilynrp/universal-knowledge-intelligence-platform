## ADDED Requirements

### Requirement: External attention score
The system SHALL compute a deterministic external attention score for a supported UKIP scope using source-weighted mention counts and recency.

Supported scopes for the MVP SHALL include:

- `entity_id`
- `concept`
- `cluster_id`
- `authority_record_id`

#### Scenario: Compute score from observations
- **WHEN** a scope has external attention observations
- **THEN** the system SHALL return `attention_score`, `category`, `total_mentions`, `active_sources`, and `last_seen_at`
- **AND** the score SHALL be reproducible for the same observations and scoring configuration

#### Scenario: Empty attention data
- **WHEN** a scope has no external attention observations
- **THEN** the system SHALL return `attention_score: 0`, `category: "none"`, `total_mentions: 0`, and empty breakdown/timeline arrays

#### Scenario: Score cap
- **WHEN** weighted mentions exceed the maximum score range
- **THEN** the system SHALL cap `attention_score` at 100

### Requirement: Attention category mapping
The system SHALL map numeric attention scores into simple categories for UI display.

Initial categories SHALL be:

- `none`: 0
- `low`: 1-24
- `moderate`: 25-49
- `high`: 50-74
- `very_high`: 75-100

#### Scenario: Category mapping
- **WHEN** `attention_score` is 67
- **THEN** the system SHALL return `category: "high"`

### Requirement: Attention endpoint
The system SHALL expose authenticated access to attention summaries.

#### Scenario: Entity attention request
- **WHEN** an authenticated user requests attention for an entity in their tenant scope
- **THEN** the system SHALL return the external attention summary for that entity

#### Scenario: Tenant isolation
- **WHEN** an authenticated user requests attention for an entity outside their tenant scope
- **THEN** the system SHALL deny access using the existing tenant-scoping behavior
