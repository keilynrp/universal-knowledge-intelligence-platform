# Tasks — generate TypeScript and Python API clients

Task group 0 must land before any client is generated; otherwise every method
name changes once and breaks whoever adopted the first cut.

## 0. Stabilize the contract

- [ ] 0.1 `generate_unique_id_function` on the FastAPI app → `{tag}_{route_name}`.
- [ ] 0.2 Test pinning operation IDs for a representative sample across tags.
- [ ] 0.3 Test: renaming a handler function does not change its operation ID.
- [ ] 0.4 Test: `app.openapi()` is deterministic across two calls.
- [ ] 0.5 Review the resulting ID list for collisions (two routes sharing a
      tag+name) and resolve by naming the routes explicitly.

## 1. Spec dump + generation script

- [ ] 1.1 `scripts/generate-sdk.mjs`: dump `sdk/openapi.json` via `app.openapi()`
      — no server, no DB, no lifespan.
- [ ] 1.2 Pin `@hey-api/openapi-ts` and `openapi-python-client` at exact
      versions.
- [ ] 1.3 Generate `sdk/typescript`.
- [ ] 1.4 Generate `sdk/python`.
- [ ] 1.5 Verify reproducibility: run twice, second run yields no diff. If it
      does, find the nondeterminism before going further.

## 2. Drift gate

- [ ] 2.1 CI job: regenerate + `git diff --exit-code sdk/`.
- [ ] 2.2 Failure message tells the author the exact command to run.
- [ ] 2.3 Prove the gate works: temporarily add a dummy route, confirm CI red,
      revert. A gate that has never failed has never been tested.

## 3. Auth + smoke tests

- [ ] 3.1 Both clients take one credential and send it as a bearer token.
- [ ] 3.2 TS smoke test: authenticate → list entities → typed result.
- [ ] 3.3 Python smoke test: same.
- [ ] 3.4 Smoke test: write call with a read-scoped key under enforcement → a
      distinguishable 403. (Cross-checks change 1 — if scope enforcement
      regresses, this fails.)

## 4. Documentation

- [ ] 4.1 `sdk/README.md`: install by git ref / local path, quickstart per
      language, regeneration instructions.
- [ ] 4.2 Scope model per README: the three scopes, the derivation rule, the
      hierarchy, and what a scope `403` means versus a role `403`.
- [ ] 4.3 State plainly which surface carries a stability commitment and which is
      generated wholesale.
- [ ] 4.4 `/developer` page: link the clients next to the curl quickstart.
- [ ] 4.5 `docs/API.md` cross-reference.

## 5. Verification

- [ ] 5.1 Full backend suite — 0.1 changes `openapi.json`, and tests that assert
      on the schema or on `/openapi.json` may break.
- [ ] 5.2 Frontend suite (the `/developer` page changed).
- [ ] 5.3 Confirm the drift gate passes on a clean tree.
- [ ] 5.4 PR.

## 6. Deliberately deferred

- [ ] 6.1 npm / PyPI publishing — needs a version policy and registry
      credentials.
- [ ] 6.2 Migrating `frontend/lib/api.ts` onto the generated client.
- [ ] 6.3 Ergonomic wrappers (pagination, retries, typed error hierarchy) — add
      after real usage shows what is missing.
