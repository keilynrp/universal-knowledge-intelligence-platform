## ADDED Requirements

### Requirement: Job state persistence in Postgres
The engine SHALL persist job state transitions to an `engine_jobs` Postgres table, replacing the in-memory-only DashMap for durable storage.

#### Scenario: Job creation persisted
- **WHEN** a new job is created via `ProcessAsync`
- **THEN** a row SHALL be inserted into `engine_jobs` with status="queued", pipeline name, job_id, and created_at timestamp

#### Scenario: Job completion persisted
- **WHEN** a running job completes successfully
- **THEN** the `engine_jobs` row SHALL be updated with status="completed", result JSON, and completed_at timestamp

#### Scenario: Job failure persisted
- **WHEN** a running job fails
- **THEN** the `engine_jobs` row SHALL be updated with status="failed" and error message

### Requirement: Hot cache for active jobs
The engine SHALL maintain an in-memory DashMap cache for active jobs (queued, running) to avoid database round-trips on frequent status polls.

#### Scenario: Status check hits cache
- **WHEN** `GetJobStatus` is called for a running job
- **THEN** the engine SHALL return state from the in-memory cache without a database query

#### Scenario: Status check for completed job
- **WHEN** `GetJobStatus` is called for a job that has been evicted from the cache (completed/failed)
- **THEN** the engine SHALL query the `engine_jobs` table and return the persisted state

### Requirement: Startup recovery
On startup, the engine SHALL mark any `engine_jobs` rows with status="running" or status="queued" as status="failed" with error="engine restarted".

#### Scenario: Stale running job on restart
- **WHEN** the engine starts and finds jobs with status="running" in the database
- **THEN** it SHALL update them to status="failed" with error="engine restarted" and failed_at timestamp

### Requirement: Job history query
The engine SHALL support querying job history via a new `ListJobs` gRPC endpoint with filtering by pipeline name and status.

#### Scenario: List recent jobs
- **WHEN** `ListJobs` is called with limit=50
- **THEN** the engine SHALL return the 50 most recent jobs ordered by created_at descending

#### Scenario: Filter by pipeline
- **WHEN** `ListJobs` is called with pipeline_filter="compute_authority"
- **THEN** the engine SHALL return only jobs for that pipeline

### Requirement: engine_jobs table schema
The `engine_jobs` table SHALL have columns: id (UUID PK), job_id (TEXT UNIQUE), pipeline (TEXT), status (TEXT), progress (REAL), result_json (TEXT NULL), error (TEXT NULL), created_at (TIMESTAMPTZ), started_at (TIMESTAMPTZ NULL), completed_at (TIMESTAMPTZ NULL).

#### Scenario: Table created on first run
- **WHEN** the engine starts and the `engine_jobs` table does not exist
- **THEN** the engine SHALL create it via a migration
