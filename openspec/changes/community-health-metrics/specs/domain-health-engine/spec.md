## ADDED Requirements

### Requirement: Discourse community schema configuration
The system SHALL extend `DomainSchema` with an optional `discourse_community` section in domain YAML files. The configuration SHALL define authority sources, communication channel tiers, and health metric declarations. Domains without this section SHALL continue to function without community metrics.

#### Scenario: Science domain has discourse_community config
- **WHEN** the schema registry loads `science.yaml` with a `discourse_community` section
- **THEN** `domain.discourse_community` SHALL be a valid `DiscourseConfig` object with health metric definitions

#### Scenario: Domain without discourse_community still loads
- **WHEN** a domain YAML lacks the `discourse_community` key
- **THEN** `domain.discourse_community` SHALL be `None` and all other domain features SHALL work unchanged

### Requirement: Gini coefficient of authorship concentration
The system SHALL compute a Gini coefficient measuring how concentrated publication authorship is within a domain. The coefficient SHALL range from 0.0 (perfectly distributed) to 1.0 (single author dominates). The computation SHALL use author publication counts extracted from `attributes_json.authors`.

#### Scenario: Balanced authorship yields low Gini
- **WHEN** a domain has 100 entities distributed evenly across 50 authors (2 each)
- **THEN** the Gini coefficient SHALL be below 0.15

#### Scenario: Concentrated authorship yields high Gini
- **WHEN** a domain has 100 entities where 1 author has 80 and 20 others have 1 each
- **THEN** the Gini coefficient SHALL be above 0.7

#### Scenario: Single author yields Gini of 0
- **WHEN** a domain has entities from only 1 author
- **THEN** the Gini coefficient SHALL be 0.0

### Requirement: International collaboration rate
The system SHALL compute the fraction of entities with authors from 2 or more distinct countries. Entities without country data SHALL be excluded from the denominator.

#### Scenario: Mixed collaboration corpus
- **WHEN** a domain has 80 entities with country data, of which 20 have multi-country authorship
- **THEN** the international collaboration rate SHALL be 0.25

#### Scenario: No country data available
- **WHEN** no entities in the domain have country information
- **THEN** the collaboration rate SHALL be `null` and the metric SHALL indicate insufficient data

### Requirement: Open Access publication rate
The system SHALL compute the fraction of entities marked as Open Access (`attributes_json.is_open_access == true`). Only entities with a defined OA status SHALL be counted.

#### Scenario: Partial OA corpus
- **WHEN** a domain has 60 entities with OA data, 30 marked as OA
- **THEN** the OA rate SHALL be 0.5

#### Scenario: No OA data available
- **WHEN** no entities have `is_open_access` in their attributes
- **THEN** the OA rate SHALL be `null`

### Requirement: Epistemic diversity via Shannon entropy
The system SHALL compute normalized Shannon entropy over the paradigm distribution from entities with `epistemic_profile.dominant`. The entropy SHALL be normalized to [0, 1] by dividing by `log2(k)` where `k` is the number of paradigms.

#### Scenario: Perfectly diverse corpus
- **WHEN** a domain has 3 paradigms each with exactly 1/3 of classified entities
- **THEN** the normalized Shannon entropy SHALL be approximately 1.0

#### Scenario: Single paradigm dominates
- **WHEN** 95% of classified entities belong to one paradigm
- **THEN** the normalized Shannon entropy SHALL be below 0.3

#### Scenario: No epistemic profiles exist
- **WHEN** no entities in the domain have `epistemic_profile`
- **THEN** the diversity metric SHALL be `null` and indicate that epistemic classification is required

### Requirement: Newcomer rate per year
The system SHALL compute the fraction of authors in a given year whose first publication in the domain is that year. An author's "first year" is determined by their earliest publication year in the domain.

#### Scenario: Year with many first-time authors
- **WHEN** year 2024 has 50 unique authors, 30 of whom have no prior publications in the domain
- **THEN** the newcomer rate for 2024 SHALL be 0.6

#### Scenario: Established community with few newcomers
- **WHEN** year 2024 has 50 unique authors, 5 of whom are first-time
- **THEN** the newcomer rate for 2024 SHALL be 0.1

### Requirement: Temporal breakdown of all metrics
The system SHALL compute each metric per year for entities with a valid `year` field. The response SHALL include a `by_year` array with metric values for each year.

#### Scenario: Metrics over multiple years
- **WHEN** a domain has entities spanning 2020-2024
- **THEN** the response SHALL include yearly values for all 5 metrics for each year in the range

#### Scenario: Year with too few entities shows warning
- **WHEN** a year has fewer than 5 entities
- **THEN** the metric value for that year SHALL still be computed but marked with `low_sample: true`

### Requirement: Domain health API endpoint
The system SHALL expose `GET /analytics/domain-health/{domain_id}` returning all 5 metrics with current aggregate values, temporal breakdown, and interpretation labels. The endpoint SHALL require authentication and return HTTP 400 for domains without `discourse_community` config.

#### Scenario: Successful health metrics retrieval
- **WHEN** an authenticated user requests `/analytics/domain-health/science`
- **THEN** the response SHALL include `gini_authorship`, `international_collaboration_rate`, `open_access_rate`, `epistemic_diversity`, and `newcomer_rate` with `value`, `label`, and `by_year` fields

#### Scenario: Unconfigured domain returns 400
- **WHEN** a user requests `/analytics/domain-health/healthcare` (no discourse_community config)
- **THEN** the system SHALL return HTTP 400 with detail explaining the domain lacks community configuration

#### Scenario: Cross-domain comparison endpoint
- **WHEN** a user requests `/analytics/domain-health/compare?domains=science,healthcare`
- **THEN** the response SHALL include metrics for each requested domain that has discourse_community config, and skip domains without it

### Requirement: Small sample warning
The system SHALL flag metrics computed from fewer than 20 entities with a `low_sample` warning. Metrics from fewer than 3 entities SHALL NOT be computed (return `null`).

#### Scenario: Very small corpus
- **WHEN** a domain has only 2 entities
- **THEN** all metrics SHALL be `null` with a message indicating insufficient data

#### Scenario: Small but viable corpus
- **WHEN** a domain has 15 entities
- **THEN** metrics SHALL be computed but include `low_sample: true` warning
