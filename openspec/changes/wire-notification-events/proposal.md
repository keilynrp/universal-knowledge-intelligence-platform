## Why

UKIP has three notification subsystems. Only the in-app **Notification Center**
(the bell, backed by `AuditLog`) is wired end-to-end. The two **outbound**
paths are UI/model scaffolding that is never connected to its triggering events:

- **Email "alert preferences"** — the `notify_on_enrichment_batch` and
  `notify_on_authority_confirm` toggles exist in the model, schema, and settings
  UI, but **no operational code reads them**. Toggling them does nothing.
- **Alert channels** (Slack/Teams/Discord/webhook) — the `ALL_EVENTS` catalogue
  advertises **9 subscribable events**, but `dispatch_event()` is called from
  exactly one place (`ops.check_failed`). The other **8 events never fire**, so a
  channel subscribed to "Report delivered" or "Entities imported" receives
  nothing.

Key enabling insight: at every meaningful event site the code **already** calls
`_audit(db, action, ...)` and `_dispatch_webhook(action, ...)` side by side. The
emit sites are already identified and instrumented — the alert-channel and email
sinks are simply missing from those same spots.

## What Changes

- Introduce a single `emit_event()` fan-out that dispatches to all four sinks
  (audit → bell, webhooks, alert channels, email) with one call.
- Add an `action → alert_event_id` mapping to bridge the two existing
  taxonomies (`harmonization.apply` ↔ `harmonization.applied`, `upload` ↔
  `entities.imported`, etc.).
- Gate email sends on the previously-dead settings toggles.
- Replace the existing `_audit` + `_dispatch_webhook` pairs with `emit_event()`
  at each instrumented site, and add emit calls at the currently-uninstrumented
  completion points (report send/fail, scheduled import, enrichment batch,
  disambiguation resolve).
- Delivery is **inline fire-and-forget** (daemon thread + fresh session via
  `db_factory`), matching the current `_dispatch_webhook` pattern. Never blocks
  the request, never raises.

## Non-goals

- `quality.low` alerting — deferred to its own change; it needs a configurable
  threshold and downward-crossing detection, not just wiring (open product
  decision on the threshold).
- Moving delivery onto the PostgreSQL job queue (External Background Job Runtime)
  — explicitly rejected for this change to avoid coupling to that rollout.
- New event types beyond the existing `ALL_EVENTS` catalogue.

## Scope (this delivery)

Phases 0 + 1 + 2. `quality.low` (Phase 3) and cleanup/verification (Phase 4)
tracked here but the threshold design is out of scope for the first cut.

## Event coverage after this change

| Alert event | Emit site | Phase |
|---|---|---|
| `entities.imported` | ingest upload / scheduled import | 1 |
| `harmonization.applied` | harmonization apply | 1 |
| `report.sent` | scheduled_reports success | 1 |
| `report.failed` | scheduled_reports error | 1 |
| `import.scheduled` | scheduled_imports success | 1 |
| `ops.check_failed` | ops_checks (already wired) | — |
| `enrichment.completed` | enrichment batch completion | 2 |
| `disambiguation.resolved` | disambiguation resolve | 2 |
| `quality.low` | quality_scorer threshold | 3 (deferred) |

| Email toggle | Emit site | Phase |
|---|---|---|
| `notify_on_authority_confirm` | authority_records confirm | 1 |
| `notify_on_enrichment_batch` | enrichment batch completion | 2 |
