# Tasks — enforce API key scopes

TDD throughout: each numbered group writes the failing test first.

## 0. Pure scope logic (no DB, no FastAPI)

- [x] 0.1 `backend/api_key_scopes.py`: `SCOPE_IMPLIES` hierarchy +
      `satisfies(granted, required) -> bool`.
- [x] 0.2 `ADMIN_PATHS` table + `READ_OVERRIDES` registry. Each of the 17
      overrides was verified by AST scan to perform no session mutation in its
      handler before being listed.
- [x] 0.3 `scope_required(method, path) -> str` with the ordered rule set,
      plus `ADMIN_EXEMPT_PATHS` (`/users/me`) — see design.md rule 1.
- [x] 0.4 Unit tests — full truth table. (`test_api_key_scopes.py`, 58 tests)

## 1. Enforcement in the auth dependency

- [x] 1.1 Failing integration test verified RED (10 failures, each for the
      missing-feature reason). Target is `POST /annotations` with an empty body:
      403 = scope denied, 422 = scope passed and validation rejected — so the
      assertion is about authorization, not about annotations.
- [x] 1.2 `request: Request` on `get_current_user`; check in the `ukip_` branch
      only, via `enforce_api_key_scope()`. Route template from
      `request.scope["route"].path` with `request.url.path` fallback.
- [x] 1.3 Same for `get_current_user_optional` — denies rather than downgrading
      to anonymous, so a too-narrow key does not silently look like empty data.
      No write-classified optional-auth endpoint exists today (all three are
      `GET`), so this is covered by calling the dependency directly.
- [x] 1.4 `ws.py` handshake requires `read`; `HTTPException` is translated to the
      existing "close 4001" path rather than propagating out of a socket.
- [x] 1.5 403 body names the required scope and the scopes the key holds.

## 2. Warn mode + observability

- [x] 2.1 `UKIP_API_KEY_SCOPES_ENFORCED` read **at call time**, not at import, so
      the flag can be flipped without rebuilding the image.
- [x] 2.2 Warn path: proceed + WARNING log + audit `api_key.scope_violation`.
      Recording never raises — observability must not break a request.
- [x] 2.3 Test: warn mode does not block, and does write the audit entry.
- [x] 2.4 Test: the record contains neither the full key nor its random
      remainder — key prefix only.
- [x] 2.5 `/health.features.api_key_scopes_enforced`; test asserts it.
      (`test_api_key_scope_enforcement.py`, 24 tests)

## 3. Coverage guard — **pulled forward, ran before group 1**

Sequencing note: this group validates the group-0 tables, so running it before
building enforcement on top of them catches a bad table while it is still cheap
to change.

- [x] 3.1 Route-enumeration test over `app.routes`.
      (`test_api_key_scope_coverage.py`, 23 tests) Beyond totality it asserts
      **table liveness** — every `ADMIN_PATHS`, `ADMIN_EXEMPT_PATHS`, and
      `READ_OVERRIDES` entry must match a real route, so a typo'd or stale entry
      fails rather than silently protecting nothing.
- [x] 3.2 Table reviewed against all 430 route/method pairs:
      **191 read / 153 write / 86 admin**. No dead entries. Two judgment calls
      flagged for review: `/workflows` classified admin (its `send_webhook`
      action is the same data-exfiltration vector as `/webhooks`), and the
      `/users/me` exemption.

## 4. Privilege invariants

- [x] 4.1 Test: `["admin"]` key owned by a `viewer` → still denied by RBAC, and
      a companion test with enforcement *off* proves the denial comes from RBAC
      rather than from the scope check.
- [x] 4.2 Test: `["read"]` key owned by a `super_admin` → denied by scope.
- [x] 4.3 Test: JWT path completely unaffected (regression).

## 5. Config, docs, verification

- [x] 5.1 `UKIP_API_KEY_SCOPES_ENFORCED` declared in `docker-compose.prod.yml`
      **and** `.env.example`, both with the warn-mode rationale inline.
- [x] 5.2 `API.md` (the canonical reference; `docs/API.md` is a historical
      stub): derivation rule, admin surfaces, read overrides, hierarchy, the
      scope-403 vs role-403 distinction, and the rollout flag.
- [x] 5.3 Settings → API Keys UI: amber notice while enforcement is off, so the
      checkboxes do not read as a live restriction. Only an explicit `false`
      warns — a failed `/health` probe stays silent rather than guessing.
      EN + ES translations added.
- [x] 5.4 Full backend suite: **3300 passed, 7 skipped**. Frontend: **294
      passed** (43 files). `tsc --noEmit` clean. Design-system gate passed.
- [ ] 5.5 PR.

⚠️ Local ESLint is currently broken *independently of this change*:
`eslint-plugin-react` crashes under ESLint 10.7.0
(`contextOrFilename.getFilename is not a function`) on untouched files too.
The pre-push hook runs ESLint, so it will fail until that is resolved.

## 6. Rollout (operator, post-merge — not part of the PR)

- [ ] 6.1 Deploy with the flag at `0`.
- [ ] 6.2 Observe ≥7 days; query audit for `api_key.scope_violation`.
- [ ] 6.3 Contact owners of any violating key; widen the key's scopes or fix the
      integration.
- [ ] 6.4 Flip `UKIP_API_KEY_SCOPES_ENFORCED=1`; confirm `/health.features`.
