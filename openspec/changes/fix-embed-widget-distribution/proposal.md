# Fix embed widget distribution

> **Priority: 2 of 3** (SDK / developer-surface track)
> **Depends on:** nothing (independent of change 1; sequenced after it because
> change 1 is a security defect and this is a functional one).
> **Blocks:** nothing.

## Why

Sprint 93 shipped an "Embeddable Widget SDK". The CRUD works, the tenant
isolation is correct (EPIC-012 scoped the public data path), and the Next.js
render page at `/embed/[token]` exists and is well built.

**The distribution path — the part a customer actually copies and pastes — is
broken in three independent ways, and none of them is covered by a test.**

1. **The iframe points at a route that does not exist.**
   `GET /embed/{token}/snippet` emits `<iframe src="{api}/embed/{token}/frame">`
   ([widgets.py:379](../../../backend/routers/widgets.py)). There is no `/frame`
   route on the backend — the renderer is the *frontend* page. Every iframe
   snippet we have ever handed out 404s.

2. **Both snippets hardcode `http://localhost:8000`.**
   `api_base = "http://localhost:8000"` with the comment *"consumers replace
   with their deployed URL"*. In production the API is
   `api.ukip.inbounduxd.com`, so every snippet is born pointing at the
   customer's own machine. A "ready-to-paste" snippet that must be hand-edited
   to work is not ready to paste, and the comment is an admission that we knew.

3. **Framing is forbidden globally, so the iframe could never have worked.**
   `frontend/next.config.ts` sets `X-Frame-Options: DENY` and CSP
   `frame-ancestors 'none'` for **all** routes — including `/embed/[token]`,
   whose own source comment reads *"consumer sites can iframe this URL
   directly"*. The security header and the product intent contradict each other,
   and the header wins.

Additionally the JS snippet's "render" is `'<pre>' + JSON.stringify(...) +
'</pre>'` — a debug dump, not a widget. That is the artifact we ask a customer
to put on their site.

The net effect: the embeddable-widget feature is not embeddable. It has 244
lines of tests (`test_sprint93.py`) that cover CRUD and the data providers, and
zero that assert a snippet is usable.

## What Changes

- **Resolve base URLs from configuration**, never hardcoded:
  - API base from `UKIP_PUBLIC_API_URL`, falling back to the request's own
    origin (`request.base_url`) so a correct value exists even unconfigured.
  - App base from the existing `FRONTEND_URL` (already declared in
    `docker-compose.prod.yml` and `.env.example` — no new prod plumbing).
- **Point the iframe at the page that actually renders**:
  `{FRONTEND_URL}/embed/{token}`. Delete the fictional `/frame` path.
- **Scope the framing headers**: `/embed/*` opts out of the global
  `X-Frame-Options: DENY` and gets `frame-ancestors` derived from the widget's
  own `allowed_origins`, so a widget restricted to `https://cliente.com` can
  only be framed by that origin, and a `*` widget can be framed anywhere. The
  rest of the app keeps `DENY` unchanged.
- **Make the JS snippet render something presentable** — a labelled value list
  per widget type instead of a JSON dump.
- **Test the contract**: snippets contain no `localhost` when configured, the
  iframe URL resolves to a real route, and the frame headers permit exactly the
  configured origins.

## Non-goals

- **Turning `allowed_origins` into an authentication boundary.** It is not one
  and this change does not pretend otherwise: the `Origin` header is set by
  browsers and trivially omitted or forged by a direct HTTP client, so
  `GET /embed/{token}/data` remains readable by anyone holding the token. The
  token *is* the credential. This change documents that explicitly in
  `docs/API.md` and in the widget UI rather than leaving operators to infer a
  protection that does not exist. Real per-origin enforcement would require
  signed, short-lived embed tokens — a separate change if a customer needs it.
- A JS embed library published to a CDN. The snippet stays dependency-free and
  inline.
- New widget types beyond the existing four.

## Impact

- `backend/routers/widgets.py` — `embed_snippet` only; the data path is
  untouched.
- `frontend/next.config.ts` — per-path header rules.
- `backend/tests/test_sprint93.py` (or a new `test_embed_distribution.py`).
- `.env.example`, `docker-compose.prod.yml` (`UKIP_PUBLIC_API_URL`),
  `docs/API.md`.
- No migration. No model change. No change to any authenticated endpoint.
