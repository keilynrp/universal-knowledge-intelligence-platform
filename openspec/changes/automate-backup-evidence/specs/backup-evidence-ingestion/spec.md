## ADDED Requirements

### Requirement: Backup evidence documents are ingested automatically

The system SHALL, on each ops-monitor cycle, record a `backup` event for every
valid evidence document in the configured evidence directory that does not
already have a `backup` event for the same environment, scope and backup id,
with operator `system:backup-recorder`.

#### Scenario: A new backup is recorded

- **WHEN** a valid document for `database` backup `pg/2026-09-25T03-00-00-076Z.sql.gz` appears
- **AND** no `backup` event exists for it
- **THEN** one `completed` event is recorded with `integrity_ref = sha256:<hex>`,
  the document's size and `completed_at`, and operator `system:backup-recorder`

#### Scenario: Freshness recovers without a person

- **WHEN** the only newer evidence is an automatically ingested document from
  today
- **THEN** `backup_freshness` is evaluated against it and is not `critical` for
  staleness

#### Scenario: Ingestion is idempotent

- **WHEN** the same document is seen on two cycles, or a person already
  recorded that backup manually
- **THEN** no second event is recorded

#### Scenario: A manual record with a longer key path still counts

- **WHEN** a manual event recorded backup id `ukip-dbukip-eqmmhw/pg/2026-09-25T03-00-00-076Z.sql.gz`
- **AND** a document arrives for `pg/2026-09-25T03-00-00-076Z.sql.gz` in the same scope
- **THEN** it is treated as the same backup and not recorded again

#### Scenario: A dump that fails its gzip test is recorded as failed

- **WHEN** a `database` document carries `gzip_ok: false`
- **THEN** the recorded event has status `failed`

### Requirement: Evidence documents are validated strictly

The system SHALL reject, log by file name and reason, and skip any evidence
document that is over 8 KB, malformed, has missing or unknown keys, declares
another environment, an unknown scope, a digest that is not 64 lowercase hex
characters, a non-positive size, or a `completed_at` in the future or older than
14 days. It SHALL NOT follow symlinks or read subdirectories.

#### Scenario: Another environment's document is refused

- **WHEN** a document declares `environment: staging` on a production backend
- **THEN** no event is recorded and the rejection names the file

#### Scenario: A malformed document does not stop ingestion

- **WHEN** one document is malformed and another is valid
- **THEN** the valid one is recorded and the monitor cycle completes

### Requirement: The recorder measures what the provider stores

The recorder SHALL compute SHA-256 over the stored object's bytes (never the
provider ETag), SHALL run `gzip -t` on database dumps, and SHALL write no
document when the object cannot be read in full.

#### Scenario: An interrupted download writes nothing

- **WHEN** streaming the newest object fails partway
- **THEN** no evidence document is written for it
