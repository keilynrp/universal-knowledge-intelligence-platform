# Attribute every request, and audit the reads that matter

> **Closes:** #376 (request log has no identity), #375 (reads are not audited).
> **Found by:** the first ER-IR-001 tabletop, 2026-09-22 (#368 phase D).
> **Depends on:** per-session tokens (#381), which give every JWT request a
> revocable session id to attribute to.

## Why

The tabletop's scenario was a stolen admin token. The first question every
incident asks is *what did they access*, and today the system cannot answer it:

- **The audit log records no reads.** `AuditMiddleware` writes a row only for
  `POST`, `PUT`, `PATCH` and `DELETE`. An empty window for a suspect account is
  ambiguous between "never used" and "used only to read", including reading
  `GET /audit-log/export`, which does not record its own execution.
- **The request log records every read, but not who made it.** About 600
  authenticated reads from an unfamiliar address were visible in the container
  log, inside the exposure window, with a sweep pattern, and still could not be
  attributed to the stolen credential. Attribution had to be inferred.

Together these are why blast radius could not be established from telemetry.
The plan's notification rule (§8) then has to notify on what is proven, and
very little was proven.

Reading the code for this proposal found a third gap, narrower but in the
same place: **mutations made with an API key are audited without an
identity.** The middleware takes the username by decoding the bearer token as
a JWT, and a `ukip_…` key is not one. The same shortcut attributes a mutation
to whoever a *revoked* token names, because decoding checks the signature, not
the session.

## What Changes

- **One resolved principal per request.** The auth dependencies already
  resolve who is acting, for both JWTs and API keys, on every authenticated
  request. They record it on the request (`user_id`, `session_id` or
  `api_key_id`) so that the logging and audit middlewares read it rather than
  re-deriving it. There is no extra database query, and nothing is attributed
  that authentication did not accept.
- **The request log carries it (#376).** `request_completed` and
  `request_failed` gain `user_id`, and `session_id` or `api_key_id`. An
  unauthenticated or rejected request carries none of these fields, not a
  placeholder. Tokens, keys and bodies are never logged.
- **Audit rows carry it.** `audit_logs` gains `session_id` and `api_key_id`,
  and `user_id` is populated. API-key mutations become attributable, and a
  revoked token can no longer lend its name to a row.
- **Reads that matter are audited (#375)**, as `READ` or `EXPORT` rows, by
  class rather than blanket:
  1. every export and download,
  2. every read of the audit log itself,
  3. every read made with an API key,
  4. bulk reads: pages past the first, or a page size above the UI default.

  The row records the route template, the status, the principal, and the
  paging parameters. It never records other query values, which can be search
  terms about people.
- **The audit log can pivot on a session.** `GET /audit-log` gains
  `session_id`, beside the `ip_address` filter from #384. From the sessions
  list, a session links to what it did.
- **The plan says what the evidence now covers.** `INCIDENT_RESPONSE_PLAN.md`
  §7 and §11 (gaps 9 and 10) are updated, and what stays uncovered (reads
  outside the four classes) is written down rather than implied.

## Non-goals

- A blanket audit of every read. Class 4 is the compromise; the design records
  how to widen it if the volume turns out to be small.
- Auditing WebSocket traffic.
- Anomaly detection or alerting on the new data. That is #377 and plan §11
  gap 6.
- Tamper evidence for `audit_logs` (signing, append-only enforcement). That is
  ER-AUD-001, a separate control.

## Impact

- `backend/auth.py`: both dependencies record the principal.
- `backend/logging_utils.py`: identity fields on the request log.
- `backend/audit.py`: principal instead of token decoding, plus the read path.
- New `backend/read_audit.py`: pure classification (no DB, no FastAPI), with a
  route-coverage test that fails when an export route lands unclassified.
- `backend/routers/audit_log.py`: `session_id` filter, `READ`/`EXPORT` actions.
- Migration: `audit_logs.session_id` (indexed) and `audit_logs.api_key_id`.
- Frontend: audit-log action filter, session pivot, a link from the sessions
  list.
- Docs: plan §7 and §11, DPA §5 ("attributable request logs … remain open").
- **Volume:** one extra insert per audited read. Classes 1–3 are low volume by
  nature. Class 4 is the one to watch, and the design sets its thresholds to
  stay out of ordinary UI browsing.
