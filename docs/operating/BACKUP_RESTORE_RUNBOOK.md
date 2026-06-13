# UKIP Backup, Restore, and Disaster Recovery Runbook

This runbook is the repository procedure for protecting and recovering UKIP.
It does not prove that provider resources are provisioned or that a restore
drill has passed. Provider provisioning, two successful backup cycles, and the
first isolated restore drill remain pending operator actions until evidence is
completed and approved.

## Objectives and Thresholds

- RPO: 24 hours
- RTO: 4 hours
- Warning threshold: older than 24 hours
- Critical threshold: older than 26 hours
- Retention: 7 daily, 4 weekly, and 3 monthly recovery points

## Ownership and Escalation

- The operations operator provisions backup resources, reviews daily results,
  performs drills, and records non-secret evidence.
- The application owner confirms release and Alembic revision compatibility.
- The security or privacy approver reviews storage location, encryption,
  failures, sanitization, and evidence completeness.
- The incident commander owns recovery priority and requests production
  cutover approval.
- Any failed job, missing integrity metadata, unreachable provider, or recovery
  point older than 26 hours is a critical operational event. Escalate it
  immediately and treat backup protection as unavailable.

## Recovery Scope

Restorable assets:

- PostgreSQL, including application records, tenant boundaries, configuration,
  and the Alembic version table.
- The `ukip_static_data` persistent volume, including operator-managed static
  assets required by the application.

Reconstructible assets:

- Redis is reconstructible cache and queue state; do not treat it as a source
  of record.
- ChromaDB is reconstructible from PostgreSQL and source documents. Re-index it
  after database recovery.
- DuckDB analytical artifacts are reconstructible from authoritative data and
  controlled import inputs.

Application secrets, S3 credentials, database credentials, and backup payloads
must never be posted to the UKIP evidence API or committed as evidence.

## 1. Configure Dokploy PostgreSQL Backups

1. In Dokploy, enable automated PostgreSQL backups for the production database.
2. Schedule at least one encrypted backup every 24 hours.
3. Send backups to an off-site S3-compatible destination separate from the VPS.
4. Configure retention for 7 daily, 4 weekly, and 3 monthly recovery points.
5. Record the provider, bucket region, schedule, retention policy, and operator
   owner in the approved operations system.
6. Confirm the job reports size, integrity reference, encryption state, start
   time, completion time, and a provider backup ID.

Do not place S3 access keys or dump credentials in UKIP application environment
variables. Dokploy or the backup provider owns those credentials.

## 2. Configure S3-Compatible Storage

1. Require server-side encryption and TLS in transit.
2. Select and record the region approved for UKIP data residency.
3. Enable bucket versioning.
4. Enable object lock or an equivalent immutability control where supported.
5. Grant the backup identity only the permissions required to write, verify,
   list, and restore its assigned backup objects.
6. Restrict deletion and retention-policy changes to separately authorized
   operator identities.
7. Test provider access without exposing credentials in logs or evidence.

## 3. Protect the Static Volume

1. Configure an encrypted backup of `ukip_static_data`.
2. Align its schedule and retention with the PostgreSQL recovery points.
3. Record a manifest or integrity checksum that associates the volume snapshot
   with its database backup ID and release.
4. Verify that the static backup can be mounted only in an isolated recovery
   environment during a drill.

## 4. Record Terminal Backup Metadata

After each completed or failed provider job, provider automation posts
non-secret metadata to:

```text
POST /ops/backups/events
```

Use a dedicated admin operations credential. Include the environment, provider,
backup ID, release, Alembic revision, timestamps, size, integrity reference,
encryption state, storage region, retention class, and provider state. Do not
include database URLs, passwords, tokens, credentials, connection strings,
bucket keys, or backup contents.

The immutable `operator` field is derived from the authenticated UKIP identity.
Any provider-reported actor belongs only in clearly labeled non-secret evidence.

## 5. Verify Freshness

1. Check `GET /ops/backups/status?environment=production`.
2. Check `GET /ops/checks` and locate `backup_freshness`.
3. Confirm a valid recovery point is no older than the RPO: 24 hours.
4. Investigate a warning immediately before it reaches 26 hours.
5. For a critical result, restore provider access or complete a valid backup,
   then reassess both endpoints.
6. Verify alert delivery by simulating a stale condition without deleting or
   altering immutable evidence.

Provider reachability must come from an explicit operator or monitoring probe;
absence of a probe is not proof of reachability.

## 6. Prepare an Isolated Restore Drill

