# Co-authorship Module — Drastic Refactor Design

- **Date:** 2026-05-28
- **Author:** UKIP team (brainstormed with Claude)
- **Status:** Approved for planning
- **Scope:** Backend + frontend rebuild of `/analytics/coauthorship`
- **Supersedes:** `EntityRelationship(relation_type='CO_AUTHOR', notes='A||B')` storage, `backfill_coauthor_edges.py`, on-demand compute in `backend/analyzers/coauthorship.py`

---

## 1. Problem statement

The current co-authorship feature has been failing in production despite multiple targeted fixes during the 2026-05-27 session (cache busting, canonical authors, panel state, backfill scoping). Latest symptom: `POST /admin/data-fixes/coauthor-edges` reports `with_authors=351, edges_generated=7847` but `GET /analyzers/coauthorship/{domain}` returns `{nodes: [], edges: []}` — the graph panel stays empty.

### Root cause (confirmed during diagnosis)

Two independent defects compound:

1. **Tenancy scope asymmetry.** The backfill writer (`backfill_coauthor_edges.py:127`) stores edges with `er.org_id = entity.org_id`. The reader (`coauthorship.py:166` via `tenant_access.add_org_sql_filter`) filters strictly on `er.org_id`. When the user's resolved scope and the entity's persisted scope disagree (e.g. legacy entities with `org_id IS NULL` and an admin in a real org), the `WHERE` clause discards every edge.
2. **Stringly-typed edge storage.** Edges live in `entity_relationships` with `relation_type='CO_AUTHOR'` and the author pair encoded as `notes='A||B'`. `target_id=entity_id` is a self-reference placeholder (acknowledged in code comments as a hack). Author identity is lossy — `"J. Smith"`, `"John Smith"`, `"Smith, J."` are three distinct nodes — and there is no link to `AuthorityRecord`/ORCID.

Beyond the immediate bug, the design has structural issues that make every fix produce the next bug:

- Tenancy double-filtered: scope by `er.org_id` AND by `re.domain` via JOIN — two sources of truth per edge.
- Every read recomputes adjacency + centrality + communities + publication counts on cache miss.
- No materialization. No diagnostics endpoint to observe the pipeline.

A surgical fix would close today's bug; a drastic rebuild closes the structural class.

---

## 2. Goals & non-goals

### Goals

- Replace the parasitic edge storage with first-class tables for authors, publications, and co-author edges.
- Introduce deterministic author identity with safe automatic merging plus a manual review queue for ambiguous cases.
- Materialize graph metrics (degree, centrality, community, publication count) via a worker job; serve reads from a precomputed table.
- Tighten tenancy: edge rows carry `(org_id, domain_id)` directly — no JOIN-back to entities for scope filtering.
- Ship a `/diagnostics` endpoint so future regressions surface their cause in seconds, not sessions.
- Rebuild the frontend `NetworkGraph` to a GraphDB / Neo4j Bloom-style visual.

### Non-goals (deferred)

- Polars integration — separate sprint, see §10.
- ORCID live lookup, year/range filters, GraphML export, matrix view.
- Online incremental centrality. Full recompute per dirty scope is acceptable at current and projected scale.

---

## 3. Data model

Four new tables plus a merge queue. `authors` is tenant-shared; everything else is `(org_id, domain_id)`-scoped.

