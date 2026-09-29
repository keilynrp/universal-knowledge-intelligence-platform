# Tasks — SEV1 paging

TDD throughout. Sections 1–3 are backend and can ship as one PR; 4 is the UI;
5 is operator work, and it is what actually closes #377.

## 1. Pushover channel

- [x] 1.1 `pushover` in `_VALID_TYPES` and the create/update patterns; the
      destination is `{"token", "user"}` JSON, validated (both present,
      30-character alphanumeric) and Fernet-encrypted into `webhook_url`.
      Tests: missing key → 422; neither value in any response.
- [x] 1.2 `alert_sender`: Pushover builder and form-encoded delivery, priority
      from `details["severity"]` (2 with `retry=60&expire=3600`, 1, 0), message
      truncated to 1024 characters, never raises. Tests with a stubbed
      `urlopen`: fields, priorities, truncation, a timeout returns False.
- [x] 1.3 The test action sends priority 2 with `retry=30&expire=60` for
      Pushover channels.

## 2. Severity and page-once

- [x] 2.1 `PAGE_CHECKS`, `URGENT_CHECKS` and a pure `severity(report, previous)`
      in `ops_monitor.py`, pinned by a test to the owner's decision.
- [x] 2.2 `Observation` gains the critical-check set; `page` only when critical
      `PAGE_CHECKS` grows. Tests: database down → page; reminder → info;
      migrations joins → page again; only backups critical → urgent; recovery
      → info.
- [x] 2.3 The severity goes into the dispatched details, and non-Pushover
      builders prefix `[PAGE]`/`[URGENT]`.

## 3. Heartbeat

- [x] 3.1 `UKIP_OPS_HEARTBEAT_URL`: ping after every cycle, `/fail` when the
      evaluation raised, 5 s timeout, never raises, never logs the URL.
      Declared in `docker-compose.prod.yml`, `.env.dokploy.example` and
      `.env.example`, and held by a configuration test.
- [x] 3.2 Tests: ok and critical both ping the base URL; a raised evaluation
      pings `/fail`; a timeout does not break the cycle; the URL never appears
      in captured logs.

## 4. UI

- [x] 4.1 The alert channel form offers Pushover with two fields (application
      token, user key) instead of a URL, and explains that "Test" sends a real
      emergency page.

## Notes from implementation

- 5.2 became its own runbook, `docs/operating/PAGING_RUNBOOK.md`, linked from
  plan §4: paging has two independent halves to set up and test, and neither
  belongs in the backup runbook.
- Plan §11 gap 2 is marked "in code", not closed: it closes with 5.3, when
  both paths have woken the phone.

## 5. Docs and operator actions

- [x] 5.1 Plan §4: how paging works and what each severity does. §11 gap 2:
      closed with what remains (no second person, no anomaly detection).
- [x] 5.2 Runbook: create the Pushover application, add the channel subscribed
      to `ops.check_failed`, create the Healthchecks.io check (period = monitor
      interval, grace = 2 intervals, Pushover integration at emergency), set
      `UKIP_OPS_HEARTBEAT_URL`.
- [x] 5.3 **Operator:** test the channel with the phone in Do Not Disturb and
      confirm it rings; stop the backend container and confirm Healthchecks.io
      pages; record both in the tabletop follow-up. Then close #377.
      Both paths woke the operator's phone on 2026-09-29: the Pushover
      channel's test at 21:36 UTC rang through Do Not Disturb, repeated
      and was acknowledged; with the monitor switched off
      (`UKIP_OPS_MONITOR_ENABLED=0`, the app kept serving),
      Healthchecks.io paged after 15 minutes (5-minute period plus
      10-minute grace), again through Do Not Disturb (reported 22:29 UTC).
      Re-enabling the monitor brought the check back up within one cycle.
      The heartbeat test switched the monitor off instead of stopping the
      container: the same silence reaches Healthchecks.io, and the app stayed
      up. Recorded in `INCIDENT_TABLETOP_2026-09-22.md`.
