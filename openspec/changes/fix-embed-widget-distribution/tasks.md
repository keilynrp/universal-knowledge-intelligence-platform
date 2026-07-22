# Tasks — fix embed widget distribution

TDD throughout. Note that tasks 1–3 each start from a test that fails against
today's code — all three defects are currently unguarded.

## 0. URL resolution

- [x] 0.1 Failing test: generated snippets contain no `localhost` when
      `UKIP_PUBLIC_API_URL` and `FRONTEND_URL` are set. (RED — both are
      hardcoded today.)
- [x] 0.2 `_resolve_bases(request) -> (api_base, app_base)` in `widgets.py`:
      env first, `request.base_url` fallback for the API, single trailing-slash
      normalization.
- [x] 0.3 Tests: env set; env unset → request origin; trailing slash on either
      input produces no doubled separator.

## 1. Iframe target

- [x] 1.1 Failing test: the iframe `src` path resolves to a real application
      route. (RED — `/frame` does not exist.)
- [x] 1.2 Point the iframe at `{app_base}/embed/{token}`; delete `/frame`.
- [x] 1.3 Test: snippet contains no `/frame`.

## 2. Framing headers

- [x] 2.1 Failing test: a response from `/embed/...` does not carry
      `X-Frame-Options: DENY`. (RED — `next.config.ts` applies it to `/(.*)`.)
- [x] 2.2 Split `next.config.ts` headers into `/embed/:path*` and a catch-all;
      omit `X-Frame-Options` on the embed rule and set a permissive
      `frame-ancestors` floor. Every other directive stays identical.
- [x] 2.3 Emit the per-widget `frame-ancestors` at request time from the embed
      route, derived from the widget's `allowed_origins`.
- [x] 2.4 Tests: restricted widget → exactly its origins; `*` widget → any;
      a non-embed route still `DENY` + `'none'` (regression — this must not
      loosen the app).

## 3. Snippet rendering

- [x] 3.1 Replace the `<pre>JSON.stringify(...)</pre>` body with an inline
      labelled renderer per widget type. Dependency-free, no external assets.
- [x] 3.2 Tests: no raw serialization in the emitted snippet; no external
      `src`/`href`.

## 4. Config, docs, verification

- [x] 4.1 Declare `UKIP_PUBLIC_API_URL` in `docker-compose.prod.yml` **and**
      `.env.example`. (`FRONTEND_URL` is already in both — confirm, do not
      duplicate.)
- [x] 4.2 `docs/API.md`: the embed contract, both snippet forms, and an explicit
      statement that the token is the credential and `allowed_origins` governs
      framing, not data retrieval.
- [x] 4.3 Widget settings UI: same clarification next to the `allowed_origins`
      field, so the operator reads it where the decision is made.
- [~] 4.4 Live check — done in parts, one gap remains. Verified live on the dev
      server: header split (/login keeps DENY+'none'; /embed drops
      X-Frame-Options; fail-closed 'none' with backend down; per-widget
      `frame-ancestors https://cliente.example.com` with a mock config API).
      NOT yet done: pasting both snippets into a scratch page against a real
      backend+widget (needs the WSL Postgres live-test setup). Do this during
      PR review or before the flag ships to prod.
- [x] 4.5 Full backend suite: 3311 passed / 7 skipped. Frontend: 302 passed, tsc clean. (`rm -rf frontend/.next`
      before pushing if a dev server ran (corrupt generated types break the
      pre-push tsc gate).
- [ ] 4.6 PR.
