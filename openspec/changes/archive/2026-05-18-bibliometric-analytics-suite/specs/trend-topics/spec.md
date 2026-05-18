## ADDED Requirements

### Requirement: Temporal frequency computation
The system SHALL compute concept frequency per time period (year) for a given domain, counting occurrences of each concept from the `enrichment_concepts` field across all entities in that domain.

#### Scenario: Compute yearly concept frequencies
- **WHEN** the endpoint receives a `domain_id` and optional `min_year`/`max_year` filters
- **THEN** it SHALL return a list of concepts with their frequency per year, sorted by total frequency descending

#### Scenario: Filter by year range
- **WHEN** `min_year=2020` and `max_year=2024` are provided
- **THEN** the system SHALL only include entities whose year field falls within that inclusive range

### Requirement: Trend slope classification
The system SHALL compute a linear regression slope (frequency vs. year) for each concept and classify it as emerging, declining, or stable.

#### Scenario: Classify emerging topic
- **WHEN** a concept's frequency slope exceeds the `emerging_threshold` (default 0.5 papers/year)
- **THEN** the system SHALL classify it as "emerging"

#### Scenario: Classify declining topic
- **WHEN** a concept's frequency slope is below the negative of `declining_threshold` (default -0.5 papers/year)
- **THEN** the system SHALL classify it as "declining"

#### Scenario: Classify stable topic
- **WHEN** a concept's frequency slope is between `-declining_threshold` and `emerging_threshold`
- **THEN** the system SHALL classify it as "stable"

#### Scenario: Skip concepts with insufficient data
- **WHEN** a concept appears in fewer than `min_years` distinct years (default 3)
- **THEN** the system SHALL exclude it from trend analysis and include it in a `skipped_count` in the response metadata

### Requirement: Trend topics endpoint
The system SHALL expose trend analysis via `GET /analyzers/trends/{domain_id}`.

#### Scenario: Successful trend request
- **WHEN** an authenticated user requests `GET /analyzers/trends/{domain_id}?limit=20`
- **THEN** the system SHALL return the top 20 concepts ranked by absolute slope magnitude, each with `concept`, `slope`, `classification`, `total_count`, and `yearly_counts` (dict of year→count)

#### Scenario: Empty domain
- **WHEN** the domain has no entities with `enrichment_concepts`
- **THEN** the system SHALL return an empty `trends` array with `total_analyzed: 0`

#### Scenario: Invalid domain
- **WHEN** the `domain_id` does not exist in the schema registry or entity table
- **THEN** the system SHALL return HTTP 404
