# ER-BCP-001 Provider Readiness Evidence Dossier — 2026-09-21

Filled-in copy of
[ER-BCP-001_READINESS_EVIDENCE_TEMPLATE.md](templates/ER-BCP-001_READINESS_EVIDENCE_TEMPLATE.md)
for issue #320. Non-secret evidence only: bucket name, account identifiers,
host names and admin user names are deliberately omitted (public repository).
The per-phase detail lives in the issue #320 comments this dossier links to.

**Outcome in one line:** provider configuration and two scheduled backup
cycles are evidenced; the first isolated restore drill **restored the backup
completely and within RTO, but the drill is recorded as `failed`**, because two
required checks failed (RPO of the chosen recovery point, and tenant
isolation, which production data cannot demonstrate). Nothing here supports a
maturity change.

## Identification

- Control ID: `ER-BCP-001`
- Dossier date: 2026-09-21
- Environment: production (backups); isolated workstation container (drill)
- Operator: the repository owner, using the platform admin identity for
  `POST /ops/backups/events` (the event's `operator` field is derived from the
  authenticated identity, not supplied by the client)
- Approver: _pending — owner decision_
- Evidence retention target: 12 months from dossier date (until 2027-09-21)

## 1. Provider configuration evidence

Read back from the provider with `get-bucket-*` calls, not taken from the
console. Detail: #320 comment "Phase B checkpoint — provider configured and
observed (2026-09-18)".

| Item | Configured value / description | Verification reference |
| --- | --- | --- |
| Backup destination type | AWS S3 general-purpose bucket, off the VPS, written by Dokploy | Phase B comment, B1 |
| Storage region | `us-east-2` | `get-bucket-location` |
| Encryption at rest | SSE-S3 (`AES256`); SSE-C blocked | `get-bucket-encryption` |
| Encryption in transit (TLS) | Bucket policy denies `aws:SecureTransport = false` | `get-bucket-policy` |
| Bucket versioning enabled | Yes | `get-bucket-versioning` |
| Object lock / immutability | Object Lock `GOVERNANCE`, 7-day default retention | `get-object-lock-configuration` |
| Backup schedule | PostgreSQL `0 3 * * *` UTC; `ukip_static_data` volume `5 3 * * *` UTC | Dokploy; cycle objects below |
| Retention policy (daily/weekly/monthly) | Dokploy keeps latest 30; non-current versions expire after 90 days (`expire-noncurrent-pg`, `expire-noncurrent-static`). The runbook's 7/4/3 scheme is approximated, not implemented literally | `get-bucket-lifecycle-configuration` |
| Backup identity permissions (write scope) | Put/Get/Delete on the backup prefixes; `DeleteObjectVersion` denied against a real object | Phase B comment, B2 |
| CI read-only identity permissions | `ListBucket` on the prefix only; Get/Put/Delete `implicitDeny` | IAM policy simulator, B2 |
| `ukip_static_data` backup configured | Yes, Dokploy volume backup, daily | cycle 2, event id 3 |

Provider observation workflow runs (`backup-freshness.yml`, observation only,
no RPO claim): 35326126138, 35330841471, 35342913491 (first scheduled).

## 2. Backup cycle #1

- Cycle date/time (UTC): 2026-09-19 03:00:00.134Z → 03:00:03Z, scheduled
- Object: `ukip-dbukip-eqmmhw/pg/2026-09-19T03-00-00-134Z.sql.gz`, 5,947,528 B
- Integrity: `sha256:9a12948744357c43c846a2957eb6e8ad6160033f49f75722b8a109c3d29f0be7`
  over the stored bytes streamed from S3; `gzip -t` OK
- `backup_assurance_events` event ID: **1**
- `GET /ops/backups/status` at observation: `critical`, `age_hours` 2.5,
  reason codes only `provider_unreachable` (B4 not yet installed; fail-closed
  as designed)
- CI workflow run ID: 35420592194
- Release / Alembic at backup: `70e1c63` / `d1e2f3a4b5c6`
- Detail: #320 comment "Phase C — cycle 1 of 2 evidenced (2026-09-19)"

## 3. Backup cycle #2

Distinct from cycle #1: a different day, object, size and digest.

- Cycle date/time (UTC): 2026-09-20 03:00:00.076Z → 03:00:02Z, scheduled
- Objects:
  - PostgreSQL `ukip-dbukip-eqmmhw/pg/2026-09-20T03-00-00-076Z.sql.gz`,
    5,953,533 B, `sha256:8730bcfc15b19863e036e4b0dd2a3e1fc46d0eef2541e394adc24226c8bd549c`
    — event **2**
  - `ukip_static_data` `…_ukip_static_data-2026-09-20T03-05-00-066Z.tar`,
    10,240 B, `sha256:0f8c735bdabb963cb19dfed05d897ab5ad828e765d8437328c853d5b343622b5`
    — event **3**
