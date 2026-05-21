# enrichment-failure-details Specification

## Purpose
TBD - created by archiving change bulk-enrichment-feedback. Update Purpose after archive.
## Requirements
### Requirement: Failed rows display an actionable failure indicator
The entity table SHALL display a clickable error indicator on rows with `enrichment_status = "failed"` that have failure diagnostics available.

#### Scenario: Failed row shows error icon
- **WHEN** an entity has `enrichment_status = "failed"` and `attributes_json` contains `enrichment_failure`
- **THEN** a red error icon appears next to the enrichment badge

#### Scenario: Failed row without diagnostics shows generic icon
- **WHEN** an entity has `enrichment_status = "failed"` but `attributes_json` does not contain `enrichment_failure`
- **THEN** a red error icon appears with a generic "Enrichment failed" tooltip

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

### Requirement: Failure details accessible from entity detail modal
The entity detail modal SHALL include a failure diagnostics section when the entity has failed enrichment.

#### Scenario: Detail modal shows failure section
- **WHEN** the user opens the detail modal for an entity with `enrichment_status = "failed"`
- **THEN** the modal includes a "Enrichment Failure" section with code, evidence, recommendations, and a "Retry Enrichment" button

#### Scenario: Retry button re-queues the single entity
- **WHEN** the user clicks "Retry Enrichment" in the detail modal
- **THEN** the system calls `POST /enrich/row/{entity_id}` and updates the UI to show the entity as "pending"

### Requirement: Completion summary toast highlights failures
When bulk enrichment completes with failures, the completion toast SHALL provide a path to inspect failed records.

#### Scenario: Completion toast with failures shows filter action
- **WHEN** the batch completes with `failed > 0`
- **THEN** the completion toast includes a "View failed" link/button that applies the `enrichment_status=failed` facet filter

#### Scenario: Completion toast with zero failures shows success only
- **WHEN** the batch completes with `failed === 0`
- **THEN** the completion toast shows only the success count without a failure action