```text
authors
  id                    BIGINT PK
  name_key              TEXT UNIQUE        canonical fingerprint
  display_name          TEXT
  aliases               JSON               all observed surface forms
  orcid                 TEXT NULL UNIQUE
  authority_record_id   INT NULL FK -> authority_records.id
  first_seen_at         TIMESTAMP
  last_seen_at          TIMESTAMP

author_publications
  author_id             BIGINT FK -> authors.id
  entity_id             INT    FK -> raw_entities.id
  org_id                INT NULL
  domain_id             TEXT
  position              INT                1 = first author
  PRIMARY KEY (author_id, entity_id)
  INDEX (entity_id), INDEX (org_id, domain_id)

coauthor_edges
  author_a_id           BIGINT FK -> authors.id   always smaller id
  author_b_id           BIGINT FK -> authors.id   always larger id
  org_id                INT NULL
  domain_id             TEXT
  weight                INT                       # joint publications
  last_seen_at          TIMESTAMP
  PRIMARY KEY (author_a_id, author_b_id, org_id, domain_id)
  INDEX (org_id, domain_id, weight DESC)

author_stats
  author_id             BIGINT FK -> authors.id
  org_id                INT NULL
  domain_id             TEXT
  degree                INT
  centrality            FLOAT
  community_id          INT
  publication_count     INT
  computed_at           TIMESTAMP
  PRIMARY KEY (author_id, org_id, domain_id)
  INDEX (org_id, domain_id, centrality DESC)

author_merge_suggestions
  id                    BIGINT PK
  author_a_id           BIGINT FK -> authors.id
  author_b_id           BIGINT FK -> authors.id
  reason                TEXT              'last+initial', 'affiliation_match', ...
  evidence              JSON              shared pubs, affiliations, concepts
  status                TEXT              'pending' | 'merged' | 'rejected'
  created_at            TIMESTAMP
  resolved_at           TIMESTAMP NULL
  resolved_by           INT NULL FK -> users.id
```

### Design rationale

- `authors` has no `org_id` — a person is one entity across tenants. Tenancy lives on publications and edges.
- Canonical edge ordering (`a_id < b_id`) eliminates dedup ambiguity without parsing strings.
- Compound PK on edges includes `org_id` and `domain_id` so the same pair can exist with distinct weights per scope without collision.
- `author_stats` is the cache. The table itself is the materialization; no in-memory layer needed.
- All rows from `entity_relationships WHERE relation_type='CO_AUTHOR'` are deleted at the end of migration. The table returns to its intended entity-to-entity purpose.

---

## 4. Identity strategy (hybrid)

Deterministic with three tiers. Only the first two merge automatically.

| Tier | Criterion | Action | `merge_confidence` |
|------|-----------|--------|--------------------|
| Strong | Identical ORCID, OR identical full name after NFD + lowercase | Auto-merge | 1.0 |
| Probable | Identical last name + identical full first name + ≥1 shared affiliation or concept | Auto-merge | 0.8 |
| Ambiguous | Last name + initial match but first names not comparable (e.g. "J. Smith" vs "John Smith") | Queue in `author_merge_suggestions` | n/a |

### `name_key` algorithm

Deterministic, idempotent, pure-Python — no LLM, no randomness.

1. NFD strip diacritics (`José` → `Jose`)
2. Remove titles and suffixes (`Dr.`, `PhD`, `Jr.`, `III`)
3. Detect format (`"Last, First"` vs `"First Last"`); normalize to `(last, first_tokens)`
4. `last` = lowercase, alpha-only
5. `first` = first non-initial token if present, else the leading initial
6. `name_key = f"{last}_{first}"`

Golden file with 100 representative pairs covers the test surface.

### Why not stochastic or LLM-backed

`merge_confidence` is a fixed label per rule, not a sampled probability. Same input always produces the same merge. Re-running the migration in staging, prod, and a replica yields identical graphs. If a learned ranker for ambiguous cases is desired later, it ships as a separate, opt-in initiative.

### AuthorityRecord linkage

When an admin confirms an identity via Wikidata / VIAF / ORCID through the Sprint 15-16 authority pipeline, the resolution populates `authors.authority_record_id` and triggers the merge. This provides an audit trail and a natural unmerge path if contradicting evidence appears later.

---

## 5. Compute model

Stats are computed by the enrichment worker, not on request.

### `recompute_coauthor_stats(org_id, domain_id)`

1. Load `coauthor_edges` for the scope → build adjacency.
2. Compute `degree`, `centrality`, `community_id`.
   - Louvain modularity for graphs ≥ 50 nodes.
   - Connected components for smaller graphs (Louvain is overkill).
3. Compute `publication_count` from `author_publications`.
4. Upsert into `author_stats` with `computed_at = now()`.

Pure Python Louvain (~80 LOC) — no external graph library required. Expected wall time: <2s for tens of thousands of authors; <5s for 100k edges (success criterion).

### Triggers

