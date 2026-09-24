# Design — attribute every request, audit the reads that matter

## Decision 1: resolve the principal once, in the auth dependency

**Considered:** decode identity in each middleware, as `AuditMiddleware` does
today (`_decode_username` parses the bearer token as a JWT).

**Rejected because** that shortcut is wrong in two ways the tabletop's scenario
cares about:

- an API key is not a JWT, so mutations made with a key are audited with no
  identity at all;
- decoding checks the signature and expiry, not the session, so a token whose
  session was revoked (#381) still names a user, and a request authentication
  refused is attributed as if it had been accepted.

Resolving an API key in middleware would also cost a database query per
request, which #376 explicitly rules out.

**Chosen:** `get_current_user` and `get_current_user_optional` already resolve
the acting identity on every authenticated request, through exactly the checks
that decide whether the request proceeds. After a successful resolution they
record it:

```python
request.state.principal = Principal(
    user_id=user.id,
    session_id=sid,          # JWT path; None for API keys
    api_key_id=key.id,       # API-key path; None for JWTs
)
```

`Principal` is a frozen dataclass in `backend/principal.py` with no username:
the id is enough to join, and the request log should not carry more personal
data than it needs. Nothing is recorded when authentication fails, so a
middleware that finds no principal knows the request was anonymous or refused.

**Verification point.** Starlette's `BaseHTTPMiddleware` and the endpoint's
`Request` should share the ASGI scope, where `request.state` lives. Nothing in
the codebase relies on that yet: `RequestLoggingMiddleware` sets
`request.state.request_id`, but nothing downstream reads it. So the first task
is a test showing that a principal set in a dependency is visible to both
middlewares after `call_next`. If it is not, the fallback is a mutable holder
that the outermost middleware places in `request.state` *before* `call_next`
and the dependency fills in. Even if the state mapping were copied, both
sides would keep a reference to the same holder. A `ContextVar` would not work
here: `BaseHTTPMiddleware` runs the app in a child task, and a value set there
does not propagate back to the middleware.

## Decision 2: the request log carries ids, not names (#376)

`request_completed` and `request_failed` gain `user_id`, and `session_id` or
`api_key_id`, **only when a principal exists**. The fields are absent, not
`null`, for anonymous and refused requests. A log reader filtering on
`user_id` should never match a line whose identity was a placeholder.

`session_id` is the opaque `sid` from `user_sessions`. It is not a credential:
it is useless without the signed token that carries it, and it is already shown
to the account owner in the sessions list. With it, a responder can go from a
log line to one session, and the #381 containment can stop exactly that
session.

Never logged: the token, the key, any header value, any request body, any query
value.

## Decision 3: audit rows carry the principal too

Migration adds two columns to `audit_logs`:

| Column | Type | Index | Why |
|---|---|---|---|
| `session_id` | `String(64)`, nullable | yes | pivot "everything this session did" |
| `api_key_id` | `Integer`, nullable, no FK | no | a key can be deleted; the evidence must survive it |

`user_id` already exists and has only ever been set by the assistant-action
endpoint. The middleware now fills all three from the principal, and keeps
writing `username` (resolved from `user_id` at write time) so existing readers
of the log and of the CSV keep working.

`api_key_id` deliberately has no foreign key. `audit_logs` is retained
indefinitely, and a row must not block or be removed by deleting the key it
names.

## Decision 4: audit reads by class, not blanket (#375)

A classification function in `backend/read_audit.py`, pure like
`api_key_scopes.py` (strings in, a class or `None` out):

```
read_audit_class(method, route_template, query, principal) -> "EXPORT" | "READ" | None

  1. method not in {GET, HEAD}                     -> None (mutations stay as today)
  2. no principal                                  -> None (nothing to attribute; the request log has it)
  3. route_template in EXPORT_ROUTES               -> "EXPORT"
  4. route_template starts with /audit-log         -> "READ"   (reading the evidence is evidence)
  5. principal.api_key_id is not None              -> "READ"   (programmatic access)
  6. skip > 0  or  limit > 500                     -> "READ"   (bulk / sweep)
  7. otherwise                                     -> None
```

**`EXPORT_ROUTES` is an explicit table**, not a substring match on "export". A
route-coverage test enumerates every `GET` route on the app and fails when a
template containing `export`, `download` or `csv`, or returning a
file-streaming response class, is not in the table or on a short, commented
exclusion list. This follows the route-coverage test in
`enforce-api-key-scopes`: a new export cannot land unaudited silently.

**Class 6 thresholds come from what the UI actually requests.** Views ask for
pages of 20–50. One dashboard widget loads `/entities?limit=500` on every
render, and two entity-detail panels ask for 200. So `limit > 500` stays out of
ordinary browsing. `skip > 0` catches a sweep regardless of page size. The
tabletop's ~600 reads were exactly that pattern. It also records a person
paging to page 2 of a table, which is rare enough to accept.

**The row** is written after the response, best-effort like mutations:
`action = READ | EXPORT`, `endpoint` = route template, `method`, `status_code`,
`ip_address`, the principal columns, and `details = {"limit": …, "skip": …,
"query_keys": [...]}`. Only query **names** are kept, never values. A search
term about a person is exactly what an access log must not become.

Denied reads (`401`, `403`) of classified routes are recorded when a principal
exists. A `403` means an authenticated credential tried something outside its
scope, which is evidence.

## Decision 5: the audit log pivots on a session

`GET /audit-log`, `/export` and `/stats` gain `session_id`, beside
`ip_address` (#384), with the same shared-description pattern. The action
filter gains `READ` and `EXPORT`. The sessions list (#383) links each session
to `/audit-log` filtered by it, so the route from "this device is not mine" to
"this is what it did" is one tap.

## Open questions for the owner

These have working defaults, so implementation is not blocked. They are policy,
not engineering:

1. **Retention of `READ`/`EXPORT` rows.** Default: the same as mutations
   (indefinite), and measure the volume for 30 days before deciding otherwise.
   A shorter window (for example 13 months) is defensible for reads, and would
   need a purge path, since `audit_logs` has none today.
2. **Class 6 breadth.** The default above. If the 30-day volume is small,
   widening to every authenticated `GET` removes the "reads outside the classes"
   residual entirely, which would be the simplest thing to explain in a
   notification.
3. **DPA wording.** §5 lists "attributable request logs" as open. Once this
   ships, confirm how the DPA should describe read logging to customers.

## Risks

- **Latency:** one synchronous insert per audited read. Mutations already pay
  this. Classes 1–5 are low volume, and class 6 is bounded by the thresholds.
- **Scope-state sharing (Decision 1):** if a future Starlette change stopped
  `request.state` crossing the middleware boundary, attribution would silently
  disappear. The verification test is the guard: it fails rather than letting
  the fields quietly go missing.
- **Double writing on exports that are also `POST`s:** a mutating export is
  audited once, as today, by the mutation path. Rule 1 makes the read path
  ignore it.
