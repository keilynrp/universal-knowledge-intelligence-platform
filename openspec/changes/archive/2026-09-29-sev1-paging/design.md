# Design — SEV1 paging

## Decision 1: Pushover as a channel type, not a side path

Alert channels already exist as database rows (`AlertChannel`: type, encrypted
destination, subscribed events), and `dispatch_event` fans an event out to every
active channel subscribed to it. Pushover is a fifth `type`. It is configured
where the others are, it is covered by the `ops_alerting` check (which warns
when nothing is subscribed to `ops.check_failed`), and it needs no new
configuration surface.

**Credentials:** Pushover needs an application token and a user key, not a URL.
They are stored as one JSON object, `{"token": …, "user": …}`, encrypted with
the same Fernet key into the existing `webhook_url` column. The column name no
longer describes every row, but a new column would need a migration and a
second encryption path for the same kind of secret. Validation on create and
update requires both keys and the 30-character alphanumeric shape Pushover
issues. The API never returns either value, as it never returns a webhook URL.

**Delivery:** `POST https://api.pushover.net/1/messages.json`, form-encoded, with
the same 10 s timeout and the same never-raise contract as the other senders.
The title is the event label, the message is the alert text, and the details
are truncated to Pushover's 1024-character limit.

## Decision 2: severity is derived from the checks, in one place

`backend/ops_monitor.py` already builds the alert details (`status`,
`failing_checks`, counts). It adds:

```
severity(report) -> "page" | "urgent" | "info"

  page    a check in PAGE_CHECKS   = {database, migrations}          is critical
  urgent  a check in URGENT_CHECKS = {backup_freshness, secrets}      is critical
  info    otherwise (warnings, recovery, reminders)
```

The two sets are the owner's decision on #377, kept as constants next to the
alert policy with a test that pins them. Changing who gets woken up is then a
one-line, reviewed change.

Mapping to Pushover:

| Severity | Priority | Behaviour |
|---|---|---|
| `page` | 2 (emergency) | breaks through DND, `retry=60`, `expire=3600` |
| `urgent` | 1 (high) | bypasses Pushover's quiet hours but not the phone's DND |
| `info` | 0 | normal |

Non-Pushover channels ignore the field, except that the message gains a
`[PAGE]` or `[URGENT]` prefix so Slack readers see the same classification.

## Decision 3: page once per incident

`alert_kind` already distinguishes degraded, escalated, changed, reminder and
recovered. Paging adds one rule on top: severity `page` is used only when the
set of critical `PAGE_CHECKS` **grows** relative to the previous observation.
A reminder or a change among other checks, during an incident that has already
paged, is sent as `info`. An emergency repeats every minute until
acknowledged, so paging again every cycle would stack pages rather than
escalate.

The previous observation already carries the failing set; it gains the critical
set. This stays pure and testable, like `alert_kind`.

## Decision 4: the dead man's switch

In-app paging cannot report its own death. `UKIP_OPS_HEARTBEAT_URL` holds a
Healthchecks.io ping URL. At the end of every monitor cycle:

- the evaluation ran (whatever the status): `GET <url>`;
- the evaluation itself raised: `GET <url>/fail`.

Both use a 5 s timeout and never raise, and the URL is never logged, because it
is a capability. The Healthchecks.io check is configured with period equal to
the monitor interval and a grace of two intervals, and its Pushover
integration set to emergency priority. If the pings stop, for whatever reason,
Healthchecks.io pages.

This deliberately does not ping on `ok` only. A red but running monitor is
already paging through Pushover. Healthchecks.io watches that the monitor is
alive, not that production is healthy.

## Decision 5: a test that proves it wakes you

`POST /alert-channels/{id}/test` for a Pushover channel sends priority 2 with
`retry=30` and `expire=60`: one real emergency, which stops by itself after a
minute. #377 requires a testable path ("an unexercised paging path is the same
gap with more configuration"), and a 200 from the API proves nothing about the
phone. The runbook asks for this test with the phone in Do Not Disturb.

## Risks

- **Pushover down:** Slack still carries the alert, as today, so it degrades to
  the current state, not below it.
- **Healthchecks.io down:** it cannot page on silence. The in-app path is
  unaffected, so it degrades to "in-app paging only".
- **Alert fatigue:** only two checks page. If they flap, the page-once rule
  holds per incident, and the fix belongs in the check, not in muting it.
- **Credential exposure:** the Pushover token can send notifications to one
  user, nothing else. The heartbeat URL can only mark a check up or down.
  Neither is logged; both are rotated in their own dashboards.