| Trigger | Latency | Frequency |
|---------|---------|-----------|
| Worker finishes enriching an entity with authors | Adds `(org, domain)` to a `dirty_scopes` set; debounced 30s; then recompute | Every ~30s during active ingest |
| `migrate_coauthor_graph` script | Synchronous recompute at end | Once during cutover |
| `POST /analyzers/coauthorship/{domain}/recompute` (admin+) | Synchronous, 60s timeout | On-demand, debugging |

### Analyzer read path

Pure SELECT:

```sql
SELECT a.id, a.display_name, a.orcid,
       s.degree, s.centrality, s.community_id, s.publication_count
FROM author_stats s
JOIN authors a ON a.id = s.author_id
WHERE s.org_id <=> :org_id AND s.domain_id = :domain_id
  AND s.degree >= :min_degree
ORDER BY s.centrality DESC
LIMIT :limit;
```

Expected p95 < 200ms (success criterion). No in-memory cache. `computed_at` lets the UI honestly display "Updated N min ago" and a `stale` flag if older than 5 min.

### Removals

- `_analytics_cache` entries with `coauth_` prefix.
- `force_refresh=true` query parameter on the analyzer endpoint.
- All `invalidate("coauth_")` calls scattered across routers.

---

## 6. API surface

### Reshaped

```text
GET /analyzers/coauthorship/{domain_id}
    ?min_weight=1 &limit=100 &community_id= &search=
    -> { domain_id, nodes[], edges[], computed_at, stale }
```

### New

```text
GET /analyzers/coauthorship/{domain_id}/author/{author_id}
    -> { author:        { display_name, orcid, aliases[], affiliations[] },
         publications:  [{entity_id, title, year, position}],     // top 20
         collaborators: [{author_id, name, weight, shared_pubs}], // top 50
         community:     { id, size, top_concepts[] } }

GET /analyzers/coauthorship/{domain_id}/diagnostics
    -> { edges_in_storage, edges_after_scope, authors_total,
         stats_computed_at, scope_breakdown: {by_org, by_domain} }

POST /analyzers/coauthorship/{domain_id}/recompute              (admin+)
GET  /analyzers/coauthorship/{domain_id}/merge-suggestions      (admin+)
POST /analyzers/coauthorship/merge-suggestions/{id}/confirm     (admin+)
POST /analyzers/coauthorship/merge-suggestions/{id}/reject      (admin+)
```

### Deprecated then removed

- `POST /admin/data-fixes/coauthor-edges` — kept one sprint as safety net, removed in F5.

---

## 7. Frontend rebuild

Visual reference: GraphDB / Neo4j Bloom. Layout:

```text
+-------------------------------------------------------------+
| Top bar: [search]  [min_weight slider]  [community v]  ...   |
+---------------------------------------+---------------------+
|                                       | Node properties  i  |
|   force-directed graph                |---------------------|
|     - circles, radius ~ sqrt(pubs)    | display_name        |
|     - color by community_id (OKLCH)   | orcid badge         |
|     - curved edges, weight label      | publications 47     |
|     - hover -> neighbors highlighted  | degree 12           |
|     - click -> fetch /author/{id}     | centrality 0.31     |
|                                       | community C3        |
|                          [+][-][fit]  | aliases (3) v       |
|                                       | top collaborators   |
+---------------------------------------+---------------------+
```

### Behavior

- **Nodes** sized by `sqrt(publication_count)`, colored by `community_id` via 10-color OKLCH palette.
- **Edges** as cubic Béziers; thickness `log(weight+1) * 1.5px`; weight label at midpoint, shown only when `zoom > 0.7`.
- **Hover**: node scales 1.15×, neighbors stay opaque, the rest fade to opacity 0.15.
- **Click**: fires `GET /author/{id}`; right panel hydrates; selected node receives a violet 2px ring.
- **Zoom controls** bottom-right via `d3-zoom`; supports pan and pinch.
- **Performance**: skip rendering edges outside viewport; throttle the simulation to 30 FPS; halt at stability.
- **Reduced motion**: respect `prefers-reduced-motion`; no entrance animation; simulation halts at tick 1.

### Implementation