- `GET /ops/backups/status` at observation: `ok`, `reason_codes: []`,
  `provider_reachable: true`, source `timestamped_file_assertion`
- CI workflow run ID: 35485954978
- Release / Alembic at backup: `8dcc975` / `d1e2f3a4b5c6`
- Detail: #320 comment "Phase C — cycle 2 of 2 evidenced, and a defect it
  exposed (2026-09-20)"; the scope defect and its fix are in the next comment
  (#359, #360; follow-up #361)

## 4. First isolated restore drill

Recorded as `restore_drill` event **id 4**, status **`failed`**.

- Isolated target and proof of non-production status: a throwaway Docker
  container `postgres:18` (server 18.6) on the operator's workstation, on its
  own Docker network, published only on `127.0.0.1:55432`, database
  `ukip_drill`, with a one-off generated credential that exists nowhere else.
  It has no route to production and no production credential. No application
  services were started, so there were no schedulers, webhooks or outbound
  integrations to disable (runbook §6 steps 4–5 did not apply).
- Restore-target safety check: `backend/scripts/validate_restore.py` at
  `da5540b`, **without** `--allow-production-target`; the target guard
  accepted host `127.0.0.1` / database `ukip_drill` and the read-only guard was
  installed on the connection.
- Recovery point: event 2, backup completed **2026-09-20T03:00:02Z**
- Pre-restore integrity: size and SHA-256 re-computed on the downloaded object
  and matched event 2; `gzip -t` OK. The object was fetched with a presigned
  URL generated in CloudShell, so no AWS credential reached the workstation.
- Restore decision/start: **2026-09-21T04:06:59Z** (first attempt; see
  findings)
- Restore completed: 2026-09-21T04:38:53Z (`pg_restore --no-owner --no-acl
  --exit-on-error`, exit 0, 04:37:11Z → 04:38:53Z, 1 m 42 s)
- Validated/usable: 2026-09-21T05:05:44Z (validator `collected_at`)
- Achieved RPO: **25.116 h vs ≤ 24 h — failed**
- Achieved RTO: **0.979 h vs ≤ 4 h — passed** (measured from the first,
  failed attempt, so the time lost to it is counted)
- Alembic revision: expected `d1e2f3a4b5c6`, actual `d1e2f3a4b5c6` — passed.
  The expectation is independent of the restored data: production's deploy
  log shows `current=d1e2f3a4b5c6` until `b8c9d0e1f2a3` was first attempted,
  later on 2026-09-20.
- Required-table checks: 8/8 passed (`alembic_version`, `users`,
  `organizations`, `organization_members`, `raw_entities`, `audit_logs`,
  `data_lifecycle_events`, `backup_assurance_events`)
- Tenant-isolation validation: **failed** — `tenant_fixture_count` 0,
  `cross_tenant_rows` 0. Not demonstrable on production data:
  `organizations` has 0 rows and all 1,231 `raw_entities` have `org_id` NULL.
  No fixture tenants were inserted into the restored copy, because that would
  test the fixtures rather than the backup.
- Restored inventory: 71 tables; `raw_entities` 1,231, `users` 1,
  `audit_logs` 6,275, `backup_assurance_events` 1, `organizations` 0
- Integrity/data-usability: the archive restored with `--exit-on-error` and no
  warnings, and the validator read every required table. A decrypt probe of
  encrypted columns was **not** performed: it needs the production
  `ENCRYPTION_KEY`, which does not leave production.
- Validator report: kept by the operator outside the repository (it is
  evidence, not source), `sha256:fa11587d14125cb9d709aff712fc6012b0b72361a06cddcc9ce613bd2d434d12`;
  the digest is also recorded in event 4.
- Static volume: the `ukip_static_data` archive (event 3) was downloaded, its
  size and SHA-256 matched event 3, and it was extracted into a throwaway
  Docker volume: 0 regular files, as expected for an empty volume. The volume
  was deleted afterwards.
- Confirmation no production target was mutated: yes. The only production
  write in Phase D is event 4 itself, through the append-only evidence API.

### Findings from the drill

1. **The first attempt failed on tooling, not on the backup.** At 04:06:59Z
   `pg_restore` 16 rejected the archive: `unsupported version (1.16) in file
   header`. The drill script had assumed the server version instead of reading
   it, and hid the failed probe behind a default of 16.
2. **Production runs PostgreSQL 18.6, and Dokploy's `pg_dump` is 18.6.** Both
   facts come from the archive header. A restore must use a server of the
   source major version and a `pg_restore` at least as new as the `pg_dump`
   that wrote the archive. The runbook did not say so; the same change as this
   dossier adds it to §7.
3. **The RPO failure measures this drill, not backup cadence.** The drill
   restored the 2026-09-20 recovery point on 2026-09-21 at 04:06Z, after the
   next scheduled backup already existed. An incident restore would pick the
   newest point. It is recorded as a failure anyway: the validator is the
   authority, and the runbook forbids reinterpreting a failed check.
4. **Tenant isolation cannot be proven from a backup of a single-tenant
   deployment.** This will fail on every drill until production has at least
   two organizations with entities, or until the check is redesigned. That is
   a decision for the owner (see residual risks), not something to change
   here.

### Deviations from the runbook, recorded rather than hidden

- §8 asks for a short-lived **read-only** database credential. The validator
  connected as the container's superuser. The connection was guarded
  read-only by the validator, and the container was local and throwaway, but
  the credential itself was not read-only.
- The container credential was shown once in an operator terminal and pasted
  into a working session. It was rotated immediately (`ALTER ROLE` with a new
  generated value, passed on stdin), and the procedure was changed to hand the
  URL over in a `0600` file instead of on screen.
- §9 (rebuild reconstructible stores) was not performed: ChromaDB and DuckDB
  are rebuilt from PostgreSQL and are outside the backup boundary. No re-index
  result is claimed.

### Drill sanitization (runbook §11)

- Kept outside the drill directory, non-secret: the validator report and the
  static-volume restore listing.
- To delete: the drill container and its network, the downloaded archive and
  its decompressed copy, the restore log, the metadata file and the `0600`
  connection file. The static volume was already deleted during the drill.
- Status: **done, 2026-09-21.** The operator confirmed the listing and the
  script removed the container, the network and the directory. Checked
  independently afterwards: no `ukip-drill` container, network or volume
  remains; the directory is gone; no `*.pgc`, downloaded archive or connection
  file is left under the operator's home or `/tmp`. The drill connection string
  was never exported in a shell, and the container credential died with the
  container.
- The first, failed attempt had run under `root`. Its working directory was
  moved to the operator's home before the second attempt, so this cleanup
  covered it too.

## 5. Provider reachability / freshness

- Mechanism: `scripts/ukip-backup-reachability-probe.sh`, run on the
  production host every 5 minutes by a systemd timer. It writes a timestamped
  assertion that the backend reads through a read-only mount
  (`UKIP_BACKUP_PROVIDER_REACHABILITY_FILE`); `GET /ops/backups/status`
  reports it as `timestamped_file_assertion`. Runbook §5b.
- Observed at the last status read (2026-09-20): `provider_reachable: true`.
- Not yet exercised: stopping the timer for more than 15 minutes and confirming
  the status turns `critical` with a stale-assertion reason. Open item.

## 6. Durable-state review

- `ukip_static_data` volume contents inspected: **YES** — `tar -tvf` in cycle 2
  and extraction during the drill both show an empty volume.
- Non-regenerable state found outside PostgreSQL: **NO**
- Finding: the volume holds custom branding assets only, and production has
  none (`GET /branding/settings` returns empty). It is backed up daily anyway,
  so it stays covered once branding is configured.
- Backup boundary silently expanded: no. The volume backup was an explicit
  Phase C decision, recorded as its own scope (`volume`) and evaluated
  separately from the database's freshness.
- Other non-database durable state considered (ChromaDB, DuckDB, Redis) and
  confirmed reconstructible: **YES by design, NOT verified by this drill.**
  Redis is a cache; ChromaDB and DuckDB are derived from PostgreSQL. No rebuild
  was run.

## 7. Residual risks

1. **Tenant isolation is not demonstrable from production backups** while
   production has no organizations. Every drill will fail this check until the
   owner decides between waiting for real tenants, running the check against a
   seeded non-production fixture restored from a backup, or redefining the
   check for single-tenant deployments. That choice is owner-level.
2. **No decrypt probe.** Restorability of encrypted columns is not evidenced.
   A probe needs a way to verify the production key without exporting it.
3. **Reconstructible stores not rebuilt.** ChromaDB and DuckDB recovery time is
   outside the measured RTO.
4. **Reachability fail-over not yet observed** (§5).
5. **Validator run with a superuser credential**, not a read-only one (§4
   deviations).
6. Carried over from Phase B: no S3 server access logging, so object reads by a
   leaked credential are not auditable; Dokploy exposes the writer secret in the
   response of a failed manual backup and briefly in the VPS process list;
   retention approximates the runbook scheme.
7. **CI never runs migrations** (#361). That gap put an append-only violation
   into production during Phase C.

## 8. Maturity statement

- Maturity before this dossier: `specified`
- Maturity this dossier supports: **`specified` — no change.** The first
  drill failed two required checks. Promotion needs, at minimum, a drill that
  passes or an explicit owner decision on residual risk 1, recorded in
  `docs/product/ENTERPRISE_CONTROL_REGISTER.md` and
  `backend/enterprise_controls.py` in the same change.
- Register and control updated in this change: NO (nothing to update).
