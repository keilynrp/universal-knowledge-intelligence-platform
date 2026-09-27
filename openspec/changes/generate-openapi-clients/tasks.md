# Tasks — generate TypeScript and Python API clients

Task group 0 must land before any client is generated; otherwise every method
name changes once and breaks whoever adopted the first cut.

## 0. Stabilize the contract

- [x] 0.1 `generate_unique_id_function` on the FastAPI app → **method + path**.
      NOT `{tag}_{route_name}` as originally designed: `route.name` IS the
      function name, so that rule would not have delivered the property the
      spec requires. Correction recorded in design.md.
- [x] 0.2 Test pinning operation IDs for a representative sample across tags.
- [x] 0.3 Test: renaming a handler function does not change its operation ID.
- [x] 0.4 Test: `app.openapi()` is deterministic across two calls.
- [x] 0.5 Review the resulting ID list for collisions (two routes sharing a
      tag+name) and resolve by naming the routes explicitly.

## 1. Spec dump + generation script

- [x] 1.1 `scripts/generate-sdk.mjs`: dump `sdk/openapi.json` via `app.openapi()`
      — no server, no DB, no lifespan.
- [x] 1.2 Pin `@hey-api/openapi-ts@0.99.0`, `typescript@5.7.3` and
      `openapi-python-client==0.29.0` — pinned in `scripts/generate-sdk-clients.sh`.
      **UNBLOCKED via Docker** instead of the three README options: the
      Windows `npx ECOMPROMISED` failure and the lockfile-regeneration hazard are
      both sidestepped by running each generator in a pinned official image
      (`node:20-slim`, `python:3.12-slim`) — a clean Linux toolchain that never
      touches `frontend/package-lock.json`.
- [x] 1.3 Generate `sdk/typescript` — `@hey-api/openapi-ts`, all 420 operations.
- [x] 1.4 Generate `sdk/python` — `openapi-python-client`. Full public surface;
      three internal domain-admin `-Output` models omitted (FastAPI
      `-Input`/`-Output` name collision the generator cannot split). Documented
      in sdk/README.md "Python fidelity note".
- [x] 1.5 Reproducibility verified: regenerated both twice, no source diff. The
      only nondeterministic artifact is `sdk/python/.ruff_cache/`, which is
      git-ignored (sdk/.gitignore).

## 2. Drift gate

- [x] 2.1 CI job: regenerate + `git diff --exit-code sdk/`.
- [x] 2.2 Failure message names the command: `node scripts/generate-sdk.mjs`.
- [x] 2.3 Prove the gate works: temporarily add a dummy route, confirm CI red,
      revert. A gate that has never failed has never been tested.
- [x] 2.4 Extend drift coverage to the generated clients (not just the spec):
      `sdk-clients-drift` CI job runs `bash scripts/generate-sdk-clients.sh
      --check`, which regenerates in the pinned Docker images and
      `git diff`s `sdk/typescript`+`sdk/python`. Failure names the regen command.
      Verified: clean tree passes; a hand-edit to a generated file turns it red.

## 3. Auth + smoke tests

- [x] 3.1 Both clients take one credential and send it as a bearer token —
      `AuthenticatedClient(token=...)` (Python) and `client.setConfig({headers})`
      (TS), exercised by the list-entities calls in `sdk/smoke/`.
- [x] 3.2 TS smoke test: authenticate → list entities → typed result —
      `sdk/smoke/smoke.ts` (run via `tsx`). Verified against a live backend.
- [x] 3.3 Python smoke test: same — `sdk/smoke/smoke.py`. Verified.
- [x] 3.4 Smoke test: write call with a read-scoped key under enforcement → a
      distinguishable, scope-naming 403 — `smoke.py` (`UKIP_SMOKE_EXPECT_ENFORCEMENT=1`).
      Verified against an ephemeral backend with `UKIP_API_KEY_SCOPES_ENFORCED=1`.
      Run in CI by the `sdk-smoke` job (backend booted with enforcement on).
      Note: the CI job proves the client path; the *production* enforcement flip
      is the separate `enforce-api-key-scopes` operational rollout (group 6).

## 4. Documentation

- [x] 4.1 `sdk/README.md`: install by git ref / local path, quickstart per
      language, regeneration instructions — added "Installing and using" +
      "Generating the clients".
- [x] 4.2 Scope model per README: the three scopes, the derivation rule, the
      hierarchy, and what a scope `403` means versus a role `403` — "API key
      scopes" section.
- [x] 4.3 State plainly which surface carries a stability commitment and which is
      generated wholesale — "Stability" + "What is here today" sections.
- [x] 4.4 `/developer` page: link the clients next to the curl quickstart.
      "Client SDKs" now shows the generated clients (install + usage per
      language, links to `sdk/README.md` and each client's folder) instead of
      hand-written `requests`/`fetch` calls. Both snippets verified: the TS one
      typechecks against a vendored copy of `sdk/typescript`, the Python one
      imports from a clean install of `sdk/python`. The TS instructions in
      `sdk/README.md` were wrong and are fixed: there is no `package.json` to
      `npm install`, and `client` is exported from `client.gen`, not the index.
- [x] 4.5 `docs/API.md` cross-reference — "Generated SDK clients" section links
      to sdk/README.md and the regeneration script.

## 5. Verification

- [x] 5.1 Full backend suite — 0.1 changes `openapi.json`, and tests that assert
      on the schema or on `/openapi.json` may break. Operation IDs (0.1) landed
      earlier with the suite green; the `/developer` change touches no backend
      code, and its backend tree is main's, whose full suite passed CI in #403.
- [x] 5.2 Frontend suite (the `/developer` page changed): ESLint, `tsc`, vitest 358/358.
- [x] 5.3 Confirm the drift gate passes on a clean tree: `generate-sdk.mjs --check`
      and `generate-sdk-clients.sh --check` both OK.
- [ ] 5.4 PR.

## 6. Deliberately deferred

- [ ] 6.1 npm / PyPI publishing — needs a version policy and registry
      credentials.
- [ ] 6.2 Migrating `frontend/lib/api.ts` onto the generated client.
- [ ] 6.3 Ergonomic wrappers (pagination, retries, typed error hierarchy) — add
      after real usage shows what is missing.