- Stay on `d3-force` (already bundled).
- Add `d3-selection` for curved edge labels.
- No new dependency.
- Target ~400 LOC in `NetworkGraph.tsx`.

### New component

`MergeSuggestionsPanel.tsx` — collapsible card above the graph, admin-only. Lists ambiguous pairs with aliases, shared publications, affiliations. Buttons: **Merge** / **Keep separate**.

### Page simplification

`coauthorship/page.tsx` drops its derived calculations (`selectedNode`, `neighborEdges`, `communityCount`) — those now come from the backend.

---

## 8. Rollout plan

Five mergeable phases, each behind one or both feature flags.

| Phase | Scope | Risk | LOC (approx) |
|-------|-------|------|--------------|
| F1 — Schema | Create the five new tables; SQLAlchemy models; lifespan migration. No logic yet. | Low | ~250 |
| F2 — Identity engine | `backend/coauthorship/identity.py` with `name_key`, `get_or_create_author`, `merge_authors`, `classify_merge`. Pytest golden file. | Low | ~400 |
| F3 — Worker integration | Hook in `enrichment_worker.py` writes `author_publications` + `coauthor_edges` + enqueues `(org, domain)` in `dirty_scopes`. `recompute_coauthor_stats` with Louvain. Feature flag `COAUTHOR_V2_WRITE=false`. | Medium | ~350 |
| F4 — Migration + cutover | `migrate_coauthor_graph.py` + admin endpoint. New readers (`coauthorship_network`, `/author/{id}`, `/diagnostics`). Frontend rebuild. Flag `COAUTHOR_V2_READ=false`. | High | ~600 |
| F5 — Cleanup | Delete legacy `entity_relationships` CO_AUTHOR rows; drop feature flags; remove `backfill_coauthor_edges.py` and its endpoint. | Low (after 7 stable days) | ~80 |

Net: ~1700 new LOC, ~400 removed. Five reviewable PRs.

### Feature flags

```python
COAUTHOR_V2_WRITE = os.getenv("COAUTHOR_V2_WRITE", "false").lower() == "true"
COAUTHOR_V2_READ  = os.getenv("COAUTHOR_V2_READ",  "false").lower() == "true"
```

### Production cutover sequence

1. Deploy F1–F3 with `WRITE=false, READ=false`. Tables exist, code dormant.
2. Set `WRITE=true`. Worker dual-writes (new tables AND legacy `entity_relationships`).
3. Wait 24h. Run `migrate_coauthor_graph` for legacy backlog. Validate `/diagnostics`.
4. Set `READ=true`. Frontend serves V2. Monitor errors for 24h.
5. Deploy F5. Remove dual-write, delete legacy rows, drop flags.

`READ=false` reverts to the legacy implementation instantly without redeploy if anything misbehaves.

---

## 9. Testing strategy

Minimum 80% coverage per project standards; targeting 85% aggregate.

```text
F1  test_coauthor_schema.py            ~15 tests   DDL, FKs, indexes, compound PKs
F2  test_identity_engine.py            ~40 tests   golden file + edge cases
    test_merge_classifier.py           ~25 tests   tiers + ORCID + affiliation
F3  test_worker_coauthor_hook.py       ~20 tests   dual write, debounce
    test_recompute_stats.py            ~15 tests   Louvain vs connected components
F4  test_migration_script.py           ~20 tests   dry-run, idempotency, counters
    test_analyzer_v2.py                ~25 tests   scope, min_weight, search, community
    test_diagnostics_endpoint.py       ~10 tests
    test_merge_suggestions_api.py      ~15 tests
F5  test_legacy_cleanup.py             ~5 tests    asserts no CO_AUTHOR rows remain
```

### Critical regression test

```python
def test_backfill_visibility_after_recompute():
    """Previous design had org_id mismatch where backfill wrote but reader
    could not see. This test seeds entities with mixed org_id (some NULL,
    some real), runs migration + recompute, and asserts every admin role
    (super_admin global, org admin, viewer) sees the correct subset."""
```

### E2E (Playwright, one spec)

Login admin → navigate to `/analytics/coauthorship` → see populated graph → click node → side panel hydrates → verify zoom/pan → verify merge suggestions panel.

