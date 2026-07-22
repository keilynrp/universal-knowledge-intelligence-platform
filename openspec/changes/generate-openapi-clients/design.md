# Design — generated API clients

## Decision 1: generated, not hand-written

A hand-written client over ~60 routers is a second implementation of the API
that drifts from the first. Generation makes drift *detectable* (see decision 4)
rather than merely regrettable.

The cost of generation is ergonomics: generated method names and error types are
mechanical. We accept that for the first cut and add sugar only where real usage
demands it — speculative wrappers are how SDKs become their own maintenance
burden.

## Decision 2: operation IDs must be stabilized first

This is a genuine prerequisite, not polish.

FastAPI's default `operationId` is `{function_name}_{path}_{method}`, so
`create_widget` in `widgets.py` becomes `create_widget_widgets_post`, and the
generated TS method is `createWidgetWidgetsPost`. Two consequences:

- The public SDK surface is ugly in a way we would want to fix later, and fixing
  it later is a breaking change for every consumer.
- **Renaming a private Python function renames a public SDK method.** Internal
  refactors become external breakage with no signal.

So: install `generate_unique_id_function` on the app producing
`{tag}_{route_name}`, and add a test pinning the operation IDs of a
representative sample. The names become an intentional interface rather than a
byproduct of implementation detail.

Ordering matters: doing this after generating clients means regenerating and
breaking every name once. Do it first.

## Decision 3: dump the spec without booting a server

```
python -c "import json; from backend.main import app; print(json.dumps(app.openapi()))"
```

`app.openapi()` is pure — no port, no database, no lifespan. This matters for
the CI gate: the drift check must be cheap and must not depend on a healthy
runtime. (Recall that CI deliberately skips real startup.)

`scripts/generate-sdk.mjs` writes `sdk/openapi.json`, then invokes both
generators against that file. The committed `sdk/openapi.json` is itself part of
the diff surface, so a spec change is visible in review even before looking at
generated code.

## Decision 4: the drift gate is the actual deliverable

A generated client that anyone can forget to regenerate is a client that will be
wrong, while looking authoritative. The gate:

```
node scripts/generate-sdk.mjs
git diff --exit-code sdk/
```

If a PR touches a route and does not regenerate, CI fails with the diff. The
failure message tells the author to run the script.

Generators must be **version-pinned** in `package.json`, or a generator release
produces phantom diffs on unrelated PRs and the team learns to ignore a red
gate — which defeats it entirely.

## Decision 5: committed generated code

Generated output is committed rather than built on demand:

- an integrator can read the client on GitHub without running our toolchain;
- `git diff` on a PR shows exactly how the public surface changed, which is
  review signal we do not otherwise have;
- the drift gate needs a committed baseline to diff against.

The cost is a large mechanical diff on schema changes. That cost *is* the
signal.

## Decision 6: auth shape

Both clients take a single credential and send `Authorization: Bearer <token>`,
because the backend already accepts a JWT or a `ukip_` key on the same header
(`auth.py` branches on the `ukip_` prefix). No separate API-key parameter — one
constructor argument, two credential kinds.

The READMEs document, from change 1: the three scopes, the derivation rule
(safe methods need `read`, mutations need `write`, admin surfaces need `admin`),
the hierarchy, and that a `403` naming a scope means the key is too narrow —
not that the user lacks permission. That distinction is invisible from the wire
and is exactly what an SDK should explain.

## Decision 7: smoke tests, not generated-code tests

Testing generated code is testing the generator. The two smoke tests instead
assert the integration seam:

1. construct client → authenticate → list entities → typed result;
2. call a write endpoint with a read-scoped key → the error surfaces as a
   distinguishable 403.

Both run against the FastAPI app in-process, so they need no deployment.

Test 2 is deliberately the cross-check on change 1: if scope enforcement
regresses, an SDK test fails.
