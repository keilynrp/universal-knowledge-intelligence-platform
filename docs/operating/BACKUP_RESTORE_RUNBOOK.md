# PostgreSQL Backup & Restore Runbook (EPIC-018)

Operational procedures for backing up and restoring UKIP's PostgreSQL database
with formal RTO/RPO commitments. Backup configuration lives in Dokploy;
verification runs daily in CI.

---

## 1. Objectives

| Item | Value |
|------|-------|
| **RTO (Recovery Time Objective)** | **4 hours** |
| **RPO (Recovery Point Objective)** | **24 hours** |
| **Approved by** | Jose Paul (product/operations owner) |
| **Approval date** | 2026-06-10 |
| **Review cadence** | Yearly, or immediately after any topology change |

**What these commitments mean:** The RPO of 24 hours means we accept losing at
most one day of writes in a full-loss scenario — the backup scheduler must
produce at least one successful backup per calendar day. The RTO of 4 hours
means that from the moment a restore decision is made to the moment the system
is serving authenticated traffic again, the elapsed wall-clock time must not
exceed 4 hours. The quarterly drill (section 7) validates both numbers against
the actual restore path.

---

## 2. Scope

### Backed up

| State | Where | Notes |
|-------|-------|-------|
| PostgreSQL database | Dokploy-managed service, outside the compose stack | Single source of truth. Both `ukip-backend` and `ukip-engine` share the same database (injected via `DATABASE_URL` and `ENGINE_DATABASE_URL` respectively). One backup covers both. |

### Not backed up — regenerable

| State | Why excluded | How to regenerate |
|-------|-------------|-------------------|
| ChromaDB vectors | Fully regenerable from the source entities in PostgreSQL | Run `python scripts/reindex_chromadb_org_scope.py` after restore (EPIC-012 re-index script). |
| Redis cache | Fail-open by design; no durable state (`--save ""`, `--appendonly no` in compose) | Warms automatically on first use after service restart. |

### Open checklist item — `ukip_static_data` volume

- [ ] **During the first restore drill:** inspect the contents of the
  `ukip_static_data` volume (mounted at `/app/static` in `ukip-backend`).
  Determine whether it contains non-regenerable state (e.g. user-uploaded files
  not stored as DB rows). If non-regenerable state is found, document the
  finding and open a follow-up issue to add volume-level backup (e.g. `restic`
  or a Dokploy volume backup destination). If the contents are fully regenerable
  or empty, record that conclusion in the drill report and close this item.

---

## 3. Backup configuration (Dokploy)

Run these steps once before the first drill. Record what you actually configured
in the drill report (section 6).

**Step 1 — Create a backup bucket.**

Create an S3-compatible bucket named `ukip-backups` (recommended provider:
Cloudflare R2; any S3-compatible store works). Create **two separate credential
sets** scoped to that bucket only:

- **Write credentials** (read-write): used by Dokploy to upload backups.
- **Read-only credentials**: used by the CI freshness monitor. Granting CI only
  read access limits blast radius if the secret leaks.

**Step 2 — Add the S3 backup destination in Dokploy.**

Navigate to the PostgreSQL database service in the Dokploy UI (exact UI path
varies by Dokploy version — look for **Backups** or **Storage** under the
database service). Add a new backup destination:

- Type: S3-compatible
- Endpoint URL: your provider's S3 endpoint (e.g. `https://<account>.r2.cloudflarestorage.com`)
- Bucket: `ukip-backups`
- Access key / Secret: the **write** credentials from Step 1
- Path prefix: `pg/`

**Step 3 — Set the schedule.**

In the same Dokploy backup configuration, set the backup schedule to daily at
**03:00 UTC**.

> **Retention note:** Dokploy's backup UI may support only a simple "keep last N
> backups" retention setting. If so, set N=14 in Dokploy (covers ~2 weeks of
> daily backups) and configure the weekly/monthly retention tiers as a **bucket
> lifecycle rule** on the R2/S3 side:
>
> - Daily: keep 7 (Dokploy handles this if N≥7)
> - Weekly: keep 4 (lifecycle rule: tag with `weekly/` prefix or use S3
>   Intelligent-Tiering / expiry rules)
> - Monthly: keep 3
>
> Record which variant was actually configured in the drill evidence (see
> section 6).

**Step 4 — Trigger a manual backup and confirm.**

Trigger one immediate manual backup from the Dokploy UI (exact UI location
varies — look for **Backup now** or a similar action on the backup destination
page). Confirm that an object appears under the `pg/` prefix in the bucket
before proceeding.

**Step 5 — Add GitHub Actions secrets for the freshness monitor.**

Add these four repository secrets in GitHub → Settings → Secrets → Actions:

| Secret name | Value |
|-------------|-------|
| `S3_BACKUP_ENDPOINT` | S3 endpoint URL (e.g. `https://<account>.r2.cloudflarestorage.com`) |
| `S3_BACKUP_BUCKET` | `ukip-backups` |
| `S3_BACKUP_RO_ACCESS_KEY_ID` | Read-only access key ID from Step 1 |
| `S3_BACKUP_RO_SECRET_ACCESS_KEY` | Read-only secret key from Step 1 |

