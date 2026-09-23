# Incident Tabletop Exercise — 2026-09-22

First exercise of `ER-IR-001` (#368 phase D), using
[the tabletop template](templates/INCIDENT_TABLETOP_TEMPLATE.md). It produced
six gaps, two of which were already known and are now measured, and two
capabilities that were verified to work as
[the plan](INCIDENT_RESPONSE_PLAN.md) claims.

Nothing was executed against production. Containment and recovery steps were
described, not performed. Read-only sources — the plan, the runbooks and the
application source — were opened for real, and every claim below about what the
system does was checked against the code rather than recalled.

## Identification

- **Exercise date (UTC):** 2026-09-22
- **Facilitator:** Claude Code session, acting as facilitator and recorder
- **Participants and the role each played:** the repository owner, holding every
  role in plan §2 — incident commander, operator, security lead and
  notification approver. That is not an artifact of the exercise; it is the
  actual staffing, and plan §11 gap 1 records it.
- **Scenario used:** stolen admin token (template scenario 1, the hardest)
- **Duration:** one sitting. The times in the timeline are the **scenario
  clock**, not the wall clock of the exercise.

## Scenario

An access token belonging to an account with the `admin` role is found in a
public paste by a third party, who reports it to the UKIP alert channel at
03:18 UTC on a Sunday. The token is decodable: its `exp` leaves roughly six
hours of validity at the moment it is read.

Participants are dropped in at **09:40 UTC**, when the owner opens their phone
and reads the message. No UKIP alert has fired overnight.

## Timeline

| Time (UTC) | Who | Observation / decision / action | Evidence |
|---|---|---|---|
| 03:18 | Third party | Reports a public paste containing an admin JWT to the alert channel | Chat message |
| 03:18–09:40 | — | No UKIP signal fires. Nothing pages | Plan §11 gap 2 |
| 09:40 | Owner | Reads the report. Declares **SEV2**. Starts the notification clock at 09:40 | Plan §3, §8 |
| 09:42 | Owner | Decides to capture evidence before containing: container logs first, then `audit_logs` for the account | Plan §5.2, §7 |
| 09:55 | Owner | Cannot reach the host: no SSH from the phone. Evidence capture is ~20 minutes away | Exercise answer |
| 09:56 | Owner | **Contains**: deactivates the compromised admin account from the phone, accepting the loss of read traceability | `DELETE /users/{id}`, which is itself audited |
| 10:18 | Owner | Captures container logs. No restart had occurred, so they survived | `incident-<id>-backend.log` |
| 10:18 | Owner | Log shows ~600 authenticated `GET` requests from an unseen IP between 04:02 and 04:47, sequential pagination, all `200`, including `GET /audit-log/export`. `audit_logs` for the window: **zero rows** | Container log; `GET /audit-log?username=…` |
| 10:25 | Owner | Raises to **SEV1** (plan §3: unclear severity resolves upward). Confirms customer notification is triggered (plan §8: credible suspicion, not confirmation) | Plan §3, §8 |
| 10:40 | Owner | Defers drafting the notification pending a determination of scope | Plan §8 |
| 10:40 | Facilitator | Exercise closed | — |

## Decisions

- **Declared severity, and why:** SEV2 at 09:40 — a credential exposed with no
  evidence of use is the §3 example for that level. Raised to SEV1 at 10:25,
  once bulk authenticated reads were visible: §3 requires the higher severity
  when it is unclear, and the reads made "credible risk" untenable as a
  description.
- **Who declared it:** the repository owner, per plan §2. Uncontested, because
  there is nobody else.
- **Containment chosen, and what it cost:** deactivation of the compromised
  account at 09:56, from a phone, in about a minute. The cost was accepted
  knowingly: containing before capturing meant giving up any chance of
  observing the token in use. In the event it cost nothing, because reads are
  not recorded anyway (gap 1) — but that was not known at 09:56.
- **Was customer notification triggered? By what criterion?** Yes, at 10:25,
  on the §8 trigger of *credibly suspected* unauthorized access. The clock had
  already been started at 09:40, which is the moment §8 defines as becoming
  aware. The internal 48-hour target falls on 2026-09-24 09:40 UTC and the
  contractual 72-hour limit on 2026-09-25 09:40 UTC.
- **Who would have approved the notification:** the same person who wrote it.
  Plan §8 already discloses this as a weakness; the exercise did not soften it.

## Objective checks

| Question | Answer |
|---|---|
| How long from the signal to someone noticing it? | **6 h 22 min** (03:18 → 09:40), overnight, and the signal came from a third party rather than from UKIP |
| How long from noticing to containment? | **16 min** (09:40 → 09:56) |
| Was the evidence captured before containment disturbed it? | **No**, and deliberately so. Containment was about twenty times faster to reach than evidence capture. The container logs survived by luck, not by design: no restart happened during the gap |
| Could the participants find the right runbook without help? | Yes. The plan, the backup runbook and the secrets rotation runbook were located and used without prompting |
| Did any step fail because a capability does not exist? | **Yes, twice.** Attributing the reads to the stolen credential was impossible, and the set of records read could not be determined from telemetry |
| Was a secret written down anywhere it should not be? | No. The token was referred to by description throughout; no key material entered the timeline |

## Gaps found

| Gap | Severity if real | Corrective action | Issue | Owner |
|---|---|---|---|---|
| Reads are not audited: `AuditMiddleware` records only `POST`/`PUT`/`PATCH`/`DELETE`, so "what did they access" returns an empty result | High — an empty audit window cannot distinguish "never used" from "used only to read" | Audit a defined set of sensitive reads, carrying the acting identity | #375 | Security/operations owner |
| The request log carries no user identity, so no read is attributable | High — about 600 reads were visible and none could be tied to the credential | Add the authenticated identity to the request log line, never the token | #376 | Security/operations owner |
| Nothing pages | High — 6 h 22 min undetected, overnight, reported by an outsider | A wake-up path for SEV1-class signals, and an exercise that proves it works | #377 | Security/operations owner |
| `GET /audit-log` cannot filter by `ip_address`, though every row stores one | Medium — the one available pivot required manual correlation | Add the filter to the list and export endpoints | #378 | Security/operations owner |
| A stolen token belonging to the operator's **own** account cannot be contained by deactivation: `PUT`/`DELETE /users/{id}` refuse both self-deactivation and deactivating the last active `super_admin`. The only remaining containment is rotating the global signing key, which logs everyone out | High — the single credential most likely to be stolen is the one that cannot be revoked in isolation | Per-session revocation | #368 phase C.3 | Security/operations owner |
| Blast radius could not be determined from telemetry: reads are unaudited, the log holds the route and not the body, and with tenants unpopulated in production an admin without an `org_id` falls into the legacy global scope (`org_id IS NULL`) and reads essentially everything | High — the DPA requires categories and approximate record counts that could not be produced | Tenant-isolation method, already the open gate of ER-BCP-001 | #320 residual risk 1 | Operations owner |

## What was verified to work

A tabletop that reports only failures is not honest either. Two load-bearing
claims were checked against the source and hold:

1. **Containment is immediate, as plan §5.3 claims.**
   `get_current_user` (`backend/auth.py`) re-queries the database on **every**
   request, filtering `is_active == True`, with no user cache in the path. The
   stolen token remained cryptographically valid, and every request carrying it
   received `401` from 09:56 onward. Containment does not wait for token expiry.

2. **Scope is reconstructible after the fact, even though it is not observable
   live.** `GET /entities` defaults to `sort_by=id` and `order=asc`, and the
   logged URLs carried no ordering parameters, so the pagination was
   deterministic. Replaying the recorded `skip` and `limit` values against an
   isolated restore of the 03:05 backup — which predates the 04:02 reads —
   under the compromised account's `org_id` yields the exact list of records
   read. Measured RTO for a restore is 4 h, well inside the 48-hour internal
   target. This method is now written into the plan; it existed in no runbook
   before this exercise.

## Plan changes

Three, each because of something that happened in this exercise:

1. **§8 gained the rule it was missing.** The plan said when to notify and what
   a notification contains, but not what to do when the deadline arrives and
   the scope is still unknown. It now says that the deadline governs certainty:
   notify with what is proven, complete it afterwards, and never treat silence
   as the default. GDPR Article 33 permits phased notification; waiting for a
   complete picture is what it does not permit. The plan already defines
   *becoming aware* as suspicion rather than confirmation, and it would be
   incoherent for the exit to demand the certainty the entry rejects.

2. **§5.2 gained the availability asymmetry.** "Capture before you disturb"
   assumed evidence and containment are equally reachable. Here containment was
   a minute away on a phone and evidence twenty minutes away on a laptop, while
   the only source that saw the reads was ephemeral. The plan now says what to
   do when the two are not equally available.

3. **§7 was corrected, and §11 gained the new gaps.** §7 described `audit_logs`
   as "who called what, over HTTP". That is true only of mutations, and the
   wording would mislead at precisely the moment it is most expensive to be
   misled.

## Approval

- **Facilitator:** Claude Code session, 2026-09-22
- **Security/operations owner:** the repository owner (`keilynrp`)
- **Date:** 2026-09-22

Maturity outcome: `ER-IR-001` advances from `identified` to `specified`, and no
further. The control is now documented, decided and exercised — and the
exercise showed it cannot yet do what it promises, because an incident it is
written for cannot attribute access or establish scope. `verified` would assert
that it works. This follows the precedent set by `ER-BCP-001`, whose first
drill ran, failed two required checks, was recorded as failed, and left the
maturity where it was.
