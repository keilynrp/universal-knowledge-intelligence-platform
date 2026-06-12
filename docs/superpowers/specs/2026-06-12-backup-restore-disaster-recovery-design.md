# Backup, Restore, and Disaster Recovery Design

**Status:** Approved design  
**Date:** 2026-06-12  
**Story:** US-073  
**Control:** ER-BCP-001  
**Target deployment:** Controlled enterprise pilot on Dokploy

## 1. Purpose

Establish a measurable backup and recovery program for UKIP. The program must
restore critical customer state after operator error, database failure,
deployment failure, or loss of the primary VPS without relying on undocumented
knowledge.

This design sets the initial pilot objectives:

- Recovery Point Objective (RPO): 24 hours.
- Recovery Time Objective (RTO): 4 hours.

These objectives are initial supported targets, not proven claims, until a
restore drill completes within both limits.

## 2. Scope

### Restorable state

The following state must be backed up and restorable:

- PostgreSQL database, including tenant data, users, audit records, lifecycle
  evidence, configuration, and encrypted credentials;
- the `ukip_static_data` volume containing customer branding and other
  persistent static uploads;
- backup metadata required to identify release, schema revision, environment,
  source database, and encryption context.

### Reconstructible state

The following state is not part of the critical backup set:

- Redis cache;
- ChromaDB vector indexes;
- DuckDB or in-memory analytical derivatives;
- generated reports or transient exports that can be regenerated;
- container images, which remain pinned and available from GHCR.

ChromaDB reconstruction uses PostgreSQL as the canonical source and the
tenant-scoped re-index workflow. Recovery is not complete for RAG-dependent
features until re-indexing has finished or those features are explicitly
declared degraded.

## 3. Backup Architecture

The primary mechanism is the managed Dokploy/PostgreSQL backup facility writing
encrypted backups to an S3-compatible off-site bucket.

Each successful backup must produce or expose:

- immutable backup identifier;
- start and completion timestamps;
- source environment and database identity;
- related UKIP release and Alembic revision;
- backup size;
- checksum or provider integrity identifier;
- encryption status;
- storage provider and region;
- retention class;
- completion status and error detail.

The application does not implement its own database scheduler in the first
version. A small UKIP verification layer checks backup freshness and records
operational evidence without handling database credentials or backup payloads.

## 4. Schedule and Retention

The initial policy is:

- one backup every 24 hours;
- retain 7 daily recovery points;
- retain 4 weekly recovery points;
- retain 3 monthly recovery points.

The provider configuration must prevent an application administrator from
silently deleting all retained recovery points with ordinary UKIP credentials.
Bucket versioning or object lock is preferred when supported and affordable.

Retention deletion must be performed by the backup platform or a dedicated
operations identity, never by the UKIP web process.

## 5. Freshness Monitoring

A backup is healthy when:

- the latest completed backup is no older than 26 hours;
- its size is greater than zero and within an explainable range;
- integrity metadata is present;
- the provider reports a successful terminal state.

The freshness check must expose:

- `ok`, `warning`, or `critical`;
- age of latest successful backup;
- latest backup ID and completion timestamp;
- last failure timestamp and reason, when available;
- RPO target and threshold;
- evidence collection timestamp.

Thresholds:

- `ok`: latest valid backup age is at most 24 hours;
- `warning`: older than 24 hours and at most 26 hours;
- `critical`: older than 26 hours, absent, corrupt, or provider unreachable
  beyond the configured check grace period.

Provider unavailability must not be reported as a successful backup.

## 6. Restore Workflow

Restores always run into an isolated environment first.

The operator workflow is:

1. Declare the drill or incident and record its identifier.
2. Select a backup that satisfies the desired recovery point.
3. Provision an isolated PostgreSQL target and static volume.
4. Restore PostgreSQL and the static volume.
5. Run schema and migration compatibility checks.
6. Start UKIP using the release recorded in the backup manifest.
7. Verify authentication, tenant isolation, record counts, audit evidence,
   critical import data, authority data, and static assets.
