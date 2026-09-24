# Tasks — attribute every request, audit the reads that matter

TDD throughout: each group writes the failing test first. Each numbered
section is sized to ship as one PR, in order; later sections depend on 1.

## 1. One principal per request (foundation)

- [ ] 1.1 Test first: a throwaway route behind `get_current_user`, and a probe
      middleware that reads `request.state.principal` after `call_next`. Assert
      it is visible for a JWT request, an API-key request, and absent for a
      refused one. **If it is not visible, switch to the holder fallback in
      design.md before going further.**
- [ ] 1.2 `backend/principal.py`: frozen `Principal(user_id, session_id,
      api_key_id)`, no username.
- [ ] 1.3 Record it in both branches of `get_current_user` and
      `get_current_user_optional`, only after every check has passed (scope
      enforcement included for keys).
- [ ] 1.4 Tests: revoked session, expired token, unknown key and insufficient
      scope all leave no principal.

## 2. Identity in the request log (closes #376)

- [ ] 2.1 Test first with `caplog`: authenticated JWT read → `user_id` and
      `session_id` on `request_completed`; API key → `user_id` and
      `api_key_id`; anonymous and `401` → none of the three fields present.
- [ ] 2.2 `RequestLoggingMiddleware`: add the fields from the principal on
      both `request_completed` and `request_failed`.
- [ ] 2.3 Test that no token, key, header or query value appears in any record
      (serialise the formatted line and search it for the token string).
- [ ] 2.4 Plan §7: container logs are now attributable. Update the DPA §5
      "attributable request logs … remain open" line to match.

## 3. Principal on audit rows

- [ ] 3.1 Migration: `audit_logs.session_id String(64)` (indexed),
      `audit_logs.api_key_id Integer` (no FK). Model updated; upgrade and
      downgrade checked on SQLite; pg covered by CI's migration rehearsal.
- [ ] 3.2 Test first: an API-key `POST` writes a row with `user_id` and
      `api_key_id` (today both are empty); a `PUT` with a revoked token writes a
      row with no identity.
- [ ] 3.3 `AuditMiddleware`: take identity from the principal; delete
      `_decode_username`; resolve `username` from `user_id` for existing
      readers.
- [ ] 3.4 Test: deleting a key leaves its rows and `api_key_id` intact.

## 4. Read audit by class (closes #375)

- [ ] 4.1 `backend/read_audit.py`: `EXPORT_ROUTES`, `EXPORT_EXCLUSIONS` (each
      with a reason) and `read_audit_class(method, route, query, principal)`.
      Unit tests cover the full rule table in design.md, including the
      thresholds (`skip=0&limit=500` → none, `skip=1` → READ, `limit=501` →
      READ).
- [ ] 4.2 Route-coverage test: every `GET` route with `export`, `download` or
      `csv` in its template, or a streaming file response, is in
      `EXPORT_ROUTES` or `EXPORT_EXCLUSIONS`. Populate the table from the
      current app until it passes, and review each entry.
- [ ] 4.3 `AuditMiddleware`: write `READ`/`EXPORT` rows for classified reads,
      with `details = {limit, skip, query_keys}`. Record `401`/`403` when a
      principal exists.
- [ ] 4.4 Test: `?q=jane%20doe&skip=50` stores `query_keys` and `skip` only;
      the search value appears nowhere in the row.
- [ ] 4.5 Test: `GET /audit-log/export` records its own execution.
- [ ] 4.6 Measure: the added latency of one audited read in the test client,
      recorded in the PR.

## 5. Pivot on a session

- [ ] 5.1 `session_id` filter on `/audit-log`, `/export` and `/stats` (the same
      pattern as `ip_address` in #384); `READ` and `EXPORT` in the action
      filter. Tests as for #384.
- [ ] 5.2 Audit-log page: session field; action options; a session id in the
      timeline pivots like an IP does.
- [ ] 5.3 Sessions list (#383): each session links to `/audit-log` filtered by
      it.
- [ ] 5.4 Regenerate OpenAPI, SDK clients, i18n projection, repo metrics.

## 6. Close the loop

- [ ] 6.1 Plan §7: what `audit_logs` now covers, and the residual (reads
      outside the four classes are in the request log only, which vanishes
      with the container unless captured first).
- [ ] 6.2 Plan §11: close gap 9 (reads not audited) and gap 10 (request log
      has no identity), each with what remains of it stated. Gap 3 (no central
      log retention) stays open and now matters more: the request log is
      attributable but still ephemeral.
- [ ] 6.3 Plan §11 gap 11 (no IP filter) was closed by #384 and the plan does
      not say so yet. Close it in section 1's PR rather than waiting for this
      one.
- [ ] 6.4 After 30 days in production: report `READ`/`EXPORT` row volume, so
      the owner can decide the open questions in design.md (retention, class 4
      breadth).
