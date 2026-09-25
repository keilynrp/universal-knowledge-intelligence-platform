# Design — automatic backup evidence

## Decision 1: a signal file, not a credential (owner, #370)

The host already hands the backend a signal without giving it a credential:
`scripts/ukip-backup-reachability-probe.sh` writes a two-field JSON document
into `/var/lib/ukip/signals`, mounted read-only into the container at
`/run/ukip-signals`, and `resolve_provider_reachability` reads it with strict
validation. Evidence uses the same channel, one document per observed backup:

```
/var/lib/ukip/signals/backup-evidence/<scope>-<object-timestamp>.json
```

Written atomically (temp file in the same directory, then `mv`), so the backend
never reads half a document.

**Rejected:** a narrow `backup:evidence` API scope. It would work, but it adds
a network-exposed credential and a new scope that every future `/ops` change
has to reason about. The signal directory's boundary (root on the host) is one
the system already trusts with the database itself.

## Decision 2: the document

```json
{
  "schema_version": 1,
  "recorder": "ukip-backup-evidence-recorder/1",
  "observed_at": "2026-09-25T03:12:40Z",
  "environment": "production",
  "scope": "database",
  "backup_id": "pg/2026-09-25T03-00-00-076Z.sql.gz",
  "completed_at": "2026-09-25T03:00:41Z",
  "size_bytes": 5968925,
  "sha256": "<64 hex>",
  "gzip_ok": true,
  "provider": "s3-compatible"
}
```

- `backup_id` is the object key **relative to the backup prefix**. It carries
  no bucket and no prefix, so the document has no path or key material, like
  the reachability document.
- `completed_at` is the object's `LastModified`, which is what the manual
  cycles record.
- `gzip_ok` is `null` for scopes that are not gzip dumps.

## Decision 3: ingestion is strict and idempotent

In `backend/backup_assurance.py`, pure and without a database, as the
reachability reader is:

```
parse_evidence_document(raw: bytes, *, environment: str) -> EvidenceDocument | Rejection
```

It rejects, and never raises into the monitor, when:

- the file is over 8 KB (read no further);
- the JSON is malformed, a key is missing or an unknown key is present;
- `schema_version` is not 1;
- `environment` differs from the backend's `UKIP_BACKUP_ENVIRONMENT` (a
  document cannot write evidence into another environment);
- `scope` is not `database` or `volume`;
- `sha256` is not 64 lowercase hex characters;
- `size_bytes` is negative or zero;
- `completed_at` is in the future or older than 14 days;
- `gzip_ok` is not a boolean for `database`.

A rejected document is logged once (by file name and reason, never content)
and skipped. The next cycle sees it again, so a fixed recorder's next document
is picked up without anyone touching the backend.

Then `ingest_backup_evidence(db, directory, environment, now)`:

1. lists regular files matching `*.json` (no symlinks followed, no
   subdirectories);
2. parses each one;
3. skips it if a `backup` event already exists for the same environment,
   scope and backup, whoever recorded it. Two backup ids name the same backup
   when they are equal, or when one ends with `/` followed by the other. The
   manual cycles' evidence notes cite objects with a leading path
   (`ukip-dbukip-eqmmhw/pg/…sql.gz`), and whether the recorded events carry
   that path or the prefix-relative key cannot be seen from the repository.
   Object names carry a millisecond timestamp, so suffix matching cannot
   conflate two backups of one scope;
4. otherwise calls `record_event`:
   - `status` is `completed`, or `failed` when `gzip_ok` is false;
   - `integrity_ref` is `sha256:<hex>`;
   - `operator` is `system:backup-recorder`;
   - `evidence` holds `{"method": "sha256-stream+gzip-t", "recorder": …,
     "observed_at": …, "source": "host-signal"}`.

**Idempotency is checked in the application, not by a unique index.**
`backup_assurance_events` is append-only (update, delete and truncate are
refused at the database, #365) and may already hold manually recorded
duplicates from before this change, so adding a unique constraint could fail
the migration on real data. Production runs a single uvicorn process with a
single monitor thread, so the check and the insert do not race.

**Where it runs:** at the start of each ops-monitor cycle, before the checks
are evaluated. The freshness check then sees evidence recorded in the same
cycle, with no second scheduler.

## Decision 4: the recorder

`scripts/ukip-backup-evidence-recorder.sh`, modelled on the probe: the same
`UKIP_AWS_RUNNER` (aws or the pinned aws-cli image), the same `EnvironmentFile`
convention, and credentials that are never printed.

For each scope and its prefix, it:

1. lists the newest object;
2. skips it if `backup-evidence/<scope>-<timestamp>.json` already exists (the
   recorder's own idempotency; the backend's is independent);
3. otherwise streams the object once through `tee` into `sha256sum` and, for
   the database scope, `gzip -t`;
4. writes the document atomically.

It prunes its own documents older than 14 days, matching the backend's
acceptance window.

**A failed stream is not evidence.** If `GetObject` fails partway, no document
is written, so a network error cannot produce a `failed` backup. Only a
completed stream whose bytes fail `gzip -t` produces `gzip_ok: false`.

**Timer:** hourly. Idempotency makes the frequency a matter of latency, not
correctness, and an hourly run records a 03:00 backup within an hour.

## Risks

- **Recorder stops running:** no new evidence, so freshness goes `critical` on
  its own, which is the right alarm. The CI listing (`backup-freshness.yml`)
  still shows whether objects exist, so "backup missing" and "recorder dead"
  remain distinguishable.
- **A forged document:** requires write access to `/var/lib/ukip/signals`,
  that is root on the host, who can already write the database directly. The
  strict parser bounds what a malformed document can do.
- **Credential scope creep:** the new credential is `GetObject` on the backup
  prefix only. It can read backups, which host root already can. It cannot
  write, delete or list outside the prefix.
