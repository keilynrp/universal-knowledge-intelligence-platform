# Notifications Runbook

UKIP has three notification subsystems. This document describes what each one
does, which events drive it, how to configure it, and how to verify delivery.

## Subsystems at a glance

| Subsystem | Transport | Audience | Source of truth |
|---|---|---|---|
| **Notification Center** (bell) | In-app, polled every 60s | Logged-in users | `AuditLog` |
| **Email** | SMTP | A single configured recipient | `NotificationSettings` |
| **Alert channels** | Slack / Teams / Discord / generic webhook | Ops/teams that subscribe | `AlertChannel` |

All outbound delivery goes through a single fan-out, `emit_event` /
`emit_outbound` (`backend/notifications/emit.py`), called at each domain event
site. Delivery is **inline fire-and-forget** (a short-lived daemon thread with
its own DB session); it never blocks the request and never raises. A failed
Slack POST or SMTP send is logged and dropped — there is no durable retry.

```
domain event ──► emit_event(action, payload)
                   ├─ AuditLog        → bell / notification center
                   ├─ Webhooks        → customer-registered outbound hooks
                   ├─ Alert channels  → Slack/Teams/Discord/webhook (subscribed)
                   └─ Email           → SMTP, gated by NotificationSettings toggles
```

Two naming schemes bridge here: audit/webhooks use dotted **action** strings
(`harmonization.apply`, `upload`); alert channels use **event ids**
(`harmonization.applied`, `entities.imported`). `resolve_alert_event()` maps
between them.

## Event catalogue (alert channels)

Subscribe a channel to any of these (`GET /alert-channels/events` lists them):

| Event id | Fires when | Emit site |
|---|---|---|
| `entities.imported` | A file upload or store pull adds entities | ingest upload, manual store pull |
| `harmonization.applied` | Harmonization step(s) applied | `/harmonization/apply*` |
| `enrichment.completed` | A background enrichment pass drains the queue | enrichment worker (drain edge) |
| `quality.low` | A domain's avg quality score crosses **down** through the threshold | `/entities/quality/compute` |
| `report.sent` | A scheduled report is delivered | scheduled reports |
| `report.failed` | A scheduled report delivery fails | scheduled reports |
| `import.scheduled` | A scheduled store import completes | scheduled imports |
| `disambiguation.resolved` | Bulk normalization rules are saved for a cluster | `/rules/bulk` |
| `ops.check_failed` | Operational checks report a degraded/critical state | `/ops/checks/run?notify=true` |

`quality.low` uses a **downward-crossing** trigger: it fires only when a
domain's average goes from at/above the threshold to below it, so a rescore that
degrades a domain notifies once — not on every recompute while already low.

## Email

Two operational emails are gated by per-preference toggles in
`NotificationSettings` (Settings → Notifications):

| Toggle | Sends when |
|---|---|
| `notify_on_authority_confirm` | An authority record is confirmed |
| `notify_on_enrichment_batch` | A background enrichment pass completes |

Email also backs the **test message** and **scheduled report** attachments.
Nothing sends unless `enabled` is on **and** SMTP host/sender/recipient are set.

## Configuration

### SMTP (email)

Set in the app: **Settings → Notifications** — SMTP host/port/user/password,
sender, recipient, and the `enabled` + per-event toggles. The password is stored
Fernet-encrypted (needs `ENCRYPTION_KEY`). Use **Send test** to confirm delivery
before enabling operational alerts.

### Alert channels

**Settings → Alert Channels** (admin) — add a channel (Slack/Teams/Discord/
generic), paste its inbound webhook URL (stored encrypted), and tick the events
it should receive. Use the per-channel **test** to confirm the webhook works.

### Environment variables

| Var | Default | Purpose |
|---|---|---|
| `UKIP_QUALITY_LOW_THRESHOLD` | `60` | Domain avg quality-score threshold (percent, 0–100) for the `quality.low` alert |
| `ENCRYPTION_KEY` | — | Fernet key; required to store/read SMTP password and channel URLs |

`UKIP_QUALITY_LOW_THRESHOLD` is declared in `docker-compose.prod.yml`. Any code
env-var read **must** be declared there or the deployed container never sees it.

## Verifying delivery (post-deploy)

Automated tests mock the network, so after deploy confirm real delivery once:

1. **Email:** configure SMTP in Settings → Notifications, click **Send test**.
2. **Alert channel:** add a Slack channel, click its **test** button.
3. **A real event:** upload a small file (fires `entities.imported`) or run a
   scheduled report (`report.sent`) and confirm the subscribed channel receives
   it. Effective flag/threshold state is visible at `/health` (`features`).

## Troubleshooting

- **Nothing arrives on a channel:** confirm the channel is active, subscribed to
  that specific event id, and the webhook URL is valid (per-channel test). Check
  backend logs for `alert-channel dispatch failed` / `Alert delivery failed`.
- **No email:** confirm `enabled` is on, SMTP host/sender/recipient are set, and
  the relevant toggle is on. Check logs for `email dispatch failed`.
- **quality.low never fires:** it only fires on a *downward crossing*; a domain
  already below the threshold does not re-fire. Lower/raise
  `UKIP_QUALITY_LOW_THRESHOLD` as needed and re-run `/entities/quality/compute`.
- **Bell shows nothing for scheduled imports/pulls:** these write an `AuditLog`
  on success; if absent, the run likely errored before completion — check the
  `SyncLog` row for that store.
