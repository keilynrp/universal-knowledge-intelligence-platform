# Page a person for SEV1, and notice when nothing can page

> **Closes:** #377 (ER-IR-001).
> **Owner decisions:** recorded on #377, 2026-09-26: Pushover; emergency
> priority for `database` and `migrations` critical, high priority for
> `backup_freshness` and `secrets` critical; a Healthchecks.io dead man's switch.

## Why

In the first tabletop, detection took **6 h 22 min**, overnight, and came from a
third party. Alerts reach Slack and the container log. Slack respects Do Not
Disturb and does not repeat, so a SEV1 at 03:00 waits until someone looks at
their phone. The 72-hour notification commitment in the DPA is sized around
exactly that delay.

Paging from inside the app is also not enough on its own: whatever takes
production down (the VPS, the container, the monitor thread) takes down the
thing that would send the page. Plan §3 defines SEV1 as "production unusable"
for exactly those cases.

## What Changes

- **Pushover becomes an alert channel type**, beside Slack, Teams, Discord and
  webhook. Its credentials (application token and user key) are stored
  encrypted, like a webhook URL.
- **Ops alerts carry a severity** derived from which checks are critical:
  - `page`: `database` or `migrations` critical (production unusable, SEV1).
    Pushover emergency priority: it breaks through Do Not Disturb and repeats
    every minute until acknowledged.
  - `urgent`: `backup_freshness` or `secrets` critical (SEV2). High priority:
    prominent, but it respects quiet hours.
  - `info`: everything else (warnings, recovery). Normal priority.
  Slack and the other channels receive every alert as before, with the
  severity in the message.
- **It pages once per incident, not every cycle.** A new page fires only when a
  paging check becomes critical that was not before. Pushover repeats until
  acknowledged, and the monitor's reminders stay at `info`.
- **A dead man's switch.** The monitor pings a Healthchecks.io check at the end
  of every cycle, and pings `/fail` when the evaluation itself fails. If the
  pings stop (VPS down, container down, monitor thread dead), Healthchecks.io
  pages through its native Pushover integration. This is the only piece that
  survives production being gone.
- **The test proves it wakes you.** The channel's existing "test" action sends a
  real emergency-priority page with a short expiry, so the operator verifies
  that it breaks through Do Not Disturb on their phone, not just that an HTTP
  call returned 200.

## Non-goals

- Detecting unauthorized access automatically (plan §11 gap 6, anomaly
  detection). This change pages on what the checks can see.
- On-call rotations or escalation to a second person (plan §11 gap 1: one
  person holds every role).
- Cancelling a running emergency on recovery through Pushover's receipt API.
  Recovery is sent as `info`, and the page stops when acknowledged or when it
  expires.

## Impact

- `backend/notifications/alert_sender.py`: a Pushover payload builder that
  posts form fields to `api.pushover.net`, with priority mapped from severity.
- `backend/routers/alert_channels.py`: the `pushover` type, credential
  validation, and an emergency test.
- `backend/ops_monitor.py`: severity in the alert details, page-once logic,
  and the Healthchecks.io ping.
- Frontend alert channel form: the Pushover type with its two fields.
- `docker-compose.prod.yml`: `UKIP_OPS_HEARTBEAT_URL` (the Healthchecks.io ping
  URL, a capability, never logged).
- Plan §4 and §11 gap 2; runbook for installing and testing both halves.
- **Operator actions:** Pushover account and application, a Healthchecks.io
  check with the Pushover integration, and one test of each.
