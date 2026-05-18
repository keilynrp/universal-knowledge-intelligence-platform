## ADDED Requirements

### Requirement: Batch progress query endpoint
The system SHALL expose `POST /enrich/progress` that accepts `{ ids: number[] }` and returns the enrichment status breakdown for those specific entity IDs.

#### Scenario: Query progress of an active batch
- **WHEN** the client sends `POST /enrich/progress` with `{ ids: [1, 2, 3, 4, 5] }`
- **THEN** the system returns `{ total: 5, pending: 2, processing: 1, completed: 1, failed: 1 }`

#### Scenario: Query progress with all completed
- **WHEN** the client sends `POST /enrich/progress` with IDs where all have `enrichment_status = "completed"`
- **THEN** the system returns `{ total: N, pending: 0, processing: 0, completed: N, failed: 0 }`

#### Scenario: Query with empty IDs array
- **WHEN** the client sends `POST /enrich/progress` with `{ ids: [] }`
- **THEN** the system returns HTTP 422 (validation error)

#### Scenario: Query requires authentication
- **WHEN** the client sends `POST /enrich/progress` without a valid auth token
- **THEN** the system returns HTTP 401

### Requirement: Bulk-ids endpoint skips completed records by default
The system SHALL NOT re-queue entities with `enrichment_status = "completed"` unless `force = true` is provided.

#### Scenario: Default behavior skips completed
- **WHEN** the client sends `POST /enrich/bulk-ids` with `{ ids: [1, 2, 3] }` where entity 3 has `enrichment_status = "completed"`
- **THEN** the system queues only entities 1 and 2, and returns `{ queued: 2, skipped: 1 }`

#### Scenario: Force re-enrichment of completed records
- **WHEN** the client sends `POST /enrich/bulk-ids` with `{ ids: [1, 2, 3], force: true }` where entity 3 has `enrichment_status = "completed"`
- **THEN** the system queues all 3 entities, and returns `{ queued: 3, skipped: 0 }`

#### Scenario: All selected are already completed without force
- **WHEN** the client sends `POST /enrich/bulk-ids` with `{ ids: [1, 2] }` where both are `completed` and `force` is not set
- **THEN** the system returns `{ queued: 0, skipped: 2 }`

### Requirement: Frontend displays persistent progress toast during bulk enrichment
The frontend SHALL show a persistent floating toast that displays real-time progress of the bulk enrichment batch.

#### Scenario: Progress toast appears on batch start
- **WHEN** the user triggers bulk enrichment and the API returns successfully
- **THEN** a progress toast appears showing "Enriching 0/N..." with a progress bar at 0%

#### Scenario: Progress toast updates with live counts
- **WHEN** the progress poll returns `{ completed: 3, failed: 1, total: 10 }`
- **THEN** the toast updates to show "Enriching 4/10..." with the progress bar at 40%

#### Scenario: Progress toast shows completion summary
- **WHEN** the progress poll returns `pending: 0, processing: 0` (batch finished)
- **THEN** the toast morphs into a summary: "Enrichment complete: N succeeded, M failed" and auto-dismisses after 8 seconds

#### Scenario: Progress toast shows skipped info
- **WHEN** the initial bulk-ids response includes `skipped > 0`
- **THEN** the progress toast shows "Queued N, skipped M (already enriched)"

### Requirement: Row-level animated indicator for active enrichment
The entity table SHALL display an animated visual indicator on rows whose enrichment is in progress.

#### Scenario: Pending row shows pulse animation
- **WHEN** an entity row has `enrichment_status = "pending"`
- **THEN** the enrichment badge displays with a pulse animation

#### Scenario: Processing row shows pulse animation
- **WHEN** an entity row has `enrichment_status = "processing"`
- **THEN** the enrichment badge displays with a pulse animation

#### Scenario: Animation stops when status resolves
- **WHEN** an entity row transitions from "processing" to "completed" or "failed"
- **THEN** the pulse animation stops and the badge shows the final static state

### Requirement: Frontend stops progress polling when batch completes
The frontend SHALL stop polling the progress endpoint when all records in the batch have resolved (no pending or processing remaining).

#### Scenario: Polling stops on full completion
- **WHEN** the progress response returns `pending: 0` AND `processing: 0`
- **THEN** the frontend stops the progress polling interval

#### Scenario: Polling stops if component unmounts
- **WHEN** the user navigates away from the entity table while a batch is in progress
- **THEN** the progress polling interval is cleared to prevent memory leaks
