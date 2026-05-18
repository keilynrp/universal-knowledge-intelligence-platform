## ADDED Requirements

### Requirement: Country extraction from affiliations
The system SHALL extract country names from affiliation strings stored in `attributes_json`, using a static lookup table of country names and common abbreviations (ISO 3166 + variants like "USA", "UK", "PRC", "ROK").

#### Scenario: Extract country from standard affiliation
- **WHEN** an entity has affiliation "MIT, Cambridge, MA, United States"
- **THEN** the system SHALL extract country as "United States" and store the ISO 3166-1 alpha-2 code "US"

#### Scenario: Extract country from abbreviated format
- **WHEN** an entity has affiliation "Tsinghua University, Beijing, PRC"
- **THEN** the system SHALL map "PRC" to country code "CN"

#### Scenario: Unresolvable affiliation
- **WHEN** the affiliation string does not match any known country pattern
- **THEN** the system SHALL set country to NULL and log the unmatched affiliation at DEBUG level

#### Scenario: Persist extracted country
- **WHEN** country extraction succeeds
- **THEN** the system SHALL store the extracted `country_code` (ISO alpha-2) in the entity's `attributes_json` under key `extracted_country`

### Requirement: Geographic aggregation endpoint
The system SHALL expose `GET /analyzers/geographic/{domain_id}` returning per-country aggregated metrics.

#### Scenario: Retrieve geographic distribution
- **WHEN** an authenticated user requests the geographic analysis for a domain
- **THEN** the system SHALL return a list of countries with `country_code`, `country_name`, `entity_count`, `citation_sum`, `author_count`, and `percentage` (of total entities)

#### Scenario: Sort by entity count
- **WHEN** no `sort_by` parameter is provided
- **THEN** the system SHALL sort countries by `entity_count` descending by default

#### Scenario: Sort by citations
- **WHEN** `sort_by=citation_sum` is provided
- **THEN** the system SHALL sort countries by `citation_sum` descending

#### Scenario: Limit results
- **WHEN** `limit=10` is provided
- **THEN** the system SHALL return only the top 10 countries, with an additional `others` entry aggregating remaining countries

#### Scenario: No geographic data
- **WHEN** no entities in the domain have extractable country data
- **THEN** the system SHALL return an empty `countries` array with `coverage: 0.0`

### Requirement: Geographic collaboration analysis
The system SHALL compute international collaboration metrics by analyzing entities with authors from multiple countries.

#### Scenario: Identify international collaboration rate
- **WHEN** an authenticated user requests `GET /analyzers/geographic/{domain_id}?include_collaboration=true`
- **THEN** the response SHALL include `collaboration_rate` (percentage of entities with authors from 2+ countries) and `top_country_pairs` (top 10 country pairs by co-publication count)

#### Scenario: Entity with single country
- **WHEN** all authors on an entity are from the same country
- **THEN** the entity SHALL NOT count as an international collaboration

### Requirement: Geographic heatmap data for dashboard
The system SHALL provide heatmap-compatible data via `GET /dashboard/summary` by including a `geographic_heatmap` field in the dashboard response.

#### Scenario: Dashboard includes geographic data
- **WHEN** an authenticated user requests `GET /dashboard/summary`
- **THEN** the response SHALL include `geographic_heatmap` as a list of `{country_code, country_name, value}` entries where value is the entity count

#### Scenario: Dashboard with no geographic data
- **WHEN** no entities have extracted country data
- **THEN** `geographic_heatmap` SHALL be an empty array
