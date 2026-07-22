# Design — API key scope enforcement

## Decision 1: method-derived scope, not per-endpoint declaration

**Considered:** annotate every endpoint with `Depends(require_scope("write"))`.

**Rejected because** it is ~400 edits across ~60 routers, and — decisively —
it is *fail-open*: a router added next sprint without the annotation is
unprotected, and nothing tells us. Security controls that depend on every
future author remembering something are controls that decay.

**Chosen:** a single derivation function applied inside the API-key branch of
the auth dependency. Every route is classified by construction; a route-
enumeration test asserts the classification is total.

```
scope_required(method, path) -> "read" | "write" | "admin"

  1. path matches an ADMIN_EXEMPT entry          -> skip rule 2
  2. path matches an ADMIN_PATH entry            -> "admin"
  3. (method, path) in READ_OVERRIDES            -> "read"
  4. method in {GET, HEAD, OPTIONS}              -> "read"
  5. otherwise                                   -> "write"
```

Rules are ordered; the admin table wins over the method rule, so a `GET /users`
is still admin-gated.

**Rule 1 was added during implementation.** Reviewing the real route table
surfaced a case the original four rules got wrong: `/users` is an admin surface,
but `/users/me`, `/users/me/password`, `/users/me/profile`, and
`/users/me/avatar` are *self-service* — every authenticated caller uses them.
Classifying them as admin would mean a read-scoped key could not read its own
profile. The exemption list is evaluated first and falls through to the method
rule. A test asserts every exemption sits under an admin path, so the list
cannot accumulate entries that exempt nothing.

The function lives in `backend/api_key_scopes.py` and takes two strings. No
`Request`, no `Session`, no FastAPI import — the entire truth table is unit
testable without a client.

## Decision 2: where the check runs

Inside `get_current_user` / `get_current_user_optional`, not in middleware.

Middleware runs before routing, so it sees the raw path but not the matched
route, and it cannot cheaply distinguish "this endpoint requires auth" from
"this endpoint is public" (`/embed/{token}/data`, `/health`, `/auth/token`).
The auth dependency already runs exactly when a credential is being resolved,
which is precisely the set of requests where a scope is meaningful.

FastAPI dependencies may declare `request: Request`, so the dependency can read
`request.method` and `request.url.path` without a signature change at any call
site.

**Path used for matching** is `request.scope["route"].path` when available (the
templated form, `/entities/{entity_id}`), falling back to `request.url.path`.
Matching the template avoids an ID that happens to contain `users` tripping the
admin table.

## Decision 3: hierarchy, and its interaction with RBAC

```
admin  ⊃  write  ⊃  read
```

`satisfies(granted: list[str], required: str) -> bool` expands each granted
scope to its implied set and tests membership. `["admin"]` alone is a valid
full-access key; the UI's three independent checkboxes remain valid input
(`["read","write"]` is simply redundant but harmless).

**Scope never elevates.** The dependency returns the same `User` it does today;
`require_role(...)` runs afterwards unchanged. The effective permission is the
*intersection* of the key's scope and the owner's role. Two invariants get
explicit tests:

- key `["admin"]` owned by a `viewer` → still 403 on an admin-role endpoint.
- key `["read"]` owned by a `super_admin` → 403 on a write endpoint.

## Decision 4: warn mode before enforce mode

`UKIP_API_KEY_SCOPES_ENFORCED` (`0` default).

Warn mode is not "logging for its own sake" — it is the only way to learn what
live integrations actually call before we start returning 403 to them. We do
not know today whether any external system holds a `read` key and writes with
it, and the failure mode of guessing wrong is a silently broken customer
integration.

Violations are written to the audit log (not only the app log) so the
observation window can be queried from the UI rather than by grepping container
output:

```
action: "api_key.scope_violation"
details: {key_prefix, method, path, required, granted, enforced: false}
```

Note `key_prefix` — never the key, never the hash.

The rollout task is explicitly *not* "flip the flag". It is: deploy at `0`,
observe ≥7 days, review `api_key.scope_violation` entries, contact owners of
any violating key, then flip.

## Decision 5: the admin-path table

Authoritative list lives in `backend/api_key_scopes.py`. Initial contents cover
the surfaces where a leaked "write" key would be catastrophic rather than
merely bad: user management, API keys themselves (a write key must not be able
to mint an admin key — privilege escalation), organizations/tenancy, store
credentials, platform auth settings, backup operations, data lifecycle purge,
workspace reset, and admin data fixes.

The exact prefixes are verified against `app.routes` during implementation; the
route-coverage test prints the full classification table so the mapping is
reviewable in CI output rather than assumed.

## Failure mode we are deliberately accepting

A `POST` that is genuinely read-only and not in `READ_OVERRIDES` will demand a
`write` key. This is safe (over-restriction, not under-restriction) and is
fixed by adding one line to the override registry when an integrator reports it.
The opposite default — treating unclassified `POST` as read — is not safe.
