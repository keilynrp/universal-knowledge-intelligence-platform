## ADDED Requirements

### Requirement: Attention timeline
The system SHALL aggregate external attention observations over time for a supported scope.

#### Scenario: Monthly timeline
- **WHEN** no timeline granularity is specified
- **THEN** the system SHALL return monthly buckets with `period`, `mentions`, `score_delta`, and `top_source_type`

#### Scenario: Daily timeline for short windows
- **WHEN** the request specifies daily granularity and the date range is within the configured limit
- **THEN** the system SHALL return daily buckets

#### Scenario: Empty timeline range
- **WHEN** no observations exist in the requested range
- **THEN** the system SHALL return an empty timeline array and preserve the score summary for the full scope when requested

### Requirement: Spike metadata
The system SHALL identify period buckets where attention materially exceeds the previous baseline.

#### Scenario: Timeline spike
- **WHEN** a period's weighted attention exceeds the rolling baseline threshold
- **THEN** the bucket SHALL include `spike: true` and a `spike_reason`
