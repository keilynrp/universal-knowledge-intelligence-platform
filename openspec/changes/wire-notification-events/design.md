## Context

Four notification sinks exist today, wired inconsistently:

| Sink | Mechanism | Wired? |
|---|---|---|
| Bell / center | `AuditLog` via `_audit(db, action, ...)` | ✅ everywhere |
| Webhooks | `_dispatch_webhook(action, payload, db_factory)` | ✅ at instrumented sites |
| Alert channels | `dispatch_event(db, event, message, details)` | ❌ only `ops.check_failed` |
| Email (SMTP) | `send_notification(settings, subject, body)` | ❌ only test button |

Two taxonomies exist. Audit/webhooks use dotted **action** strings
(`harmonization.apply`, `upload`, `authority.confirm`, `entity.bulk_delete`,
`entity.merge`). Alert channels use the `ALL_EVENTS` **event ids**
(`harmonization.applied`, `entities.imported`, `enrichment.completed`, …). They
overlap in meaning but not in spelling.

## Decision

Add `backend/notifications/emit.py` with a single fan-out entry point. It keeps
the audit write in the caller's transaction (as today) and fires the other three
sinks fire-and-forget.

```python
def emit_event(
    db: Session,
    action: str,
    payload: dict,
    db_factory,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    user_id: int | None = None,
    alert_message: str | None = None,
) -> None:
    # 1. bell/center — in the caller's txn (caller still commits)
    _audit(db, action, entity_type=entity_type, entity_id=entity_id,
           user_id=user_id, details=payload)
    # 2. webhooks — existing fire-and-forget
    _dispatch_webhook(action, payload, db_factory)
    # 3. alert channels — new; maps action → alert_event_id, own thread+session
    _dispatch_alert_channels(action, payload, db_factory, alert_message)
    # 4. email — new; gated by NotificationSettings toggles, own thread+session
    _dispatch_email(action, payload, db_factory)
```

### Action → alert-event mapping

```python
_ACTION_TO_ALERT_EVENT: dict[str, str] = {
    "upload":              "entities.imported",
    "scheduled_pull":      "import.scheduled",
    "harmonization.apply": "harmonization.applied",
    # report.sent / report.failed / enrichment.completed / disambiguation.resolved
    # are emitted with the alert-event id directly as `action` (no audit action).
}
```

Events with no natural audit action (report.*, enrichment.completed,
disambiguation.resolved) are emitted by passing the alert-event id itself as
`action`; `_dispatch_alert_channels` treats an id already in `ALL_EVENT_IDS` as
a pass-through. This keeps one code path.

### Email gating

`_dispatch_email` loads the singleton `NotificationSettings` and only sends when
`enabled` **and** the relevant toggle is on:

```python
_ACTION_TO_EMAIL_TOGGLE = {
    "authority.confirm":     "notify_on_authority_confirm",
    "enrichment.completed":  "notify_on_enrichment_batch",
}
```

If the toggle attr is absent or false → no email. Subject/body are derived from
the action + payload via a small formatter.

### Why inline fire-and-forget (not the job queue)

`_dispatch_webhook` already uses `threading.Thread(daemon=True)` + a fresh
session from `db_factory`. Matching it keeps the change self-contained, avoids
coupling to the in-flight External Background Job Runtime rollout, and preserves
"never block the request, never raise". Each async sink swallows and logs its
own exceptions and updates channel/webhook stats exactly as the existing code
does.

## Risks / trade-offs

- **Duplicate delivery under retries**: inline fire-and-forget has no retry; a
  failed Slack POST is logged and dropped (same as webhooks today). Acceptable
  for notifications; durable delivery is a future job-queue concern.
- **Taxonomy drift**: the mapping table is the single source of truth; a unit
  test asserts every `ALL_EVENT_IDS` member is either mapped-from an action or
  pass-through, so a new event can't silently go unwired.
- **Thread/session churn**: three short-lived threads per emit. Emit sites are
  low-frequency (imports, reports, batch completions), so this is negligible.

## Migration / rollout

Pure additive at call sites: replacing `_audit(...)` + `_dispatch_webhook(...)`
with `emit_event(...)` preserves existing bell + webhook behavior (same action
strings, same payloads) while adding the two new sinks. No schema change; no
migration. Existing sprint43/56/81-82/104 tests must stay green.
