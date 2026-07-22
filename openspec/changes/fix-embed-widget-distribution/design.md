# Design — embed widget distribution

## Decision 1: two base URLs, from two sources

The snippet needs both:

| Snippet | Target | Source |
|---|---|---|
| iframe | the **frontend** render page | `FRONTEND_URL` |
| JS | the **backend** JSON endpoint | `UKIP_PUBLIC_API_URL` |

`FRONTEND_URL` already exists, is read by `auth_users.py`, and is declared in
`docker-compose.prod.yml:47` and `.env.example:95`. Reusing it costs nothing and
keeps one canonical answer to "where does the app live".

`UKIP_PUBLIC_API_URL` is new on the backend. Rather than making it mandatory,
the resolver falls back to `str(request.base_url)`:

```
api_base = env("UKIP_PUBLIC_API_URL") or str(request.base_url).rstrip("/")
```

**Why a fallback and not just `request.base_url`?** Behind a reverse proxy,
`base_url` reflects what the proxy forwarded, which is correct only when
`--proxy-headers` and `X-Forwarded-*` are configured end to end. We do not want
snippet correctness silently coupled to proxy configuration, so an explicit
override wins when present. **Why not require the env var?** Because the failure
mode of an unset variable should be "probably right" (the origin the request
actually arrived on), not "definitely wrong" (`localhost`). Both are declared in
prod compose regardless — an env var read by code but absent from
`docker-compose.prod.yml` is a dead flag.

Trailing slashes are normalized once, in the resolver, not at each use site.

## Decision 2: the iframe points at the frontend, and `/frame` is deleted

`/embed/{token}/frame` was never implemented. Two ways to fix it:

- **(a) point at `{FRONTEND_URL}/embed/{token}`** — the React page already
  exists, already fetches `/embed/{token}/data`, and already renders all four
  widget types with real styling.
- (b) implement a server-rendered HTML `/frame` route on the backend.

Chosen (a). Option (b) means a second renderer for the same four widget types,
in a different language, that will drift from the first one. The page we already
built is the renderer.

## Decision 3: framing headers become per-path

Today `frontend/next.config.ts` applies to `/(.*)`:

```
X-Frame-Options: DENY
Content-Security-Policy: ... frame-ancestors 'none'
```

`X-Frame-Options` has no origin-list semantics worth using (`ALLOW-FROM` is
dead in every modern browser), so the mechanism is CSP `frame-ancestors`, and
`X-Frame-Options` must be **absent** on embed routes — present-and-`DENY` is
honoured by browsers that would otherwise respect the CSP.

Split the header config into two rules:

| Path | `X-Frame-Options` | `frame-ancestors` |
|---|---|---|
| `/embed/:path*` | *(omitted)* | per-widget (see below) |
| everything else | `DENY` | `'none'` |

Everything else in the CSP (script-src, connect-src, …) stays identical on both
rules; only the framing directives differ.

**Per-widget ancestors.** `next.config.ts` headers are static, so a widget whose
`allowed_origins` is `https://cliente.com` cannot get a tailored static header.
The embed page therefore emits the widget-specific `frame-ancestors` at request
time from its own route handler, using the `allowed_origins` returned by
`/embed/{token}/config`:

- `allowed_origins == "*"` → `frame-ancestors *`
- otherwise → `frame-ancestors <origin list>`

The static rule for `/embed/:path*` is the permissive floor (it must not say
`'none'`, or the dynamic header is moot); the dynamic header narrows it.

Note the honest limitation: `frame-ancestors` restricts *framing*, which
protects against clickjacking and unwanted display. It does not restrict
*reading* `/embed/{token}/data` with curl. See the non-goal in the proposal.

## Decision 4: the JS snippet renders, minimally

Replacing `<pre>{json}</pre>` with a small inline renderer — a heading and a
definition list of the widget's headline numbers — keeps the snippet
dependency-free and under ~25 lines while producing something a customer can
actually put on a page. Anything richer belongs in the iframe path, which is why
the iframe exists.

## What we are explicitly not fixing here

`_get_active_widget` looks up by `public_token` with no rate limiting, so the
token space is enumerable in principle (UUID4 — 122 bits, not realistically
enumerable, but unthrottled). Out of scope; noted for the record.
