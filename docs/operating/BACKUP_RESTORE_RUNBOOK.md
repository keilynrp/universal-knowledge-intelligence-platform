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

**Set `scope` on every event**: `database` for a PostgreSQL dump (the default)
and `volume` for a `ukip_static_data` archive. Freshness is judged per scope
and the database scope governs the overall verdict, so a volume archive can
never stand in for a missing dump. Before the field existed, the status
endpoint reported whichever job finished last — with the volume job running
five minutes after the database job, a failing dump would have been masked by
a 10 KB archive of an empty directory. `GET /ops/backups/status` reports the
newest volume archive separately in `latest_volume_backup`; an environment with
no volume backup is not thereby unhealthy.

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

### 5a. Automated Backup-Object Observation (not the overall authority)

`.github/workflows/backup-freshness.yml` runs daily and, once configured (see
Operator Actions below), lists the newest object in the backup bucket with
read-only provider credentials and fails only on conditions it can directly
observe from that listing: `backup_missing` (no object exists),
`backup_empty` (newest object's size is `<= 0`), or `backup_timestamp_invalid`
(the timestamp is absent, unparseable, or clearly in the future beyond a
small clock-skew tolerance). It holds no UKIP application credential of any
kind, calls no UKIP API endpoint, and does not mutate application state — it
cannot POST to `POST /ops/backups/events` or read `GET /ops/backups/status`.

**This workflow is provider observation only — it holds no local
RPO/freshness policy and is not the overall backup-assurance authority.**
The authoritative RPO/freshness policy remains exclusively the
backend/evidence process (`GET /ops/backups/status`, backed by
`backend.backup_assurance.evaluate_backup_freshness`, section 4/5 above). The
workflow does compute the newest object's age, but purely as informational
evidence/logging — labeled "observed object age" and explicitly stated to
not be an RPO/freshness pass-fail decision. An earlier draft reintroduced a
local `WARNING_AFTER_HOURS`/`CRITICAL_AFTER_HOURS` threshold and failed runs
on it; that was rejected on strategic review for duplicating the backend's
authority and was removed (see
[ER-BCP-001-HISTORICAL-RECONCILIATION.md](ER-BCP-001-HISTORICAL-RECONCILIATION.md)).
A green run of this workflow means only "the newest object this job could
see exists, is non-empty, and has a valid timestamp" — it does not mean
overall backup assurance is `ok`, and it does not mean the backup is fresh
enough to meet RPO. The backend may independently report `critical` (for
example: `provider_unreachable`, or `integrity_missing` on the actual
recorded event) even when this workflow's run is green.

The S3-compatible provider's ETag is retained only as non-secret, informational
provider metadata (an object/version identifier) and is never treated as
integrity evidence — an ETag is not guaranteed to be a full-object checksum,
so this workflow always projects `integrity_missing` as an expected,
structural, non-blocking limitation until a provider-verified checksum path
exists (Phase B). It also deliberately does not assert `provider_reachable` —
that signal must stay fresh within 15 minutes
(`backend.backup_assurance.PROVIDER_REACHABILITY_MAX_AGE_MINUTES`), which a
daily workflow cannot honestly provide. See
[ER-BCP-001-HISTORICAL-RECONCILIATION.md](ER-BCP-001-HISTORICAL-RECONCILIATION.md)
for the audit that produced this design and for the residual risks this gap
represents.

Automated application-side evidence ingestion (recording the observed object
as a `backup` event via `POST /ops/backups/events`) is deferred until a
least-privilege credential/path exists — every route under `/ops`, including
the read-only status endpoint, currently requires `admin` scope
(`backend/api_key_scopes.py`), which is too broad to store in a GitHub-hosted
scheduled workflow. Until that narrower mechanism exists, evidence ingestion
into `backup_assurance_events` is a manual or trusted-service operator step
(section 4 above); see §13 below.

Until the required secrets exist, every run of this workflow fails fast with
a clear, non-secret error rather than silently no-op'ing.

### 5b. Provider Reachability Probe (B4)

`evaluate_provider_reachability` treats an assertion older than
`PROVIDER_REACHABILITY_MAX_AGE_MINUTES` (15) as stale. A container's
environment cannot be changed while it runs, so `UKIP_BACKUP_PROVIDER_REACHABLE`
/ `..._AT` can never carry a signal that stays fresh — they are kept only for
compatibility. The refreshable channel is a heartbeat document:

`scripts/ukip-backup-reachability-probe.sh` runs on the production host every
5 minutes, lists the backup prefix with the **read-only** provider credential,
and writes `{"reachable": <bool>, "observed_at": "<UTC ISO-8601>"}` atomically
to `UKIP_REACHABILITY_OUT`. The backend reads that file through a **read-only**
mount and applies the same staleness rule, so a probe that dies makes the
signal fail closed on its own. The application still holds no provider
credential, and the document carries no bucket, path or key material.

**OPERATOR ACTION REQUIRED — install on the production host:**

1. Create the signal directory and install the script:

```bash
install -d -m 0755 /var/lib/ukip/signals
install -m 0755 scripts/ukip-backup-reachability-probe.sh \
  /usr/local/bin/ukip-backup-reachability-probe.sh
```

2. Create `/etc/ukip/backup-probe.env`, **root-owned, mode 0600**, holding the
   read-only credential and the non-secret endpoint/bucket/prefix. This is the
   only place the credential exists on the host; never put it in the script,
   in the compose file, or in the application environment.

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=...
S3_BACKUP_ENDPOINT=...
S3_BACKUP_BUCKET=...
S3_BACKUP_PREFIX=...
```

3. Install the systemd units and start the timer:

```ini
# /etc/systemd/system/ukip-backup-probe.service
[Unit]
Description=UKIP backup provider reachability probe
[Service]
Type=oneshot
EnvironmentFile=/etc/ukip/backup-probe.env
ExecStart=/usr/local/bin/ukip-backup-reachability-probe.sh
```

```ini
# /etc/systemd/system/ukip-backup-probe.timer
[Unit]
Description=Run the UKIP backup provider reachability probe every 5 minutes
[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
AccuracySec=30s
[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload && systemctl enable --now ukip-backup-probe.timer
```

The script picks its runner itself (`UKIP_AWS_RUNNER`, default `auto`): it uses
`aws` when the host has the CLI, and otherwise runs the pinned
`amazon/aws-cli` image through Docker, forwarding the credential by variable
name so it never reaches the host's process list. `ExecStart` is the same in
both cases — do not hand-write a wrapper on the server, or production ends up
running code that no review ever saw.

On a Docker-only host, pull the image once before enabling the timer, so a slow
first pull is not mistaken for an unreachable provider:

```bash
docker pull amazon/aws-cli:latest
```

The service unit then needs Docker available:

```ini
[Unit]
After=docker.service
Requires=docker.service
```

4. In Dokploy, set `UKIP_BACKUP_SIGNAL_DIR=/var/lib/ukip/signals` and
   `UKIP_BACKUP_PROVIDER_REACHABILITY_FILE=/run/ukip-signals/backup-provider-reachability.json`,
   then redeploy so the read-only mount and the variable take effect.

**Verify** (no secrets in any output):

```bash
systemctl list-timers ukip-backup-probe.timer
cat /var/lib/ukip/signals/backup-provider-reachability.json
curl -s -H "Authorization: Bearer $TOKEN" https://<api-host>/ops/backups/status
```

`provider_reachability_source` must read `timestamped_file_assertion`, and
`provider_unreachable` must be gone from `reason_codes`. Stop the timer for
20 minutes and the source must become `stale_file_assertion` with the reason
back — that check is what proves the signal is measured rather than asserted.

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
  --expected-target-host "$DRILL_DATABASE_HOST" \
  --expected-target-database "$DRILL_DATABASE_NAME" \
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
[backup and restore evidence template](templates/BACKUP_RESTORE_EVIDENCE_TEMPLATE.md)
for each cycle and for the drill. Roll both cycles and the drill up into the
[ER-BCP-001 readiness evidence dossier](templates/ER-BCP-001_READINESS_EVIDENCE_TEMPLATE.md)
that covers the full gate: provider configuration, two backup cycles, and the
first isolated restore drill. Attach or reference:

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

## 13. Operator Actions Pending

Repository readiness work (this document, the backup-assurance API, and
`.github/workflows/backup-freshness.yml`) cannot itself provision live
infrastructure. Each item below is a live-provider or secret action an
operator must perform outside this repository before evidence can be
collected. None of these have been executed by this change.

1. **Configure the S3-compatible backup destination in Dokploy** — create the
   bucket, write credentials, schedule, and retention per sections 1–3 above.
   Verify read-only via `aws s3api list-objects-v2 --endpoint-url <endpoint>
   --bucket <bucket> --prefix <prefix>` using the read-only credentials only.
   Dokploy writes each backup to `<service appName>/<configured prefix>/`,
   not to the configured prefix alone — read the real key from the bucket
   and scope IAM policies and lifecycle rules to that full path.
   Rollback: remove the Dokploy backup destination; the bucket and its objects
   are unaffected by application code either way.
2. **Create two S3 credential sets scoped to the backup bucket only** — write
   (for Dokploy) and read-only (for CI). Never place either in application
   environment variables. Verify least privilege by attempting a write with
   the read-only key and confirming it is denied. Rollback: revoke and
   recreate the keys at the provider.
3. **Add repository secrets** `S3_BACKUP_ENDPOINT`, `S3_BACKUP_BUCKET`,
   `S3_BACKUP_RO_ACCESS_KEY_ID`, `S3_BACKUP_RO_SECRET_ACCESS_KEY` — used only
   by `backup-freshness.yml`, read-only. No UKIP application secret is
   required by this workflow. Also set the non-secret repository
   **variable** `S3_BACKUP_PREFIX` to the full key prefix Dokploy writes to
   (unset falls back to `pg/`, which Dokploy never writes to on its own). Verify by re-running the workflow via
   `workflow_dispatch` and confirming it passes the first guard step.
   Rollback: delete the secrets; the workflow fails closed at the same guard
   step it fails at today.
4. **Evidence ingestion into `backup_assurance_events` remains manual or
   trusted-service, by design, until a least-privilege credential exists** —
   `backend/api_key_scopes.py` classifies every route under `/ops` (including
   the read-only `GET /ops/backups/status`) as requiring `admin` scope; there
   is no narrower role today. Storing an admin-scoped UKIP API key in a
   GitHub-hosted scheduled workflow was assessed on strategic review as too
   broad a trust boundary for "record backup evidence", so
   `backup-freshness.yml` deliberately holds no UKIP application credential
   and does not POST to `POST /ops/backups/events`. Until a narrower
   evidence-ingestion scope/credential is designed (a bounded follow-up, not
   part of this change), record each completed or failed provider job via
   section 4 above using a trusted operator identity or a trusted colocated
   service — never a GitHub Actions secret. Rollback: none required; this is
   the current, intended fail-closed state, not a temporary gap to revert.
5. **Install the provider reachability probe (§5b)** — the repository now
   ships the mechanism, but it must be installed on the production host. Until
   it is, `provider_reachable` correctly reports `false` and
   `GET /ops/backups/status` stays `critical` with reason
   `provider_unreachable`; that is expected, not a defect, and it must never
   be papered over by setting `UKIP_BACKUP_PROVIDER_REACHABLE=1` by hand — a
   static assertion goes stale after 15 minutes anyway and, before it does, it
   claims something nobody measured. Rollback: unset
   `UKIP_BACKUP_PROVIDER_REACHABILITY_FILE` and stop the timer.
6. **Observe the first two backup cycles and run the first isolated restore
   drill** against a demonstrably non-production target per sections 5–12,
   using the
   [readiness evidence dossier](templates/ER-BCP-001_READINESS_EVIDENCE_TEMPLATE.md).
   This is Phase B/C/D work and is explicitly out of scope for this change.
