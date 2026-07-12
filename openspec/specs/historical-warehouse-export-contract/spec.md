# historical-warehouse-export-contract Specification

## Purpose
TBD - created by archiving change retrospective-intelligence-layer. Update Purpose after archive.
## Requirements
### Requirement: Warehouse exports use versioned manifests

The system SHALL write an export manifest for each warehouse export containing
`export_id`, `dataset_name`, `dataset_version`, `schema_version`, `org_scope`,
`started_at`, `finished_at`, `row_counts`, `partition_range`, `source_query`,
`checksum`, and `status`.

#### Scenario: Successful export is auditable

- **WHEN** an export of historical journal metric snapshots completes
- **THEN** the manifest records the exported row count, schema version,
  partition range, and checksum

#### Scenario: Failed export is bounded

- **WHEN** an export fails
- **THEN** the manifest records a sanitized error code and status
- **AND** does not store credentials or raw provider secrets

### Requirement: Export schemas are warehouse-compatible

The system SHALL define export schemas using warehouse-safe scalar, timestamp,
array, and JSON fields and SHALL identify partition and clustering columns.

#### Scenario: Event export includes partition fields

- **WHEN** historical events are exported
- **THEN** the dataset includes `recorded_date`, `event_type`, `org_id`, and
  `schema_version` fields suitable for partitioning or clustering

### Requirement: Exports enforce tenant boundaries

The warehouse export service SHALL require explicit tenant scope for customer
data exports and SHALL NOT export cross-tenant data unless the export is a
governed platform-level aggregate with no tenant-identifiable payload.

#### Scenario: Tenant export cannot include other tenant rows

- **WHEN** an export is requested for `org_id = 12`
- **THEN** every exported row contains `org_id = 12`

### Requirement: Export jobs are idempotent by dataset version

The system SHALL make exports idempotent using dataset name, dataset version,
org scope, and partition range.

#### Scenario: Retried export does not duplicate dataset partitions

- **WHEN** an export job is retried for the same dataset version and partition
  range
- **THEN** the final warehouse dataset contains one accepted copy of each row

### Requirement: Warehouse export remains optional for initial deployment

The retrospective layer SHALL operate without a configured warehouse, while
exposing health and readiness status for warehouse export capability.

#### Scenario: Warehouse is not configured

- **WHEN** the warehouse connector is disabled
- **THEN** retrospective event writing and snapshot querying continue to work
- **AND** export endpoints report `not_configured`

