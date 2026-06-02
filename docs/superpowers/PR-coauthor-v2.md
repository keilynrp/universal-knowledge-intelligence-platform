# Coauthorship V2: drastic refactor (first-class graph + GraphDB UI)

## Why

`/analytics/coauthorship` was broken: clicking **Regenerar red de coautoría**
reported success ("351 entidades, 7847 colaboraciones") but the graph panel
**never populated**.

**Root cause — tenancy-scope asymmetry.** Co-author edges were stored
parasitically as `entity_relationships(relation_type='CO_AUTHOR', notes='A||B')`
with `er.org_id = entity.org_id`, while the reader filtered by the
request-resolved `org_id`. Legacy rows written with `NULL` org never matched the
resolved scope, so **every edge was discarded at read time** — storage looked
full, the panel stayed empty.

Rather than patch the scope filter, this replaces the parasitic storage with a
first-class, materialized coauthorship graph and rebuilds the UI in the
GraphDB/Neo4j-Bloom visual style.

## What changed

### Data model (5 first-class tables + audit/queue)
`authors`, `author_publications`, `coauthor_edges`, `author_stats`,
`coauthor_dirty_scopes`, `coauthor_contributions`, `author_merge_suggestions`,
`author_merge_audit`.
- **`org_id = 0` sentinel** for legacy/global scope (not `NULL`) so compound
  primary keys enforce uniqueness portably on SQLite **and** Postgres.
- Idempotent weight accounting: one `(entity, author_a, author_b)` triple
  contributes **exactly +1** to an edge, via the `coauthor_contributions` log.

### Deterministic hybrid identity
- `name_key` canonicalizer (NFD diacritic strip + NFC recompose, title/suffix
  removal, particle handling, `last_first` form, **Han/Hangul surname-first**).
  163-case golden file.
- 3-tier `classify_merge` (strong / probable / ambiguous / distinct). ORCID is
  authoritative. **Identity model = optimistic collapse + ORCID override**
  (`name_key` UNIQUE): same-name surfaces collapse; near-miss pairs
  (`smith_j` ↔ `smith_john`) are **queued for human review, never auto-merged**
  — the architect's C3 concern.
- `get_or_create_author` (race-safe upsert), `merge_authors` (repoint + audit),
  and a **producer** that scans authors and fills the review queue.

### Worker materialization
- `write_coauthor_artifacts` hook (flag-gated) runs **after** the enrichment
  commit, isolated so a coauthor failure can never roll back enrichment.
- `recompute_coauthor_stats` via **python-louvain** (community detection ≥50
  nodes; connected components below) with a **safety cap** (>3000 nodes / 25k
  edges → connected-components fallback) so a pathological scope can't stall the
  worker. A 30s-debounced dispatcher drains `coauthor_dirty_scopes`.

### API (new `backend/routers/coauthorship.py`)
- `GET /analyzers/coauthorship/{domain}` — V2 reader (behind `COAUTHOR_V2_READ`,
  legacy fall-through when off). `_scope_org_id` translates the tenant sentinel
  `-1` → V2 `0` — the fix that prevents reintroducing the original bug.
- `GET …/{domain}/author/{id}` — detail (metrics, collaborators, publications).
- `GET …/{domain}/diagnostics` — pipeline counters (storage → scope → coverage).
- `POST …/{domain}/recompute` — admin, 30s/scope rate-limited.
- `GET/POST /coauthorship/merge-suggestions[/generate|/{id}/confirm|/reject]`.
- `POST /admin/data-fixes/migrate-coauthor-graph` + `migrate_coauthor_graph` CLI.

### Frontend rebuild (GraphDB look)
- `NetworkGraph` rewrite: cubic-Bézier edges (width `log(weight+1)·1.5`, weight
  labels when zoomed), OKLCH community palette, radius by publication count,
  hover-dim neighbors, keyboard neighbor cycling, reduced-motion aware.
- `NodePropertiesPanel` (Neo4j-Bloom side panel), `GraphControls` (search /
  min-weight / community chips), `MergeSuggestionsPanel` (admin review).
- Page simplified to compose these; consumes `computed_at` / `stale` /
  `coverage_pct`; old backfill button + client-side derived state removed.

## Rollout (flag-gated, reversible)

`COAUTHOR_V2_WRITE` and `COAUTHOR_V2_READ` now **default ON**; legacy code and
the flags are **retained one release** as a safety net (set the env vars `false`
to roll back with no redeploy). Tests pin the flags **off** so suites stay
deterministic and opt in per-case.

**⚠️ Required at deploy:** run the migration once to backfill V2 tables, then
watch `/diagnostics`:
```
python -m backend.scripts.migrate_coauthor_graph --dry-run   # audit
python -m backend.scripts.migrate_coauthor_graph             # apply
```

A follow-up (post-soak) removes the flags + legacy paths and tags the release.

## Decisions worth a reviewer's eye

- **Identity model = optimistic collapse (Plan B), not full same-name splitting**
  — keeps `name_key`/`orcid` UNIQUE. Distinct same-name authors without ORCID
  can conflate; accepted for current corpus size, full splitting deferred.
- **Perf gate re-calibrated (spec §12.3 waiver).** python-louvain can't hit the
  original 100k-edge/<10s target (~14–18s; scales with node count). Replaced by
  a realistic gate — 2,000 nodes / ~14k edges < 5s (measured 1.7s) — plus the
  safety cap. `leidenalg`/`igraph` is the documented upgrade path.

## Verification

- **Backend regression:** 2382 passed / 7 skipped / 0 failed.
- **Coauthorship suite:** 262 passed (schema, identity, classifier, recompute +
  perf gate, worker hook, migration, V2 reader/author/diagnostics, merge API,
  producer, legacy cleanup).
- **Live end-to-end on a real DB** (domain `science`): migration created 474
  authors / 806 publications / 2,671 edges; recompute → 51 communities in
  962 ms; **`edges_in_storage == edges_after_scope == 2671`** (bug fixed); HTTP
  smoke test of the reader / author / diagnostics endpoints all green.
- `tsc --noEmit` + `eslint` clean on all new frontend files.

## Test plan

- [ ] CI green on the full backend suite.
- [ ] `pnpm playwright test e2e/coauthorship.spec.ts` (mocked V2 endpoints).
- [ ] Bootstrap visual baselines once: `pnpm playwright test
      e2e/network_graph_visual.spec.ts --update-snapshots`, then commit.
- [ ] On a prod replica: `migrate_coauthor_graph --dry-run`, confirm
      `name_key` collapse + edge counts look sane.
- [ ] Manual smoke: `/analytics/coauthorship` (domain with multi-author data)
      shows a populated graph for super_admin, admin (real org), and viewer.
- [ ] `/diagnostics` shows `edges_after_scope > 0` for every role that sees a
      populated graph.

## Out of scope / follow-ups

- F5.2 full: delete flags + legacy analyzer/backfill/admin endpoint + ~24 legacy
  bibliometric tests, then tag `coauthor-v2-cleanup` (after a production soak).
- `leidenalg`/`igraph` swap if a single scope routinely exceeds the Louvain cap.
- Plan A (true same-name splitting) if author-disambiguation accuracy becomes a
  headline feature.
- Polars integration (explicitly deferred to a separate sprint).
