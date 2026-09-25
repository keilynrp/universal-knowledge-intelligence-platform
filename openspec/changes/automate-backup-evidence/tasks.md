# Tasks — automatic backup evidence

TDD throughout. Sections 1 and 2 are independent and can ship as one PR or two.
Section 4 is operator work and is what actually turns the automation on.

## 1. Backend ingestion

- [x] 1.1 `parse_evidence_document` in `backend/backup_assurance.py`: pure, with
      every rejection rule in design.md Decision 3, each a test (oversized file
      read no further, malformed, missing or unknown key, wrong schema, other
      environment, bad scope, bad digest, non-positive size, future or stale
      `completed_at`, non-boolean `gzip_ok` for database).
- [x] 1.2 `ingest_backup_evidence(db, directory, environment, now)`: regular
      `*.json` files only, no symlinks, no subdirectories. Idempotent against
      *any* existing `backup` event of the same environment and scope, manual
      ones included, where backup ids match when equal or when one ends with
      `/` + the other (design.md Decision 3). `gzip_ok: false` → `failed`.
- [x] 1.3 Tests: a new document is recorded once across two runs; a manual
      record of the same backup suppresses it; one malformed plus one valid
      records the valid one; a recorded document makes `backup_freshness`
      non-critical.
- [x] 1.4 Call it at the start of `ops_monitor.run_once`, before the checks; a
      failure in ingestion is logged and never fails the cycle.
- [x] 1.5 `UKIP_BACKUP_EVIDENCE_DIR` (default `/run/ukip-signals/backup-evidence`),
      declared in `docker-compose.prod.yml` and `.env.example`. A variable the
      code reads but prod compose does not declare is one that does nothing.

## 2. Host recorder

- [x] 2.1 `scripts/ukip-backup-evidence-recorder.sh`, modelled on the
      reachability probe (runner selection, `EnvironmentFile`, no credential
      output), per design.md Decision 4.
- [x] 2.2 Tests through `subprocess` with a stub runner, as
      `test_backup_provider_reachability_file.py` does: the document written
      matches the schema the backend accepts (round-trip through
      `parse_evidence_document`); an interrupted stream writes nothing; a
      corrupt gzip gives `gzip_ok: false`; an existing document is not
      rewritten; old documents are pruned; no credential appears in output.

## 3. Documentation

- [x] 3.1 Runbook §4 and §5a: the automatic path, with the manual one as the
      fallback. §13.4: replace "remains manual … until a least-privilege
      credential exists" with the decision and its trust boundary.
- [x] 3.2 Runbook: the systemd service and timer (hourly) and the
      `EnvironmentFile` for the new credential, next to the probe's.
- [x] 3.3 ER-BCP-001 evidence notes: automatic cycles are evidence of equal
      weight for freshness (owner decision 3, #370); maturity still depends
      on the restore drill.

## Deviations from design.md, found while implementing

- The parser and ingestion live in their own module, `backend/backup_evidence.py`,
  not in `backup_assurance.py`: they are tested apart, and that file already
  holds the reachability reader and the freshness rules.
- The recorder downloads the object once into a private temporary directory
  instead of piping it through `tee`. In bash a process substitution's exit
  status cannot be relied on, and the temporary file lets it compare the bytes
  received with the size the listing reports: a download that exits 0 but is
  short writes no document either.

## 4. Operator actions (not code)

- [ ] 4.0 Check how the manual cycles recorded `backup_id` in production
      (`GET /ops/backups?environment=production`): full key or relative to
      the prefix. Suffix matching covers both; this confirms it.
- [ ] 4.1 Create the read-only credential: `ListBucket` + `GetObject` on the
      backup prefix only.
- [ ] 4.2 Install the recorder and its timer on the production host.
- [ ] 4.3 Confirm the first automatic cycle appears in `GET /ops/backups` with
      operator `system:backup-recorder`, and that `backup_freshness` stays `ok`
      the following day without manual recording. Then close #370.