Every drill requires an isolated restore environment with a separate network,
database, credentials, storage path, and application URL. Never restore a drill
over production.

Before loading data:

1. Select an approved PostgreSQL backup and matching `ukip_static_data`
   recovery point.
2. Record the backup ID, release, Alembic revision, completion timestamp,
   integrity reference, region, and restore start timestamp.
3. Provision an empty drill database and isolated static volume.
4. Disable schedulers, webhooks, and notifications in drill.
5. Disable outbound enrichment calls, report delivery, background imports, and
   any integration that could mutate external systems.
6. Ensure drill credentials cannot access production resources.
7. Obtain approval to use the selected recovery point and drill target.

## 7. Restore PostgreSQL and Static Data

1. Verify the selected backup's integrity reference before restore.
2. Restore PostgreSQL into the empty isolated drill database using the
   provider-supported restore operation.
3. Do not run migrations during validation. The restored Alembic revision must
   match the expected revision for the selected release.
4. Restore the matching `ukip_static_data` snapshot into the isolated volume.
5. Start only the minimum read-only services needed for validation.
6. Record provider job IDs, timestamps, warnings, and failures without secrets.

## 8. Run the Restore Validator

From the repository root, populate the drill metadata variables. Set
`DRILL_DATABASE_URL` only in a controlled operator shell using a short-lived,
read-only database credential. The URL is secret because it normally contains
credentials: disable shell tracing, do not place it directly in command
history, restrict process inspection on the drill host, and unset it
immediately after validation. Run this exact command:

```bash
python -m backend.scripts.validate_restore \
  --database-url-env "DRILL_DATABASE_URL" \
  --environment "isolated-drill" \
  --backup-id "$BACKUP_ID" \
  --operator "$OPERATOR" \
  --expected-revision "$EXPECTED_REVISION" \
  --backup-completed-at "$BACKUP_COMPLETED_AT" \
  --restore-started-at "$RESTORE_STARTED_AT" \
  --tenant-a "$TENANT_A" \
  --tenant-b "$TENANT_B" \
  --output "$VALIDATION_REPORT"
```

Do not add `--allow-production-target` during a routine drill. A nonzero exit
means validation failed. Preserve the structured report, calculate its checksum,
and do not reinterpret a failed required check as a pass. After the command,
run `unset DRILL_DATABASE_URL` and remove any shell-history entry or temporary
credential material created for the drill.

## 9. Rebuild Reconstructible Stores

1. Re-index ChromaDB from the restored PostgreSQL records and approved source
   documents.
2. Recreate required DuckDB analytical artifacts from authoritative inputs.
3. Start Redis empty and allow only controlled cache reconstruction.
4. Compare representative record counts and tenant-scoped queries with the
   validation report.
5. Keep schedulers and outbound integrations disabled throughout reconstruction.

## 10. Complete and Approve Evidence

Use the
[backup and restore evidence template](templates/BACKUP_RESTORE_EVIDENCE_TEMPLATE.md).
Attach or reference:

- provider backup and restore job IDs;
- release and Alembic revision;
- selected recovery-point timestamps;
- validator report and checksum;
- expected and achieved RPO/RTO;
- PostgreSQL and static-volume integrity evidence;
- ChromaDB re-index result;
- failures, risks, and corrective actions;
- operator and independent approver decisions.

Record a `restore_drill` event only after validation is complete. Use `passed`
only when every required check and objective passes; use `passed_with_risk` or
`failed` when the evidence supports those outcomes. Approval of this repository
procedure is not approval of a specific drill.

## 11. Sanitize and Remove the Drill

1. Export only approved, non-secret evidence.
2. Stop all drill services.
3. Revoke temporary credentials.
4. Delete isolated database, static volume, generated indexes, caches, and
   temporary reports according to the approved sanitization process.
5. Verify that no restored personal data or backup payload remains on operator
   workstations, temporary volumes, logs, or CI artifacts.
6. Record cleanup completion and approver confirmation in the evidence.

## 12. Incident Restore and Cutover

During an incident:

1. The incident commander declares the recovery scope and selects an approved
   recovery point.
2. Follow the same isolated restore and validator steps before considering
   production traffic.
3. Review data loss against RPO: 24 hours and elapsed recovery time against
   RTO: 4 hours.
4. Document unresolved validation failures, security risks, and business impact.
5. Incident cutover requires separate approval from the incident commander and
   designated production approver.
6. Only after that approval may operators update production routing or replace
   production data.
7. Preserve the incident timeline, evidence, approvals, and corrective actions.