---

## 4. Continuous verification

`.github/workflows/backup-freshness.yml` (added separately as Task 9 of
EPIC-018) runs daily at **07:00 UTC** — four hours after the scheduled backup
window. It lists objects under `pg/` using the read-only credentials and **fails
the workflow run if the most-recent object is older than 26 hours.**

A red run means the nightly backup either did not execute or did not upload
successfully. Triage in this order:

1. **Check Dokploy backup logs.** In the Dokploy UI, open the PostgreSQL service
   → Backups → recent run history. Look for errors (disk full, S3 auth failure,
   pg_dump timeout).
2. **Check bucket credentials.** Confirm the write credentials have not been
   rotated or expired. Re-enter them in Dokploy if needed.
3. **Check VPS disk space.** A full `/var` or temp partition causes pg_dump to
   fail silently or mid-write. Free space and retry.
4. **If the backup genuinely missed:** trigger a manual backup immediately from
   the Dokploy UI, confirm the object appears in the bucket, then investigate
   why the scheduled run failed before re-enabling the schedule.

---

## 5. Restore drill procedure

### Terminal constraints (read before running any command)

Dokploy's web terminal attaches **inside the running container** — there is no
Docker CLI, no compose wrapper, and no host shell. The same constraints
documented in `SECRETS_ROTATION_RUNBOOK.md` apply here:

- **Use single-line commands only.** Paste mangles multiline input in the
  Dokploy terminal.
- **No `\` line continuations, no heredocs, no multiline pipes** (split complex
  pipelines into intermediate files in `/tmp`).
- For PostgreSQL commands (`psql`, `createdb`, `pg_restore`), open a terminal on
  the **postgres container** (or use `psql` from the backend container if the
  postgres client is installed). The postgres container has the pg client tools.
- For Python decrypt probes, open a terminal on the **backend container**
  (`ukip-backend`).

### Drill steps

**Step 1 — Identify and download the backup.**

From your workstation (or the VPS host if you have shell access), use the AWS
CLI or an S3-compatible client to list and download the latest object:

```bash
aws s3 ls s3://ukip-backups/pg/ --endpoint-url https://<account>.r2.cloudflarestorage.com --recursive | sort | tail -5
```

Note the key and timestamp of the most-recent object — this is the **recovery
point**. Download it:

```bash
aws s3 cp s3://ukip-backups/pg/<filename> /tmp/ukip_restore.dump --endpoint-url https://<account>.r2.cloudflarestorage.com
```

Record the backup timestamp and compute the recovery-point age (now − backup
timestamp). This must be ≤ 24 hours to satisfy RPO.

**Step 2 — Create a scratch database.**

Open a terminal on the **postgres container**. Create the drill database with a
single-line command:

```bash
createdb -U postgres ukip_drill
```

Or via psql if `createdb` is not in PATH:

```bash
psql -U postgres -c "CREATE DATABASE ukip_drill;"
```

**Step 3 — Restore the dump.**

Dokploy uses pg_dump to create backups. Determine the dump format from the file
extension or header, then restore with the matching tool.

Plain SQL dump (`.sql` file):

```bash
psql -U postgres -d ukip_drill -f /tmp/ukip_restore.dump
```

Custom-format dump (`.dump` / `.pgdump` file, default for Dokploy):

```bash
pg_restore -U postgres -d ukip_drill /tmp/ukip_restore.dump
```

Record the start and end time of the restore. The elapsed restore time counts
toward the 4-hour RTO.

**Step 4 — Verify schema version.**

Confirm the restored database is at the expected Alembic migration head. Run on
the postgres container:

```bash
psql -U postgres -d ukip_drill -c "SELECT version_num FROM alembic_version;"
```

Compare against production:

```bash
psql -U postgres -d <prod_db_name> -c "SELECT version_num FROM alembic_version;"
```

Both must match. A mismatch means the backup is from a database at a different
schema revision than the current codebase — document the finding and do not
promote to production without running `alembic upgrade head` against `ukip_drill`
first.

**Step 5 — Row-count spot check.**

Spot-check key tables against production to confirm data volume is plausible.
Run each pair (drill vs production) on the postgres container:

```bash
psql -U postgres -d ukip_drill -c "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM raw_entities; SELECT COUNT(*) FROM authority_records; SELECT COUNT(*) FROM organizations;"
```

```bash
psql -U postgres -d <prod_db_name> -c "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM raw_entities; SELECT COUNT(*) FROM authority_records; SELECT COUNT(*) FROM organizations;"
```

Record both sets of counts in the drill report (section 6). Significant
divergence (>5% on stable tables) should be investigated before declaring the
drill a pass.

**Step 6 — Decrypt probe (data-integrity test).**

This is the definitive test that the backup contains usable encrypted data. Open
a terminal on the **backend container** (`ukip-backend`).

Point the backend at the drill database by writing a one-liner probe script to
`/tmp`. The pattern mirrors the one in `SECRETS_ROTATION_RUNBOOK.md` (write to
file, then run — avoids paste-mangling of multiline input):

```bash
printf 'from backend.database import SessionLocal\nfrom backend import models\nfrom backend.encryption import decrypt_value\ndb = SessionLocal()\nfails = 0\nfor ai in db.query(models.AIIntegration).all():\n try: decrypt_value(ai.api_key)\n except Exception as e: print("FAIL AIIntegration", ai.id, e); fails += 1\nfor s in db.query(models.StoreConnection).all():\n for f in ["api_key","api_secret","access_token"]:\n  v = getattr(s, f, None)\n  if v:\n   try: decrypt_value(v)\n   except Exception as e: print("FAIL Store", s.id, f, e); fails += 1\nprint("decrypt_probe failures:", fails)\ndb.close()\n' > /tmp/probe.py && DATABASE_URL=postgresql://postgres@<postgres-host>/ukip_drill python /tmp/probe.py
```

Replace `<postgres-host>` with the postgres container hostname visible from the
backend container (e.g. `ukip-postgres` or the Dokploy-assigned hostname).

Expected output: `decrypt_probe failures: 0`

Any non-zero failure count means at least one encrypted credential in the backup
cannot be decrypted with the current `ENCRYPTION_KEY`. Investigate before using
this backup for production recovery (see `SECRETS_ROTATION_RUNBOOK.md` §1 if an
`ENCRYPTION_KEY` rotation is suspected).

**Step 7 — Record elapsed time vs RTO.**

Note the wall-clock time from the start of Step 1 to the end of Step 6.
This is the drill's measured **time-to-usable-data**. It must be under 4 hours.
If it exceeds 4 hours, file a follow-up issue to reduce restore time (larger
instance type, pg_restore parallelism, pre-staged download, etc.).

**Step 8 — Drop the drill database.**

Clean up on the postgres container:

```bash
psql -U postgres -c "DROP DATABASE ukip_drill;"
```

---

## 6. Drill report template

Copy this block into a new file under `docs/operating/evidence/` named
`drill-YYYY-MM-DD.md` and fill it in immediately after each drill.

```markdown
# Backup & Restore Drill — YYYY-MM-DD

