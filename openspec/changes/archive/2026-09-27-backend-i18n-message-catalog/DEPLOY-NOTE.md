# Deploy note — backend i18n (#209)

Everything in this change is internal except one thing, and it is the only item
on this page that reaches someone outside the organisation.

## The password-reset email changes language

**Before:** every recipient got a Spanish subject and body, regardless of who
they were.

```
Subject: UKIP: recupera tu contraseña
```

**After:** the text comes from the catalog in the language the request resolved
— explicit `?language=` parameter, then `Accept-Language`, then English.

```
Subject: UKIP: reset your password        (default, and for English requesters)
Subject: UKIP: recupera tu contraseña     (Spanish requesters — unchanged for them)
```

### Who is affected

Anyone who requests a password reset **without** a Spanish language signal now
receives English where they previously received Spanish. Spanish-speaking users
are unaffected: they keep the exact wording they had.

### Why this is safe to ship

Nothing in the product depends on the current Spanish text — confirmed with the
product owner on 2026-07-31. There is no mail filter, no automated parser and no
support macro keyed to the subject line.

### What to watch after deploy

- **Support tickets about "the email came in the wrong language."** The most
  likely cause is a client that sends no `Accept-Language`; the fix is for the
  frontend to pass `?language=` explicitly, which it already can.
- **Nothing else.** Delivery, tokens, expiry (30 minutes) and the reset link are
  untouched.

### Rollback

Revert the phase 7 commit. The catalog keys can stay — they are inert without
the call site.

## Not outward-facing, but worth knowing

- `POST /agentic-chat/query`, `GET /assistant/actions` and
  `POST /auth/password-reset/request` gained an optional `language` query
  parameter and read `Accept-Language`. Existing callers are unaffected: omitting
  both yields the previous default for reports and English elsewhere.
- `sdk/openapi.json` and both generated SDK clients changed accordingly.
- Operators who read the agentic chat in English now get English replies instead
  of Spanish ones. That is the defect #209 reported, on a different surface.
