# enrichment-schedule-ui Specification

## Purpose
TBD - created by archiving change enrichment-scheduler. Update Purpose after archive.
## Requirements
### Requirement: Derived-status dashboard shows scheduler health card
The derived-status dashboard page (`/analytics/dashboard`) SHALL display a scheduler health card below the existing derived-status resource cards. The card SHALL show: scheduler enabled/disabled badge, interval, last run timestamp, next estimated run, and total entities queued in last cycle.

#### Scenario: Scheduler health card renders with live data
- **WHEN** the user views the derived-status dashboard
- **THEN** a "Enrichment Scheduler" card is visible showing `GET /enrichment/schedule` data

#### Scenario: Card shows "Scheduler disabled" state
- **WHEN** no policies are enabled or the scheduler is globally paused
- **THEN** the card displays a warning badge "Scheduler paused" with no next-run estimate

### Requirement: Per-domain staleness indicator on the scheduler card
The scheduler card SHALL include a per-domain staleness table showing each monitored domain's `current_enrichment_pct`, `is_stale` flag (red/green badge), and `last_run` timestamp.

#### Scenario: Stale domain shows red badge
- **WHEN** a domain's `is_stale = true`
- **THEN** the domain row shows a red "Stale" badge alongside the enrichment percentage

#### Scenario: Healthy domain shows green badge
- **WHEN** a domain's `is_stale = false`
- **THEN** the domain row shows a green "Healthy" badge

### Requirement: Manual trigger button on per-domain staleness row
Each domain row in the scheduler card SHALL include a "Run Now" button (visible to admin+ users) that calls `POST /enrichment/schedule/{domain_id}/trigger` and displays an inline success toast with the queued count.

#### Scenario: Admin clicks Run Now on a stale domain
- **WHEN** an admin user clicks "Run Now" for a stale domain
- **THEN** the button shows a loading spinner, the trigger API is called, and on success a toast shows "Queued N entities for enrichment"

#### Scenario: Run Now is hidden for non-admin users
- **WHEN** a viewer or editor views the scheduler card
- **THEN** the "Run Now" button is not rendered

### Requirement: Policy edit modal accessible from scheduler card
The scheduler card SHALL include an "Edit Policy" button per domain row (admin+ only) that opens a modal with fields for `min_enrichment_pct`, `max_budget_per_run`, `staleness_threshold_days`, and `enabled` toggle. Saving calls `PUT /enrichment/schedule/{domain_id}/policy`.

#### Scenario: Admin opens and saves policy edit
- **WHEN** an admin clicks "Edit Policy" and submits the form
- **THEN** the policy is updated via the API, the modal closes, and the card refreshes with the new values

#### Scenario: Validation prevents invalid input
- **WHEN** the admin enters `min_enrichment_pct = 150`
- **THEN** the form shows an inline error and does not submit

