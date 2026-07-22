# Tasks — fix embed widget distribution

TDD throughout. Note that tasks 1–3 each start from a test that fails against
today's code — all three defects are currently unguarded.

## 0. URL resolution

- [ ] 0.1 Failing test: generated snippets contain no `localhost` when
      `UKIP_PUBLIC_API_URL` and `FRONTEND_URL` are set. (RED — both are
      hardcoded today.)
- [ ] 0.2 `_resolve_bases(request) -> (api_base, app_base)` in `widgets.py`:
      env first, `request.base_url` fallback for the API, single trailing-slash
      normalization.
- [ ] 0.3 Tests: env set; env unset → request origin; trailing slash on either
      input produces no doubled separator.

## 1. Iframe target

- [ ] 1.1 Failing test: the iframe `src` path resolves to a real application
      route. (RED — `/frame` does not exist.)
- [ ] 1.2 Point the iframe at `{app_base}/embed/{token}`; delete `/frame`.
- [ ] 1.3 Test: snippet contains no `/frame`.

## 2. Framing headers

- [ ] 2.1 Failing test: a response from `/embed/...` does not carry
      `X-Frame-Options: DENY`. (RED — `next.config.ts` applies it to `/(.*)`.)
- [ ] 2.2 Split `next.config.ts` headers into `/embed/:path*` and a catch-all;
      omit `X-Frame-Options` on the embed rule and set a permissive
      `frame-ancestors` floor. Every other directive stays identical.
- [ ] 2.3 Emit the per-widget `frame-ancestors` at request time from the embed
      route, derived from the widget's `allowed_origins`.
- [ ] 2.4 Tests: restricted widget → exactly its origins; `*` widget → any;
      a non-embed route still `DENY` + `'none'` (regression — this must not
      loosen the app).

## 3. Snippet rendering

- [ ] 3.1 Replace the `<pre>JSON.stringify(...)</pre>` body with an inline
      labelled renderer per widget type. Dependency-free, no external assets.
- [ ] 3.2 Tests: no raw serialization in the emitted snippet; no external
      `src`/`href`.

## 4. Config, docs, verification

- [ ] 4.1 Declare `UKIP_PUBLIC_API_URL` in `docker-compose.prod.yml` **and**
      `.env.example`. (`FRONTEND_URL` is already in both — confirm, do not
      duplicate.)
- [ ] 4.2 `docs/API.md`: the embed contract, both snippet forms, and an explicit
      statement that the token is the credential and `allowed_origins` governs
      framing, not data retrieval.
- [ ] 4.3 Widget settings UI: same clarification next to the `allowed_origins`
      field, so the operator reads it where the decision is made.
- [ ] 4.4 Live check: create a widget, paste both snippets into a scratch HTML
      page, confirm the iframe renders and the JS snippet populates. This is a
      copy-paste feature — it is not done until something was actually pasted.
- [ ] 4.5 Full backend suite + frontend suite. Remember `rm -rf frontend/.next`
      before pushing if a dev server ran (corrupt generated types break the
      pre-push tsc gate).
- [ ] 4.6 PR.
