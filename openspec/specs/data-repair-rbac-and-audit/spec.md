# data-repair-rbac-and-audit Specification

## Purpose
TBD - created by archiving change affiliation-data-integrity-incident-2026-05. Update Purpose after archive.
## Requirements
### Requirement: Data-repair endpoints MUST require the super_admin role
HTTP endpoints that trigger destructive data repair SHALL require `require_role("super_admin")`. Viewer, editor, and admin roles SHALL receive HTTP 403 even when the requested operation is `dry_run=true`.

#### Scenario: Unauthenticated request to the data-repair endpoint
- **WHEN** a client calls `POST /admin/data-fixes/legacy-affiliations` without an `Authorization` header
- **THEN** the response status is 401
- **AND** no rows are inspected or modified

#### Scenario: Viewer attempts a data-repair call
- **WHEN** a viewer-role JWT calls the endpoint with `{"dry_run": true}`
- **THEN** the response status is 403
- **AND** no rows are inspected or modified

#### Scenario: Editor attempts a data-repair call
- **WHEN** an editor-role JWT calls the endpoint
- **THEN** the response status is 403

#### Scenario: Admin (non-super) attempts a data-repair call
- **WHEN** an admin-role JWT (without `super_admin`) calls the endpoint
- **THEN** the response status is 403
- **AND** the request body does not influence the outcome (admin is rejected even with `dry_run=true`)

### Requirement: Data-repair endpoints MUST default to dry-run
The endpoint's request schema SHALL default `dry_run` to `True`. Callers must explicitly send `{"dry_run": false}` to mutate data. An empty request body SHALL trigger a safe dry-run, never a write.

#### Scenario: Super-admin sends an empty body
- **WHEN** a super-admin calls the endpoint with `{}`
- **THEN** the response is 200 and `mode = "dry-run"`
- **AND** no rows are modified

#### Scenario: Super-admin sends `{"dry_run": false}`
- **WHEN** a super-admin explicitly opts out of dry-run
- **THEN** the response is 200 and `mode = "applied"`
- **AND** matching rows are modified within a single transaction

### Requirement: Data-repair endpoints MUST log every invocation
The endpoint SHALL emit a structured log line at INFO level for every invocation, capturing the caller identity, the request parameters (`dry_run`, `requeue_enrichment`, `org_id`, `limit`), and the resulting counters (`scanned`, `matched`, `fixed`). Logs SHALL be persisted by the standard application logging pipeline.

#### Scenario: Super-admin triggers a dry-run
- **WHEN** a super-admin calls the endpoint with `{"dry_run": true, "org_id": 5}`
- **THEN** the application log contains a line referencing the caller username, `dry_run=True`, `org_id=5`, and the resulting counters
- **AND** the log line is at INFO level

#### Scenario: Apply run with re-enrichment
- **WHEN** a super-admin calls the endpoint with `{"dry_run": false, "requeue_enrichment": true}`
- **THEN** the log line records `mode=applied`, `requeue_enrichment=True`, and the final counters
- **AND** the log entry is correlated with the request via the standard request_id

### Requirement: Request payloads MUST reject unknown fields and enforce bounds
The endpoint SHALL reject requests containing fields not declared in `LegacyAffiliationFixRequest` (Pydantic `extra="forbid"`). Numeric inputs SHALL be bounded: `org_id ≥ 1`, `limit ≥ 1`, `limit ≤ 1_000_000`.

#### Scenario: Request with an unknown field
- **WHEN** a super-admin sends `{"dry_run": true, "evil": "x"}`
- **THEN** the response is 422
- **AND** no migration runs

#### Scenario: Request with `org_id = 0`
- **WHEN** a super-admin sends `{"org_id": 0}`
- **THEN** the response is 422

#### Scenario: Request with `limit = 0`
- **WHEN** a super-admin sends `{"limit": 0}`
- **THEN** the response is 422