8. Rebuild ChromaDB and other derived state.
9. Run application smoke tests.
10. Record achieved RPO, RTO, data differences, failures, and operator actions.
11. Destroy or sanitize the drill environment according to policy.

A production cutover requires a separate incident decision and must not happen
automatically after a drill restore.

## 7. Restore Validation

The drill acceptance suite must verify:

- the database starts and Alembic revision matches the manifest;
- an admin can authenticate;
- at least two test tenants remain isolated;
- representative entity, audit, lifecycle, and encrypted-credential records
  exist and are readable through governed application paths;
- branding/static assets resolve;
- `/health` and required operational checks pass;
- ChromaDB reconstruction preserves tenant metadata;
- no production callbacks, webhooks, schedules, or notifications fire from the
  drill environment.

Secrets used in the drill must be isolated from production. Restored encrypted
credentials may be validated for decryptability without calling external
providers.

## 8. Failure Handling

The program must address:

- missing or stale backup;
- checksum or provider integrity failure;
- incomplete static-volume backup;
- incompatible application release or schema revision;
- unavailable bucket or lost provider credentials;
- insufficient restore storage;
- restoration by an unauthorized operator;
- accidental production connection from the drill environment;
- ChromaDB rebuild failure.

Failures are terminal and visible. The operator must not mark a drill successful
when critical data is restored but required validation is incomplete.

## 9. Security and Privacy

- Backups must be encrypted in transit and at rest.
- Backup credentials must be separate from application runtime credentials.
- Access follows least privilege and is logged by the storage provider.
- Evidence contains metadata, not database contents or secret values.
- Restore environments inherit production-equivalent tenant controls.
- Drill data is deleted after evidence capture unless an incident hold applies.
- Storage region must be recorded and later governed by ER-DEP-001.

## 10. Evidence Model

Each backup or restore drill produces a versioned evidence record containing:

- evidence schema version;
- control and story IDs;
- environment and release;
- backup ID and selected recovery point;
- start/end timestamps;
- expected and achieved RPO/RTO;
- validation results;
- failures and corrective actions;
- operator and approver;
- checksums for attached reports;
- final outcome: passed, failed, or passed with accepted residual risk.

Evidence is retained for at least 12 months. It must be exportable later through
the ER-AUD-001 evidence pack.

## 11. Maturity Gates

`ER-BCP-001` advances only with evidence:

- `specified`: this design, runbook contract, acceptance tests, and owners are
  approved;
- `implemented`: Dokploy/S3 configuration, verification checks, evidence
  schema, and runbook exist;
- `verified`: two successful backup cycles and one isolated restore drill meet
  RPO/RTO and validation criteria;
- `operated`: scheduled backups and monitoring run through the agreed
  observation window with alert ownership;
- `auditable`: retained evidence is versioned, attributable, exportable, and
  independently inspectable.

This design approval alone moves no maturity state.

## 12. Implementation Units

Implementation will be split into:

1. backup inventory and configuration contract;
2. backup metadata/evidence schema;
3. provider-neutral freshness check;
4. operations endpoint and alert integration;
5. backup and restore runbook;
6. isolated restore validation script;
7. legal and operating-document claim reconciliation;
8. first operational configuration and restore drill.

Provider-specific credentials and bucket provisioning remain operator actions
and must not be committed to the repository.

## 13. Rollback

Monitoring and evidence collection can be disabled without deleting backups.
The existing provider-managed backup configuration remains active during any
verification-layer rollback.

No implementation change may reduce retention or delete existing recovery
points until a newer configuration has completed a successful restore drill.

## 14. Completion Criteria

US-073 implementation is complete when:

- the runbook exists and matches the deployed provider configuration;
- daily encrypted off-site backups are active;
- retention is configured and evidenced;
- freshness monitoring alerts on a backup older than 26 hours;
- two backup cycles and one isolated restore drill pass;
- achieved RPO is at most 24 hours and RTO at most 4 hours;
- reconstructible-state limitations are visible;
- evidence is retained and linked from the control register;
- legal and procurement documents state the actual maturity without claiming
  an unexecuted drill.
