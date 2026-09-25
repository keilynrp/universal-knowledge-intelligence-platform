# Record backup evidence automatically, without an application credential

> **Closes:** #370 (ER-BCP-001).
> **Owner decisions:** recorded on #370, 2026-09-25: a host signal file rather
> than an API credential; a new read-only List+Get storage credential; equal
> weight for freshness.

## Why

Scheduled detection (#369) reported `backup_freshness: critical` on its first
evaluation, and the backups were fine. The provider held the dumps of 2026-09-21
and 2026-09-22, but nobody had *recorded* them as `backup_assurance_events`.
Freshness is measured against recorded evidence, which is correct: the control
must not trust what nobody recorded. Recording, though, is manual by design
(runbook §13.4), so the status goes `critical` every day a person does not
record the cycle. Now that detection alerts on it, a manual step has become a
permanently red alarm, and people learn to ignore alarms like that.

It is manual because the only way in was `POST /ops/backups/events`, which
requires an `admin` API key, and holding one in a scheduled job was judged too
broad a trust boundary for "record backup evidence".

## What Changes

- **A recorder on the production host**, beside the reachability probe. It is a
  systemd timer with its own read-only storage credential (`ListBucket` +
  `GetObject`, limited to the backup prefix). For the newest object of each
  scope (`database`, `volume`) it:
  - streams the stored bytes once, computing SHA-256 over exactly what the
    provider holds, never the multipart ETag;
  - runs `gzip -t` for database dumps;
  - writes one evidence document into the signals directory the backend
    already mounts read-only.
- **The backend ingests those documents itself**, inside the ops monitor it
  already runs. It validates each document strictly, as it does the
  reachability signal, and records a `backup` event with operator
  `system:backup-recorder`. It is idempotent on (environment, scope,
  backup_id), so a retry, a restart or a manual record of the same cycle never
  duplicates evidence. A dump that fails `gzip -t` is recorded as `failed`, not
  skipped.
- **No application credential exists for this at all.** There is no new API
  scope and no key in a job. The trust boundary is root on the host, which
  already holds the database.
- **The evidence standard is the manual cycles' standard**, so an automatic
  cycle weighs the same for freshness. ER-BCP-001 maturity keeps depending on
  the restore drill.
- Runbook §4, §5a and §13.4 describe the automatic path and keep the manual one
  as the fallback.

## Non-goals

- Restore drills. They stay human-run and human-recorded.
- A new API scope. Considered and rejected by the owner (#370).
- Moving `backup-freshness.yml` (the CI listing) off its list-only identity.
- Deleting or rewriting any evidence: `backup_assurance_events` stays
  append-only.

## Impact

- New `scripts/ukip-backup-evidence-recorder.sh`, tested through `subprocess`
  with a stub runner, as the probe is.
- New ingestion in `backend/backup_assurance.py` (pure validation) and a call
  from `backend/ops_monitor.py`'s cycle.
- `docker-compose.prod.yml`: nothing new to mount. The signals directory is
  already mounted read-only at `/run/ukip-signals`; one environment variable
  names the evidence subdirectory.
- Runbook, ER-BCP-001 evidence notes.
- **Operator actions, not code:** create the List+Get credential, install the
  timer. Until then nothing changes, and manual recording keeps working.
