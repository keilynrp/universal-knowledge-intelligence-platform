## MODIFIED Requirements

### Requirement: Clicking failure indicator reveals diagnostics panel
The system SHALL display an inline expandable panel below the entity row showing failure details when the error indicator is clicked. The panel SHALL include `enrichment_failure_reason` (the new categorised field) as a human-readable label alongside the existing failure object fields.

#### Scenario: Panel shows failure code and evidence
- **WHEN** the user clicks the error indicator on a failed row
- **THEN** an inline panel expands below the row showing: failure code (human-readable label), evidence text, the list of providers attempted, and the `enrichment_failure_reason` category badge if present

#### Scenario: Panel shows actionable recommendations
- **WHEN** the failure panel is expanded
- **THEN** it displays the `recommendations` array from the failure object as a bulleted list of corrective actions

#### Scenario: Panel shows record snapshot at time of failure
- **WHEN** the failure panel is expanded and the failure object contains `record_snapshot`
- **THEN** it shows the entity's primary_label, canonical_id, and DOI at the time enrichment was attempted

#### Scenario: Panel can be collapsed
- **WHEN** the user clicks the error indicator again or clicks a close button
- **THEN** the failure panel collapses

#### Scenario: Panel shows failure reason badge when available
- **WHEN** the entity has a non-NULL `enrichment_failure_reason`
- **THEN** the panel displays a coloured badge: `no_match` (grey), `circuit_open` (red), `api_error` (orange), `rate_limited` (amber), `timeout` (yellow), `all_sources_failed` (red)

#### Scenario: Panel shows unknown label for NULL failure reason
- **WHEN** the entity's `enrichment_failure_reason` is NULL (pre-migration row)
- **THEN** the badge shows "Unknown" in grey without causing an error
