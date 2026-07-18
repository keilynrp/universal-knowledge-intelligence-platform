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

## 3. quality.low (DEFERRED — needs threshold design)

- [ ] 3.1 Decide configurable threshold + downward-crossing semantics (product).
- [ ] 3.2 Emit `quality.low` from `quality_scorer.py` on threshold cross.
- [ ] 3.3 Tests incl. no-spam-on-recompute.

## 4. Cleanup + verification

- [ ] 4.1 Resolve `pull`/`scheduled_pull` bell mismatch (write AuditLog or drop dead icons).
- [ ] 4.2 E2E test per event (mocked sink → assert payload shape).
- [ ] 4.3 Docs (notifications runbook) + confirm SMTP/encryption env vars in prod compose.
- [ ] 4.4 Full backend suite green (`pytest backend/tests/`).
