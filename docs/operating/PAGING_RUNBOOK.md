# Paging Runbook

Sets up and proves the path that wakes a person for a SEV1 (#377, openspec
change `sev1-paging`). Until every step below is done, **nothing pages**: alerts
still reach Slack only, and the incident response plan §11 gap 2 stays open.

In the first tabletop, detection took 6 h 22 min, overnight, and came from a
third party. Slack respects Do Not Disturb and does not repeat. This runbook
replaces "someone will look at their phone" with two independent paths:

| Path | Fires when | Why it is needed |
|---|---|---|
| **Pushover channel** | The ops monitor sees `database` or `migrations` critical (emergency), or `backup_freshness` or `secrets` critical (high) | The app can see its own critical states |
| **Healthchecks.io dead man's switch** | The monitor stops pinging: VPS down, container down, monitor thread dead | Whatever takes production down takes the in-app pager with it |

## 1. Pushover

1. Create a Pushover account and install the app on the on-call phone. On iOS,
   allow **Critical Alerts** for Pushover, or emergency pages will not break
   through Do Not Disturb.
2. Create an application at pushover.net → *Create an Application/API Token*.
   Note the **application token** and your **user key** (both are 30 letters
   and digits).
3. In UKIP, open **Settings → Alerts → Add Channel**:
   - type **Pushover (pages a phone)**;
   - paste the token and the user key (they are stored encrypted and never shown
     again);
   - subscribe it to **Operational check failed** (`ops.check_failed`).

**Test it with the phone in Do Not Disturb.** Press **Test** on the channel. It
sends a real emergency page that repeats every 30 seconds and stops by itself
after a minute. The phone must ring through Do Not Disturb. A green "sent" in
the UI only proves that Pushover accepted the request. The phone ringing is the
test.

## 2. Healthchecks.io

1. Create a check at healthchecks.io: **period** = the monitor interval
   (`UKIP_OPS_MONITOR_INTERVAL_SECONDS`, 5 minutes by default), **grace** =
   10 minutes (two intervals).
2. Under *Integrations*, add **Pushover**, set its priority for "down" to
   **emergency**, and enable it for this check.
3. Copy the check's **ping URL** (`https://hc-ping.com/<uuid>`). It is a
   capability: anyone holding it can mark the check up or down. Set it only in
   Dokploy:

   ```
   UKIP_OPS_HEARTBEAT_URL=https://hc-ping.com/<uuid>
   ```

   Redeploy. Within one interval the check turns green in Healthchecks.io.

**Test it.** Stop the backend container, or set `UKIP_OPS_MONITOR_ENABLED=0` and
redeploy. After period plus grace (about 15 minutes), Healthchecks.io must page
the phone. Start it again, and the check recovers on the next ping.

A failed evaluation inside the monitor pings `/fail`, which Healthchecks.io
treats as down immediately. The in-app path reports it as critical too.

## 3. What pages, and how loudly

| Checks critical | Severity | Pushover | Slack |
|---|---|---|---|
| `database`, `migrations` | `page` | emergency (priority 2): through DND, repeats every 60 s until acknowledged, expires after 1 h | `[PAGE]` prefix |
| `backup_freshness`, `secrets` | `urgent` | high (priority 1): bypasses Pushover quiet hours, not the phone's DND | `[URGENT]` prefix |
| anything else, reminders, recovery | `info` | normal | unchanged |

It pages **once per incident**: again only when another paging check becomes
critical. The emergency keeps repeating until someone acknowledges it in the
Pushover app. Acknowledging stops the repetition. It does not resolve the
incident; follow the incident response plan from §5.

The sets are the owner's decision on #377 and live in
`backend/ops_monitor.py` (`PAGE_CHECKS`, `URGENT_CHECKS`). A test pins them, so
changing who gets woken up is a reviewed change.

## 4. Rotation and removal

- **Pushover token or user key:** edit the channel and paste both new values.
  Revoke the old application token at pushover.net.
- **Heartbeat URL:** regenerate the check's URL in Healthchecks.io, update
  `UKIP_OPS_HEARTBEAT_URL` in Dokploy, and redeploy.
- **To stop paging:** deactivate the Pushover channel, and pause the
  Healthchecks.io check. Record why in the incident response plan §11.

## 5. Evidence

Record in the tabletop follow-up (or the next exercise): the date of each test,
that the phone rang through Do Not Disturb, and the time from the container
stopping to the Healthchecks.io page. When both tests have passed, close #377
and mark plan §11 gap 2 closed.
