# Incident Tabletop Exercise — template

One copy per exercise, filled in during and right after it, committed as
evidence for `ER-IR-001` (#368 phase D). A tabletop that produces no gaps was
either too easy or not honest.

Rules: nothing is executed against production, the participants answer from
what the system **actually** offers (open the runbooks and endpoints for real),
and "I don't know" is a valid, valuable answer — write it down as a gap.

## Identification

- Exercise date (UTC):
- Facilitator:
- Participants and the role each played:
- Scenario used:
- Duration:

## Scenario

State it in a few lines, including the moment the participants are dropped
into. Suggested scenarios, hardest first:

1. **Stolen admin token.** An access token belonging to an admin is found in a
   public paste. It is valid for another 6 hours.
2. **Key exposure.** `ENCRYPTION_KEY` was pasted into a support ticket.
3. **Destroyed data.** A tenant reports that most of their entities are gone;
   the audit trail shows a workspace reset with a legitimate credential.
4. **Silent backup failure.** Backups have not run for six days; nobody
   noticed because the evidence was recorded manually.
5. **Host compromise.** The VPS shows a process nobody recognizes.

## Timeline

Every line with its UTC time, exactly as during a real incident.

| Time (UTC) | Who | Observation / decision / action | Evidence |
|---|---|---|---|
| | | | |

## Decisions

- Declared severity, and why:
- Who declared it:
- Containment chosen, and what it cost:
- Was customer notification triggered? By what criterion?
- Who would have approved the notification:

## Objective checks

Measured against the plan, not against impressions:

| Question | Answer |
|---|---|
| How long from the signal to someone noticing it? | |
| How long from noticing to containment? | |
| Was the evidence captured before containment disturbed it? | |
| Could the participants find the right runbook without help? | |
| Did any step fail because a capability does not exist? | |
| Was a secret written down anywhere it should not be? | |

## Gaps found

Each one gets an issue, or an explicit decision not to fix it. A gap without an
owner is a gap that will be found again in the next exercise.

| Gap | Severity if real | Corrective action | Issue | Owner |
|---|---|---|---|---|
| | | | | |

## Plan changes

What this exercise changed in `INCIDENT_RESPONSE_PLAN.md`. If nothing changed,
say so and say why.

## Approval

- Facilitator:
- Security/operations owner:
- Date:
