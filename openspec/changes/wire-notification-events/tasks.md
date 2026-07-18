## 0. Foundation — unified emitter (TDD)

- [x] 0.1 Add `backend/notifications/emit.py` with `emit_event()` fan-out.
- [x] 0.2 Add `_ACTION_TO_ALERT_EVENT` mapping + pass-through for `ALL_EVENT_IDS`.
- [x] 0.3 Add `_run_alert_dispatch()` (thread + fresh session, calls `dispatch_event`).
- [x] 0.4 Add `_run_email_dispatch()` gated by `NotificationSettings` toggles + subject/body formatter.
- [x] 0.5 Unit tests: fan-out hits all sinks; mapping covers every `ALL_EVENT_IDS`; email gating on/off; never raises when a sink fails. (`test_notification_emit.py`, 12 tests)
- [x] 0.6 Confirm existing sprint43/56/81-82/104 suites still green. (95 passed)

## 1. High-value / low-effort sites (already instrumented)

- [x] 1.1 `entities.imported` — `emit_outbound` at both ingest upload paths (science + CSV).
- [x] 1.2 `harmonization.applied` — `emit_outbound` at apply + apply-all.
- [x] 1.3 `report.sent` — `emit_outbound` at scheduled_reports success.
- [x] 1.4 `report.failed` — `emit_outbound` at scheduled_reports error path.
- [x] 1.5 `import.scheduled` — `emit_outbound("scheduled_pull")` at scheduled_imports success.
- [x] 1.6 email `notify_on_authority_confirm` — `emit_outbound` at authority confirm.
- [~] 1.7 Fan-out logic covered by emit unit tests; existing router suites guard wiring. (dedicated per-endpoint integration tests: follow-up)

## 2. Medium-effort completion hooks

- [x] 2.1 Enrichment batch-completion hook = drain edge in `background_enrichment_worker`.
      Pure `_next_batch_state()` fires once per queue-drain (not per entity).
- [x] 2.2 `enrichment.completed` alert + `notify_on_enrichment_batch` email via
      `_emit_enrichment_batch_complete()` on the drain edge.
- [x] 2.3 `disambiguation.resolved` — `emit_outbound` at `create_rules_bulk` (`/rules/bulk`).
- [x] 2.4 Tests: emit unit tests (13) + worker batch-edge tests (`TestBatchCompletion`, 4).

## 3. quality.low

- [x] 3.1 Configurable threshold `UKIP_QUALITY_LOW_THRESHOLD` (percent, default 60) +
      downward-crossing semantics (`quality_low_crossings`, pure).
- [x] 3.2 Emit `quality.low` per domain from `/entities/quality/compute` (before/after
      domain averages around `compute_all`).
- [x] 3.3 Tests: threshold config, crossing logic (no-fire when already-below /
      staying-above / no baseline / at-threshold), domain averaging. (`test_quality_low_alert.py`, 9)

## 4. Cleanup + verification

- [x] 4.1 REVERTED — attempted to drop `pull`/`scheduled_pull` bell mappings, but
      `test_sprint56` asserts they are intended bell actions ("Scheduled import completed"/🗓️).
      Restored them; bell vocabulary unchanged. (Making scheduled imports actually WRITE a
      bell AuditLog is a separate noise/product call — left as-is; they fire `import.scheduled`
      on alert channels via `emit_outbound`.)
- [ ] 4.2 E2E test per event (mocked sink → assert payload shape). (follow-up)
- [ ] 4.3 Docs (notifications runbook) + confirm SMTP/encryption env vars in prod compose. (follow-up)
- [x] 4.4 Full backend suite: 3188 passed / 7 skipped (1 transient failure from the 4.1
      cleanup, fixed by the revert; sprint56 re-run green).
