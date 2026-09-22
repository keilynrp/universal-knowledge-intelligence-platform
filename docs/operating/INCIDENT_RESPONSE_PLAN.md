# UKIP Incident Response Plan

Control `ER-IR-001` / US-079. This plan says how a suspected security or
availability incident is declared, classified, contained, evidenced and
communicated.

It describes **what exists today**, and marks what does not. A plan that
claims capabilities the team does not have is worse than no plan: it is
discovered to be fiction during the incident it was written for.

Both decisions this plan waited on were made on 2026-09-22 (#368 phase B):
the repository owner declares incidents and authorizes customer notification,
and the DPA commits notification **within 72 hours** of becoming aware, with
an internal target of 48. Both are recorded in §2 and §8, and are revisited
when the team grows past one person.

---

## 1. Scope

| In scope | Out of scope |
|---|---|
| Unauthorized access to UKIP data or accounts | Product bugs with no security or availability impact |
| Exposure of credentials, keys or tokens | Planned maintenance |
| Loss, corruption or unauthorized deletion of data | Customer-side incidents in their own systems |
| Production unavailability or severe degradation | Vendor incidents with no effect on UKIP data or service |
| Suspected tampering with audit or backup evidence | |

A vendor incident that **does** touch UKIP data or availability (the VPS host,
the S3 backup provider, the OAuth identity provider) is in scope.

## 2. Roles

Today UKIP is operated by one person. **That person currently holds every role
below.** This is recorded, not hidden: it means there is no second pair of eyes
during an incident and no escalation path if they are unavailable. Treat it as
the top residual risk of this control.

| Role | Responsibility | Who |
|---|---|---|
| Incident commander | Declares the incident and its severity, runs the response, owns the timeline | the repository owner (`keilynrp`) |
| Operator | Executes containment and recovery steps | the repository owner (`keilynrp`) |
| Security lead | Judges blast radius, decides whether data was affected | the repository owner (`keilynrp`) |
| Notification approver | Authorizes what is told to customers and when | the repository owner (`keilynrp`) |
| Deputy | Takes over if the commander is unreachable | **None.** See §11 gap 1 |

**Declaration authority (decided 2026-09-22):** the repository owner (`keilynrp`) declares incidents and
authorizes customer notification. Anyone who suspects an incident raises it
immediately; over-declaring is cheap, under-declaring is how incidents are
discovered by customers.

This concentration of roles is accepted deliberately, not overlooked: it is
what a one-person team can commit to today. **It is revisited when funding and
staffing allow a second responder**, and the deputy row is the first thing that
changes then.

## 3. Severity model

Severity is about **impact**, not about how hard the fix looks. Reassess it as
facts arrive: severity is a working hypothesis, and it moves in both
directions.

| Severity | Definition | UKIP examples | Response |
|---|---|---|---|
| **SEV1** | Confirmed unauthorized access to customer data, or production unusable with no workaround | Stolen admin credential used to read another tenant's data; database destroyed; ransomware on the VPS | Drop everything. Continuous work until contained. |
| **SEV2** | Credible risk of data exposure, or a core function broken for everyone | Encryption or JWT key exposed with no evidence of use; backups unrecoverable; auth broken for all users | Same working day, without interruption |
| **SEV3** | Degraded service or a control not working, with no data at risk | Scheduled detection dead; backups stale beyond RPO; a scheduler stopped; deploy left the schema stale | Within one working day |
| **SEV4** | A weakness worth fixing, no live impact | An unused permission that is too broad; a dependency vulnerability with no exploit path | Tracked as an ordinary issue |

Rules that do not bend:

- **Any suspicion that personal data left the boundary is at least SEV2** until
  proven otherwise, and the notification clock starts at that moment.
- **Suspected tampering with evidence** (audit trail, backup events) is at least
  SEV2, because it attacks the ability to investigate everything else.
- If the severity is unclear, it is the higher one until the facts say
  otherwise.

## 4. Detection

What actually reaches a human today:

| Source | What it catches | How it reaches someone |
|---|---|---|
| Scheduled detection (#368) | Database, migrations, schedulers, alerting, secrets, backup freshness | `ops.check_failed` to Slack within 5 minutes of a state change, plus a reminder every 6 h while it lasts; also the container log |
| `GET /health` | Service up, schema drift, bootstrap state | Polled by the operator; **nothing pages on it** |
| `GET /ops/checks` | The full check suite on demand | Operator, admin credential |
| Backup assurance | Stale, missing or invalid backups; provider unreachable | Feeds the checks above |
| `audit_logs` | Who did what, over HTTP | Read after the fact |
| GitHub security gates | Vulnerable dependencies, secrets in commits, CodeQL findings | Pull request checks and email |
| Dokploy | Deploy failures, container restarts | Its own UI |
| Customer report | Everything nobody instrumented | Email |

**Known detection gaps.** No paging outside Slack, so a SEV1 at 03:00 waits for
someone to look at their phone. No central log retention: container logs are
ephemeral and disappear with the container, which is why capturing them is the
first evidence step below. Error telemetry (Sentry) is available but off by
default. Nothing watches for anomalous login or access patterns.

## 5. Response steps

### 5.1 Declare

1. State the suspicion in one sentence, with the time it was noticed.
2. Assign a severity from §3. When in doubt, go higher.
3. Start a timeline file (§7). Every later step appends to it, with UTC times.
4. For SEV1 and SEV2, note the moment the clock started for notification (§8).

### 5.2 Assess

Before changing anything, capture what you are about to disturb (§7). Then
establish, in this order:

1. **What is affected?** One tenant, one user, one component, or everything.
2. **Is data involved?** Read, changed, exfiltrated, destroyed — or none of
   these, which is also an answer worth recording.
3. **Is it ongoing?** An attacker with a live session needs containment before
   analysis.

### 5.3 Contain

Containment beats tidiness. It is acceptable to log every user out or take a
function offline. Record each action and its time.

| Situation | Action today | Cost |
|---|---|---|
| Compromised user account | Set `is_active = False` for that user. Every request re-resolves the user and requires `is_active`, so **live sessions stop immediately**, not at token expiry | That person cannot work |
| Compromised API key | `DELETE /api-keys/{id}` (revoke) | Only that integration stops |
| JWT signing key exposed | Rotate `JWT_SECRET_KEY` — secrets rotation runbook §2, shortening or skipping the grace window | **Everyone is logged out** |
| Encryption key exposed | Secrets rotation runbook §1 end to end, then destroy the old key (the one case where it is destroyed, not archived) | Pre-rotation backups keep values encrypted with the destroyed key |
| Bad deploy | Redeploy the previous commit in Dokploy; confirm `/health` reports that commit with `schema: current` | Whatever the deploy contained is reverted |
| Data loss or corruption | Backup and restore runbook. Objectives: RPO 24 h, RTO 4 h. **Restore into an isolated target first**, never over production | Data written after the recovery point is lost |
| Host or provider compromise | Treat every credential on that host as exposed and rotate all of them; the writer credential cannot delete backup versions and Object Lock protects them for 7 days | Wide blast radius; expect a long response |

**What cannot be contained today:** a single session or device cannot be
revoked without disabling the account or rotating the global signing key
(#368 phase C.3).

### 5.4 Eradicate and recover

1. Remove the cause, not only the symptom.
2. Restore service, and verify with `/ops/checks`, not by impression.
3. Rotate every credential that was exposed, or may have been.
4. Keep watching: the same signal that found it should now be quiet, and
   scheduled detection should report `recovered`.

## 6. Communication

Internal first, then customers per §8. During an incident:

- SEV1: update the timeline at least hourly, even when the update is "no
  progress yet".
- SEV2: update at least twice a day.
- Never describe a problem as solved before a check confirms it.

## 7. Evidence

Evidence is collected **before** containment changes the system, because
containment destroys state. Minimum set:

1. **Container logs**, first, because they vanish with the container:
   `docker logs <container> > incident-<id>-backend.log`
2. **Database evidence**, which survives by design:
   - `audit_logs` — who called what, over HTTP. Retained indefinitely by policy
     and no longer deleted by a workspace reset (#372).
   - `backup_assurance_events` — append-only; `UPDATE`, `DELETE` and `TRUNCATE`
     are all refused at the database (#365).
   - `data_lifecycle_events` — exports, deletions, purges, workspace resets.
   - `secret_rotation_events` — key fingerprints and dates, never key material.
3. **Provider evidence**: S3 object versions and Object Lock state; CloudTrail
   for management calls (it does **not** cover S3 object reads); Dokploy deploy
   history.
4. **The timeline**, kept by hand: each observation, decision and action with
   its UTC time and who did it.

Never paste secrets into the timeline, tickets or chat. Record a key by its
fingerprint, never its value.

## 8. Customer notification

**Trigger.** Any confirmed or credibly suspected unauthorized access to, or
loss of, customer data. Availability alone does not trigger it unless the
contract says so.

**Timeframe (decided 2026-09-22).** The controller is notified **without
undue delay and in any case within 72 hours** of the operator becoming aware
of a personal data breach. The **internal target is 48 hours**; 72 is the
committed limit, because a single responder with no paging cannot honestly
promise less as a contractual floor. `docs/legal/DPA_BASELINE.md` §11 carries
the same commitment; the two are changed together or not at all.

"Becoming aware" means the moment a person forms a credible suspicion that
customer data was accessed, lost or altered without authorization — not the
moment it is confirmed. §5.1 requires that moment to be written down.

**What a notification contains** (DPA §11, already agreed): the nature of the
breach; the categories and approximate number of data subjects and records
concerned; the likely consequences; and the measures taken or proposed.

**Who approves it:** the repository owner (`keilynrp`), per §2. Today the same person writes and
releases it, which is a known weakness of a one-person team: there is no second
reader before a customer communication goes out.

**Mexico:** `docs/legal/MEXICO_ANNEX.md` applies in addition. Check it before
notifying, do not assume the DPA covers everything.

## 9. Postmortem

Within five working days of closing a SEV1 or SEV2, and for any incident that
surprised the team.

Blameless: the question is what let this happen and what made it hard to see,
not who typed the command. Each postmortem records the timeline, the impact,
the cause, what detected it, what slowed the response, and corrective actions
as tracked issues.

**Worked example, already in the repository.** The 2026-09-20 migration
incident (#359, #360) is a postmortem in everything but name: a migration that
tried to rewrite append-only evidence took `/ops/backups/*` down for about
three hours. It was detected by `/health` reporting `schema: stale`, its
corrective actions became #361 (CI now rehearses migrations over data, #364)
and the append-only control was hardened afterwards (#363, #365). That is the
shape a postmortem should take.

## 10. Exercises

This plan is not credible until it has been exercised. A tabletop uses
[the tabletop template](templates/INCIDENT_TABLETOP_TEMPLATE.md) and produces a
timeline, the gaps found and corrective actions. `ER-IR-001` cannot reach
`operated` without at least one (#368 phase D).

## 11. Known gaps

Recorded here so nobody discovers them mid-incident:

1. **One person holds every role**, with no deputy and no escalation path.
   Accepted by the owner on 2026-09-22 as what the current team can commit to,
   and revisited when funding and staffing allow a second responder. It is also
   why the notification commitment is 72 hours rather than 24.
2. **No paging.** Alerts reach Slack and the container log; nothing wakes
   anyone up.
3. **No central log retention.** Container logs are ephemeral, so early capture
   is the only way to keep them.
4. **No per-session revocation** (#368 phase C.3): containing one stolen token
   means disabling the account or logging everyone out.
5. **Error telemetry off by default** (`SENTRY_ENABLED=0`).
6. **No anomaly detection** on logins or access patterns.
7. **Tenant isolation is not demonstrable** from production data today
   (ER-BCP-001 residual risk 1), which would matter when judging blast radius
   in a multi-tenant incident.
8. **Backup evidence ingestion is manual** (#370), so a stale-backup alert may
   mean "nobody recorded it" rather than "no backup exists". Check both.

## 12. Maintenance

Owner: the security/operations owner named in
`docs/product/ENTERPRISE_CONTROL_REGISTER.md`. Reviewed after every SEV1 or
SEV2, after every tabletop, and at least annually. Changes are versioned in
this repository; the plan in use is the one on `main`.