---

## 10. Out of scope (intentionally)

- **Polars adoption.** Considered. For this refactor specifically, the bottleneck is Louvain (graph algorithm, not DataFrames) and SQL I/O. Polars yields ~zero perf win at current and projected scale, adds ~30 MB and a second DataFrame API to the codebase, and would dilute review focus. A separate "Polars adoption for hot paths" sprint should target `olap.py`, `correlation.py`, and large CSV ingest, where measured ROI is real.
- ORCID live lookup, year filtering, GraphML export, matrix/heatmap alternative view.
- Online incremental centrality.

---

## 11. Observability and rollback

- `/diagnostics` ships permanently. First place to look if the graph appears empty again.
- Structured logger in `recompute_coauthor_stats` reports `scope`, `nodes`, `edges`, `communities`, `wall_time_ms`. Indexed in logs.
- F4 rollback: `COAUTHOR_V2_READ=false` + restart. No data loss — dual-writes remain alive until F5.
- F5 is irreversible without restoring `entity_relationships` from backup. F5 only ships after 7 consecutive stable days post-F4.

---

## 12. Success criteria (definition of done)

1. `/analytics/coauthorship` renders a populated graph in `default` and in domain-specific scopes for super_admin, admin, and viewer roles.
2. `GET /analyzers/coauthorship/{domain}` p95 < 200ms on current corpus.
3. `recompute_coauthor_stats` completes < 5s for 100k edges.
4. `name_key` collapsing: the current 351-entity corpus reduces from ~7800 string-unique nodes to N canonical nodes (baseline measured during migration dry-run).
5. Zero rows with `relation_type='CO_AUTHOR'` remain in `entity_relationships` after F5.
6. Aggregate test coverage of the coauthorship module ≥ 85%.

---

## Appendix A — Affected files

### New

```
backend/coauthorship/__init__.py
backend/coauthorship/identity.py
backend/coauthorship/migration.py
backend/coauthorship/recompute.py
backend/coauthorship/louvain.py
backend/scripts/migrate_coauthor_graph.py
backend/routers/coauthorship.py
backend/tests/test_coauthor_schema.py
backend/tests/test_identity_engine.py
backend/tests/test_merge_classifier.py
backend/tests/test_worker_coauthor_hook.py
backend/tests/test_recompute_stats.py
backend/tests/test_migration_script.py
backend/tests/test_analyzer_v2.py
backend/tests/test_diagnostics_endpoint.py
backend/tests/test_merge_suggestions_api.py
backend/tests/test_legacy_cleanup.py
frontend/app/components/graph/MergeSuggestionsPanel.tsx
frontend/app/components/graph/NodePropertiesPanel.tsx
frontend/app/components/graph/GraphControls.tsx
frontend/e2e/coauthorship.spec.ts
```

### Modified

```
backend/models.py                          # +5 model classes
backend/main.py                            # router include + lifespan migration
backend/enrichment_worker.py               # write hook + dirty_scopes
backend/analyzers/coauthorship.py          # readers re-pointed at new tables
backend/routers/analytics.py               # remove coauthorship route after move
backend/config.py                          # feature flags
frontend/app/analytics/coauthorship/page.tsx
frontend/app/components/graph/NetworkGraph.tsx
frontend/app/components/graph/useForceLayout.ts
frontend/lib/api.ts                        # (no change expected)
```

### Removed (F5)

```
backend/scripts/backfill_coauthor_edges.py
backend/routers/admin_data_fixes.py        # coauthor-edges route + request models
backend/tests/test_admin_data_fixes.py     # the coauthor-edges tests
```

---

## Appendix B — Open questions for implementation planning

1. Naming of feature flags — `COAUTHOR_V2_*` vs `COAUTHORSHIP_REBUILD_*`. Decide during F1 PR review.
2. Whether the F3 dual-write should also update `entity_relationships` weights (additive) or skip them (since they will be deleted in F5). Preference: skip to keep the write path simple.
3. Whether `author_stats.computed_at` should be exposed in the per-author endpoint response (UI affordance vs API surface bloat). Decide during F4 frontend review.

End of design.
