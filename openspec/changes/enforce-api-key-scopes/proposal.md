# Enforce API key scopes

> **Priority: 1 of 3** (SDK / developer-surface track)
> **Depends on:** nothing. **Blocks:** `generate-openapi-clients` (the SDK must
> document an auth model that is actually true).

## Why

`POST /api-keys` accepts `scopes: ["read" | "write" | "admin"]`, persists them,
lists them back in the UI, and publishes a scope catalogue at
`GET /api-keys/scopes` with descriptions like *"Read — GET endpoints"* and
*"Write — mutating endpoints"*.

**No code anywhere reads that field for authorization.**

`backend/auth.py` resolves an API key to its owning `User` and returns it
(`get_current_user` lines 171–183, `get_current_user_optional` lines 215–223,
`ws.py` lines 57–58). From that point the request is indistinguishable from a
JWT session for that user. Concretely:

- A key created with `scopes: ["read"]` by an admin can `DELETE /entities/{id}`,
  rotate encryption keys, and create more API keys.
- The scope checkboxes in Settings → API Keys are a **false security control**:
  they tell an operator they have restricted a credential when they have not.
- There is no test asserting scope behaviour — `test_sprint81_82.py` covers
  creation, listing, revocation, and hash storage, but never a denial.

This is the classic "confused deputy" shape: the credential is weaker than the
principal it impersonates, but only on paper. It is the single blocking defect
on the developer surface — publishing an SDK (change 3) that documents scoped
keys would propagate the false promise to every integrator.

## What Changes

- **Derive the required scope from the request**, not from per-endpoint
  annotations: `GET`/`HEAD`/`OPTIONS` → `read`; `POST`/`PUT`/`PATCH`/`DELETE` →
  `write`; any path under an explicit **admin-path table** → `admin` regardless
  of method. One rule covers all ~60 routers and is **fail-closed** for routes
  added later.
- **Escalating hierarchy**: `admin` implies `write` implies `read`. A key
  holding `["admin"]` satisfies every requirement; `["read"]` satisfies only
  reads.
- **Override registry** for the handful of endpoints whose HTTP method
  misrepresents their effect (read-only `POST` search/NLQ endpoints), so we do
  not force integrators into `write` keys to run a query.
- **Never elevates**: the scope check is an *additional* gate, applied before
  the existing `require_role` RBAC. A key with `admin` scope owned by a `viewer`
  user still gets a viewer's permissions. Scope ∩ role, never scope ∪ role.
- **Two-phase rollout behind `UKIP_API_KEY_SCOPES_ENFORCED`** (default `0`):
  - *warn mode* (`0`): the request proceeds, but every would-be denial is logged
    at WARNING and written to the audit log as `api_key.scope_violation` with
    key prefix, method, path, required scope and granted scopes.
  - *enforce mode* (`1`): the same condition returns `403` naming the required
    scope.
  This lets us observe real prod traffic before breaking any live integration.
- **Route-coverage test**: enumerate every route on the app and assert each one
  resolves to a scope — a new router cannot silently land unclassified.
- Surface the effective flag in `GET /health` → `features`, and declare
  `UKIP_API_KEY_SCOPES_ENFORCED` in `docker-compose.prod.yml` (a code-read env
  var that is not declared in the prod compose file is a flag that does nothing
  — this has bitten us before).

## Non-goals

- Per-key rate limits or per-key tenant pinning.
- Reworking the RBAC role model.
- Retiring `admin` scope in favour of finer permissions — three scopes stay.
- Flipping the flag to `1` in production. That is an operator action taken after
  the warn-mode observation window, tracked in the rollout task, not shipped
  inside this change.

## Impact

- `backend/auth.py` — API-key branches of `get_current_user`,
  `get_current_user_optional`, and the `ws.py` handshake.
- New `backend/api_key_scopes.py` — pure scope-derivation logic (no DB, no
  FastAPI), so it is exhaustively unit-testable.
- `backend/main.py` — `/health.features`.
- `docker-compose.prod.yml`, `.env.example`, `docs/API.md`.
- No migration. No schema change. Existing keys keep the scopes they were
  created with; warn mode guarantees zero behaviour change on deploy.
