# Coauthorship V2 — production cutover runbook

The V2 code ships **inert**: `COAUTHOR_V2_WRITE` / `COAUTHOR_V2_READ` default
**OFF**, so deploying changes nothing — the legacy coauthorship path keeps
serving. Cutover is a deliberate, ops-controlled opt-in.

## 0. Deploy (automatic)
Merging to `main` triggers the `deploy` job in `.github/workflows/docker.yml`.
On startup the app auto-creates the 8 V2 tables (`Base.metadata.create_all`,
idempotent) — empty. No behavior change yet (flags off).

Confirm the new image is live and `pip install -r requirements.txt` pulled
`python-louvain` + `networkx`.

## 1. Backfill V2 tables from existing data
Run **once** against the production DB. Idempotent and additive — does not
touch legacy `entity_relationships`.

Option A — shell on the prod host:
```
python -m backend.scripts.migrate_coauthor_graph --dry-run   # audit counts
python -m backend.scripts.migrate_coauthor_graph             # apply
```

Option B — admin HTTP endpoint (no shell needed):
```
curl -X POST https://<prod-host>/admin/data-fixes/migrate-coauthor-graph \
     -H "Authorization: Bearer <PROD_ADMIN_JWT>" \
     -H "Content-Type: application/json" -d '{"dry_run": true}'   # audit
# then dry_run:false to apply
```

The migration also seeds the merge-suggestion review queue.

## 2. Verify
```
curl -H "Authorization: Bearer <PROD_ADMIN_JWT>" \
     https://<prod-host>/analyzers/coauthorship/<domain>/diagnostics
```
Success = `edges_after_scope` equals `edges_in_storage` (the original bug was
these diverging) and `authors_total > 0`. `coverage_pct` < 100 is normal — it's
multi-author entities ÷ all domain entities, not a failure signal.

## 3. Flip the flags ON
Set in the production environment and restart:
```
COAUTHOR_V2_WRITE=true
COAUTHOR_V2_READ=true
```
Now the worker materializes V2 on every enrichment and the endpoints serve from
the V2 tables. Open `/analytics/coauthorship` (pick a domain that has
multi-author data) and confirm the graph renders.

## Rollback
Set `COAUTHOR_V2_READ=false` (and/or `COAUTHOR_V2_WRITE=false`) in the prod env
and restart — instant fallback to the legacy path, no redeploy. V2 tables are
left intact for a later retry.

## Later (post-soak)
Once V2 has served stably with `coverage_pct` as expected: run
`backend/scripts/cleanup_legacy_coauthor.py` to drop legacy `CO_AUTHOR` rows,
then the F5.2 follow-up removes the flags + legacy code and tags the release.
