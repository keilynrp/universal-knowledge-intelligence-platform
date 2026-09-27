# Generate TypeScript and Python API clients

> **Priority: 3 of 3** (SDK / developer-surface track)
> **Depends on:** `enforce-api-key-scopes` — the client's auth documentation
> must describe scopes that are real. Shipping an SDK that documents scoped keys
> while scopes are unenforced would multiply the false promise across every
> integration.

## Why

UKIP has no client SDK. "Integrating with UKIP" today means hand-writing HTTP
calls against ~60 routers, discovering request and response shapes by reading
`/docs`, and re-deriving them every time a schema changes. Nothing tells an
integrator that a field they depend on was removed until their code breaks in
production.

We already have the raw material: FastAPI publishes a complete `openapi.json`
covering every route, and the `/developer` portal already points at it. What is
missing is the generated artifact and — more importantly — the guarantee that it
stays in sync.

The `/developer` page's quickstart is three curl commands. That is a reasonable
first contact and a poor foundation for anyone building on us.

## What Changes

- **A stable public contract.** FastAPI's default `operationId`s embed the
  function name, path, and method (`create_widget_widgets_post`), which produces
  ugly and unstable client method names — renaming a Python function silently
  renames a public SDK method. Install a deterministic
  `generate_unique_id_function` so operation IDs derive from route name and tag,
  and pin the resulting names with a test.
- **Two generated clients, committed to the repo:**
  - `sdk/typescript` — generated with `@hey-api/openapi-ts`.
  - `sdk/python` — generated with `openapi-python-client`.
  Both are consumed by git reference or local path. **Not published to npm or
  PyPI in this change** — publishing implies a versioning and deprecation
  commitment to strangers that we should make deliberately, not as a side
  effect of adding a build script.
- **One regeneration entry point**: `scripts/generate-sdk.mjs` dumps
  `openapi.json` from the app without booting a server, then runs both
  generators.
- **A CI drift gate**: regenerate and `git diff --exit-code`. If a PR changes a
  route without regenerating, CI fails. This is the requirement that makes the
  SDK worth having — a stale generated client is worse than none, because it
  looks authoritative.
- **Auth as a first-class client concern**: both clients accept either a JWT or a
  `ukip_` API key, and their READMEs document the scope model shipped in change
  1, including what a `403` means and how to widen a key.
- **A smoke test per client** exercising the real path an integrator takes:
  authenticate, list entities, handle a 403.

## Non-goals

- **Publishing to npm/PyPI.** Deliberate follow-up; requires deciding the public
  contract's version policy and holding registry credentials.
- **Migrating the frontend onto the generated TS client.** The frontend's
  `apiFetch` works and is used in hundreds of places; churning it is a large,
  independent refactor with no user-visible benefit. The generated client may be
  adopted incrementally later.
- **Hand-written ergonomics on top of the generated surface** (pagination
  helpers, retry policy, typed error hierarchy). Generate first, learn from real
  use, add sugar later — not speculatively.
- **Narrowing the exposed surface.** Every route in `openapi.json` is generated.
  Deciding which endpoints constitute a supported public contract versus an
  internal one is a product decision that deserves its own change; until then
  the README states plainly that the surface is generated wholesale and not all
  of it is a stability commitment.

## Impact

- New `sdk/` tree (generated code, committed).
- New `scripts/generate-sdk.mjs`.
- `backend/main.py` — `generate_unique_id_function` on the FastAPI app. This is
  the one change that touches running code, and it alters `openapi.json`
  operation IDs (not paths, not schemas, not behaviour).
- `.github/workflows/` — drift gate.
- `frontend/app/developer/page.tsx` — link the clients alongside the curl
  quickstart.
- `docs/API.md`, `sdk/README.md`.
- No migration. No database change. No endpoint behaviour change.