| Field | Value |
|-------|-------|
| Date | YYYY-MM-DD |
| Operator | <name / GitHub handle> |
| Backup object key | `pg/<filename>` |
| Backup object timestamp (UTC) | YYYY-MM-DD HH:MM |
| Recovery point age at drill start | HH:MM (must be ≤ 24h for RPO pass) |

## Step timings

| Step | Start (UTC) | End (UTC) | Elapsed |
|------|-------------|-----------|---------|
| 1 — Identify + download | | | |
| 2 — Create ukip_drill | | | |
| 3 — Restore dump | | | |
| 4 — Verify schema version | | | |
| 5 — Row-count check | | | |
| 6 — Decrypt probe | | | |
| **Total (steps 1–6)** | | | **HH:MM (≤ 4h RTO)** |

## Row counts

| Table | Production | ukip_drill | Delta |
|-------|-----------|------------|-------|
| users | | | |
| raw_entities | | | |
| authority_records | | | |
| organizations | | | |

## Schema version

| DB | alembic_version |
|----|-----------------|
| Production | |
| ukip_drill | |
| Match | YES / NO |

## Decrypt probe output

```
(paste full output here)
```

## Retention configuration (first drill only)

Describe what was actually configured:
- Dokploy retention setting: keep last N = ___
- Bucket lifecycle rules configured: YES / NO (describe)

## ukip_static_data volume review (first drill only)

- Contents inspected: YES / NO
- Non-regenerable state found: YES / NO
- Finding: ___
- Follow-up issue opened: YES / NO / N/A

## Pass / Fail

| Criterion | Result |
|-----------|--------|
| RPO ≤ 24h (recovery point age) | PASS / FAIL |
| RTO ≤ 4h (total elapsed time) | PASS / FAIL |
| Schema version match | PASS / FAIL |
| Decrypt probe failures = 0 | PASS / FAIL |
| **Overall** | **PASS / FAIL** |

## Findings and follow-ups

- (list any deviations, failures, or improvement items)
```

---

## 7. Cadence

| Trigger | Action |
|---------|--------|
| Quarterly (minimum) | Full drill per section 5; file report in `docs/operating/evidence/` |
| After major schema change | Full drill to confirm the new migration head restores cleanly |
| After topology change (new Dokploy version, storage migration, new postgres major version) | Full drill |
| After any restore used in a real incident | Post-incident drill with lessons-learned addendum |

**Next drill due:** 3 months after the first drill is completed and filed.

The drill report doubles as audit evidence that the RTO/RPO commitments are
tested and achievable. Keep all evidence files in `docs/operating/evidence/`
and commit them to `main`.
