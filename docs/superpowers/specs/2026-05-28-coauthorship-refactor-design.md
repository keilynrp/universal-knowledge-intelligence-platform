# Co-authorship Module — Drastic Refactor Design

- **Date:** 2026-05-28
- **Author:** UKIP team (brainstormed with Claude)
- **Status:** Approved for planning (rev 2 — applies CRITICAL/HIGH fixes from architect review)
- **Scope:** Backend + frontend rebuild of `/analytics/coauthorship`
- **Supersedes:** `EntityRelationship(relation_type='CO_AUTHOR', notes='A||B')` storage, `backfill_coauthor_edges.py`, on-demand compute in `backend/analyzers/coauthorship.py`

---

## 1. Problem statement

The current co-authorship feature has been failing in production despite multiple targeted fixes during the 2026-05-27 session (cache busting, canonical authors, panel state, backfill scoping). Latest symptom: `POST /admin/data-fixes/coauthor-edges` reports `with_authors=351, edges_generated=7847` but `GET /analyzers/coauthorship/{domain}` returns `{nodes: [], edges: []}` — the graph panel stays empty.

### Root cause (confirmed during diagnosis)

Two independent defects compound:

1. **Tenancy scope asymmetry.** The backfill writer (`backfill_coauthor_edges.py:127`) stores edges with `er.org_id = entity.org_id`. The reader (`coauthorship.py:166` via `tenant_access.add_org_sql_filter`) filters strictly on `er.org_id`. When the user's resolved scope and the entity's persisted scope disagree (e.g. legacy entities with `org_id IS NULL` and an admin in a real org), the `WHERE` clause discards every edge.
2. **Stringly-typed edge storage.** Edges live in `entity_relationships` with `relation_type='CO_AUTHOR'` and the author pair encoded as `notes='A||B'`. `target_id=entity_id` is a self-reference placeholder (acknowledged in code comments as a hack). Author identity is lossy — `"J. Smith"`, `"John Smith"`, `"Smith, J."` are three distinct nodes — and there is no link to `AuthorityRecord`/ORCID.

### Alternatives ruled out

- **Stale analytics cache.** Sessions 2026-05-27 (commits `a5abe5aa`, `684d9738`) shipped `_analytics_cache.invalidate("coauth_")` and `force_refresh=true` paths. We confirmed the empty result reproduces even with cache disabled.
- **`domain_id="default"` filter mismatch.** The reader already handles the NULL/"default" split correctly via `or_(domain == 'default', domain.is_(None))`. Verified by inspecting `_load_coauthor_edges`.
- **`notes='A||B'` parser whitespace.** The reader trims both sides; mismatched author surface forms (e.g. trailing space) would lower edge count but not zero it out at the 7847→0 magnitude observed.

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

Five new tables plus a merge queue. `authors` is tenant-shared; everything else is `(org_id, domain_id)`-scoped.

### Sentinel for legacy global scope

To make compound primary keys involving `org_id` enforce uniqueness portably (SQLite/Postgres both treat NULL as distinct in UNIQUE constraints), **every scoped table stores legacy global rows as `org_id = 0`**, not NULL. `org_id = 0` is reserved and matches the existing `LEGACY_GLOBAL_ORG_ID` sentinel concept already used in `tenant_access.persisted_org_id`. Existing nullable columns elsewhere in UKIP are unchanged; the sentinel is local to the five new tables.

```text
authors
  id                    BIGINT PK
  name_key              TEXT UNIQUE        canonical fingerprint
  display_name          TEXT
  aliases               JSON               all observed surface forms (cap: 50 entries, oldest evicted)
  orcid                 TEXT NULL UNIQUE
  authority_record_id   INT NULL FK -> authority_records.id   -- NOT unique; multiple authors may
                                                              -- transiently point at one record
                                                              -- pre-merge; merge collapses them
  first_seen_at         TIMESTAMP
  last_seen_at          TIMESTAMP

author_publications
  author_id             BIGINT FK -> authors.id
  entity_id             INT    FK -> raw_entities.id  ON DELETE CASCADE
  org_id                INT NOT NULL DEFAULT 0       -- 0 = legacy global
  domain_id             TEXT NOT NULL
  position              INT                          -- 1 = first author
  PRIMARY KEY (author_id, entity_id)
  INDEX (entity_id)
  INDEX (org_id, domain_id)
  INDEX (author_id, org_id, domain_id)              -- recompute hot path

coauthor_edges
  author_a_id           BIGINT FK -> authors.id ON DELETE CASCADE   -- always smaller id
  author_b_id           BIGINT FK -> authors.id ON DELETE CASCADE   -- always larger id
  org_id                INT NOT NULL DEFAULT 0
  domain_id             TEXT NOT NULL
  weight                INT NOT NULL                  -- # joint publications
  last_seen_at          TIMESTAMP
  PRIMARY KEY (author_a_id, author_b_id, org_id, domain_id)
  INDEX (org_id, domain_id, weight DESC)

author_stats
  author_id             BIGINT FK -> authors.id ON DELETE CASCADE
  org_id                INT NOT NULL DEFAULT 0
  domain_id             TEXT NOT NULL
  degree                INT
  centrality            FLOAT
  community_id          INT
  publication_count     INT
  computed_at           TIMESTAMP
  PRIMARY KEY (author_id, org_id, domain_id)
  INDEX (org_id, domain_id, centrality DESC)
  INDEX (org_id, domain_id, community_id)           -- supports community_id= filter in API

author_merge_suggestions
  id                    BIGINT PK
  author_a_id           BIGINT FK -> authors.id ON DELETE CASCADE
  author_b_id           BIGINT FK -> authors.id ON DELETE CASCADE
  reason                TEXT                'last+initial', 'affiliation_match', ...
  evidence              JSON                shared pubs, affiliations, concepts
  status                TEXT                'pending' | 'merged' | 'rejected'
  created_at            TIMESTAMP
  resolved_at           TIMESTAMP NULL
  resolved_by           INT NULL FK -> users.id

author_merge_audit                          -- append-only log for ALL merges (auto + manual)
  id                    BIGINT PK
  winner_author_id      BIGINT              -- surviving id
  loser_author_id       BIGINT              -- merged-away id (no FK — row may be deleted)
  tier                  TEXT                'strong' | 'probable' | 'manual'
  reason                TEXT
  evidence              JSON
  performed_at          TIMESTAMP
  performed_by          INT NULL FK -> users.id     -- NULL = automatic

coauthor_dirty_scopes                       -- durable replacement for in-process Set
  org_id                INT NOT NULL
  domain_id             TEXT NOT NULL
  enqueued_at           TIMESTAMP
  reason                TEXT                'enrichment' | 'migration' | 'manual'
  PRIMARY KEY (org_id, domain_id)
```

### Design rationale

- `authors` has no `org_id` — a person is one entity across tenants. Tenancy lives on publications and edges.
- `org_id = 0` sentinel makes all compound PKs enforce uniqueness across legacy and tenant rows uniformly.
- Canonical edge ordering (`a_id < b_id`) eliminates dedup ambiguity without parsing strings.
- `author_publications.entity_id` cascades on delete: removing a `raw_entity` removes its publications, and a follow-up dirty-scope enqueue triggers edge recompute.
- `author_stats` is the cache. The table itself is the materialization; no in-memory layer needed.
- `author_merge_audit` is append-only and supports unmerge by replaying loser rows.
- `coauthor_dirty_scopes` survives worker restarts; an in-process Python set does not.
- All rows from `entity_relationships WHERE relation_type='CO_AUTHOR'` are deleted at the end of migration. The table returns to its intended entity-to-entity purpose.

### Tenancy reassignment policy

If a `raw_entity.org_id` is mutated (rare — tenant reassignment), the worker hook UPDATEs all matching `author_publications.org_id` in the same transaction and enqueues both old and new scopes for recompute. Documented as a worker invariant; tested in `test_worker_coauthor_hook.py`.

---

## 4. Identity strategy (hybrid)

Deterministic with three tiers. Only the first two merge automatically. Every auto-merge writes an `author_merge_audit` row.

| Tier | Criterion | Action | `merge_confidence` |
|------|-----------|--------|--------------------|
| Strong | Identical ORCID, OR identical `name_key` **and** ≥1 shared publication (entity_id) | Auto-merge | 1.0 |
| Probable | Identical `name_key` + ≥1 shared affiliation OR ≥1 shared concept (and no ORCID conflict) | Auto-merge | 0.8 |
| Ambiguous | `name_key` collision without disambiguator, OR last name + initial match across different first-name forms | Queue in `author_merge_suggestions` | n/a |

**Why the disambiguator requirement on strong tier**: "John Smith" alone is not safe to auto-merge. Two people published in 2019 with the name "John Smith" must remain separate unless ORCID matches or they co-published. This was the architect-review C3 correction.

### `name_key` algorithm

Deterministic, idempotent, pure-Python — no LLM, no randomness.

1. NFD strip diacritics (`José` → `Jose`).
2. Remove titles and suffixes (`Dr.`, `PhD`, `Jr.`, `III`).
3. Detect format (`"Last, First"` vs `"First Last"`); normalize to `(last_tokens, first_tokens)`. Handles particles (`van`, `der`, `de`, `la`) as part of the last name token. Hyphenated surnames preserved with hyphen as separator.
4. `last` = lowercase, Unicode-letter-only (preserves CJK, Cyrillic).
5. `first` = first non-initial token if length ≥ 2, else the single leading initial letter, else empty.
6. `name_key = f"{last}_{first}"` (trailing underscore retained when `first` empty — mononyms get `mononym_`).

**Routing for the canonical "J. Smith" vs "John Smith" case**:
- `"J. Smith"` → `name_key = "smith_j"`
- `"John Smith"` → `name_key = "smith_john"`
- These are **distinct keys**, hence DIFFERENT authors by default.
- The merge classifier detects `(smith_j, smith_john)` as a `last+initial` ambiguous pair and enqueues a merge suggestion. **Never auto-merged.** The admin reviews shared publications and affiliations and decides.

This resolves the tension §1 flagged: aggressive collapse in §1's framing is *not* what the algorithm does — surface forms diverging by initial vs full first name are explicitly routed to ambiguous review.

### CJK, mononyms, particles — explicit policy

- CJK names: NFD does not decompose CJK; `last` keeps the family ideograph(s); golden file covers `"李 明"`, `"Wang, Wei"`, `"Ye Zhuo"`.
- Mononyms (e.g. `"Madonna"`, `"Pelé"`): `last = "madonna"`, `first = ""`, `name_key = "madonna_"`. Cannot collide with other names unless they too are mononyms with the same surface form.
- Particles: `"Vincent van der Berg"` → last tokens = `["van", "der", "berg"]` joined as `"vanderberg"`; first = `"vincent"`; `name_key = "vanderberg_vincent"`. Documented; golden cases exist for `van`, `der`, `de`, `la`, `del`, `da`, `dos`, `el`, `al`.

Golden file with ≥150 representative pairs (100 baseline + 50 covering the cases above) covers the test surface. Treated as a regression baseline — new edge cases append.

### AuthorityRecord linkage

When an admin confirms an identity via Wikidata / VIAF / ORCID through the Sprint 15-16 authority pipeline, the resolution populates `authors.authority_record_id` and triggers the merge. This provides an audit trail and a natural unmerge path if contradicting evidence appears later.

---

## 5. Compute model

Stats are computed by the enrichment worker, not on request.

### `recompute_coauthor_stats(org_id, domain_id)`

1. Load `coauthor_edges` for the scope → build adjacency.
2. Compute `degree`, `centrality`, `community_id`.
   - **Use the `python-louvain` package** (community detection, MIT-licensed, ~50 KB). Pure-Python "~80 LOC Louvain" was an aspirational claim in rev 1; the dep is cheaper than maintaining our own.
   - Connected components for graphs < 50 nodes (Louvain is overkill).
3. Compute `publication_count` from `author_publications` using the `(author_id, org_id, domain_id)` index.
4. Upsert into `author_stats` with `computed_at = now()`.
5. Delete the scope's row from `coauthor_dirty_scopes`.

Expected wall time at current corpus: <2s. **Target for 10× corpus (100k edges): <5s.** If `python-louvain` benchmarks miss this target during F3 prototype, accept p95 < 10s and document the regression in the success criteria. Recompute is a background job; user-facing reads stay <200ms regardless.

### Triggers

| Trigger | Latency | Frequency |
|---------|---------|-----------|
| Worker finishes enriching an entity with authors | Inserts `(org, domain)` into `coauthor_dirty_scopes`; debounced 30s; then recompute | Every ~30s during active ingest |
| `migrate_coauthor_graph` script | Synchronous recompute of touched scopes at end | Once during cutover |
| `POST /analyzers/coauthorship/{domain}/recompute` (admin+) | Synchronous, 60s timeout, **rate-limited to 1 req per scope per 30s** | On-demand, debugging |
| `raw_entity` deleted (cascade fires) | Worker observes `author_publications` row drop → enqueues scope | Per entity deletion |

`coauthor_dirty_scopes` is polled every 30s by the worker; on poll, any row with `enqueued_at + 30s < now()` is consumed.

### Analyzer read path

Pure SELECT. **NULL-safe equality via COALESCE — `<=>` from rev 1 was MySQL-only and would silently filter all rows on SQLite/Postgres.**

```sql
SELECT a.id, a.display_name, a.orcid,
       s.degree, s.centrality, s.community_id, s.publication_count
FROM author_stats s
JOIN authors a ON a.id = s.author_id
WHERE s.org_id = :org_id                       -- :org_id resolved to 0 for legacy global
  AND s.domain_id = :domain_id
  AND s.degree >= :min_degree
ORDER BY s.centrality DESC
LIMIT :limit;
```

The router resolves `org_id` once via `tenant_access.resolve_request_org_id`. For super_admin global views the existing helper returns `None`; this layer translates that to **no `org_id` filter at all**:

```python
if org_id is None:                       # super_admin global view
    where = "s.domain_id = :domain_id AND s.degree >= :min_degree"
else:                                    # everyone else, including legacy users (org_id == 0)
    where = "s.org_id = :org_id AND s.domain_id = :domain_id AND s.degree >= :min_degree"
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
    -> { domain_id, nodes[], edges[], computed_at, stale, coverage_pct }
```

`coverage_pct` = `publications_processed / source_entities_eligible` for the scope — surfaces partial migrations to the UI.

### New

```text
GET /analyzers/coauthorship/{domain_id}/author/{author_id}
    -> { author:        { display_name, orcid, aliases[], affiliations[] },
         publications:  [{entity_id, title, year, position}],     // top 20
         collaborators: [{author_id, name, weight, shared_pubs}], // top 50
         community:     { id, size, top_concepts[] },
         stats_computed_at }

GET /analyzers/coauthorship/{domain_id}/diagnostics
    -> { edges_in_storage, edges_after_scope, authors_total,
         stats_computed_at, dirty_queue_depth,
         last_recompute_ms, coverage_pct,
         scope_breakdown: {by_org, by_domain} }

POST /analyzers/coauthorship/{domain_id}/recompute              (admin+, rate-limited)
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
- **Accessibility**: graph is augmented with a parallel ARIA list of nodes; arrow keys move focus between neighbors of the selected node; Enter activates focus; the side panel is wired as `aria-live="polite"`.

### Implementation

- Stay on `d3-force` (already bundled).
- Add `d3-selection` for curved edge labels.
- No new frontend dependency.
- Target ~400 LOC in `NetworkGraph.tsx`.

### New component

`MergeSuggestionsPanel.tsx` — collapsible card above the graph, admin-only. Lists ambiguous pairs with aliases, shared publications, affiliations. Buttons: **Merge** / **Keep separate**.

### Page simplification

`coauthorship/page.tsx` drops its derived calculations (`selectedNode`, `neighborEdges`, `communityCount`) — those now come from the backend.

---

## 8. Rollout plan

Seven mergeable phases (F4 split into a/b/c per architect review H2), each behind one or both feature flags.

| Phase | Scope | Risk | LOC (approx) |
|-------|-------|------|--------------|
| F1 — Schema | Create the seven new tables; SQLAlchemy models; lifespan migration. No logic yet. | Low | ~280 |
| F2 — Identity engine | `backend/coauthorship/identity.py` with `name_key`, `get_or_create_author`, `merge_authors`, `classify_merge`. Pytest golden file (≥150 cases). | Low | ~450 |
| F3 — Worker integration | Hook in `enrichment_worker.py` writes `author_publications` + `coauthor_edges` + enqueues `coauthor_dirty_scopes`. `recompute_coauthor_stats` with `python-louvain`. Feature flag `COAUTHOR_V2_WRITE=false`. **Shadow-table mirroring deferred** — equivalent safety via `WRITE=false` gating + `migrate_coauthor_graph` dry-run audits on a prod replica + `/diagnostics` monitoring once enabled. | Medium | ~400 |
| F4a — Migration + diagnostics | `migrate_coauthor_graph.py` (idempotent UPSERT semantics) + admin endpoint + `/diagnostics` endpoint. Promote shadow tables to real tables once F3 verification passes. No UI changes. | Medium-High | ~300 |
| F4b — V2 read endpoints | New readers behind `COAUTHOR_V2_READ=false`: `coauthorship_network`, `/author/{id}`, merge-suggestions API. Old endpoint preserved untouched. | Medium | ~250 |
| F4c — Frontend rebuild | `NetworkGraph.tsx` rewrite, `NodePropertiesPanel.tsx`, `MergeSuggestionsPanel.tsx`, `coauthorship/page.tsx` simplification, e2e spec. | Medium | ~500 |
| F5 — Cleanup | Delete legacy `entity_relationships` CO_AUTHOR rows; drop feature flags; remove `backfill_coauthor_edges.py` and its endpoint; drop shadow tables. | Low (after 7 stable days) | ~80 |

Net: ~2260 new LOC, ~400 removed. Seven reviewable PRs.

### Feature flags

```python
COAUTHOR_V2_WRITE  = os.getenv("COAUTHOR_V2_WRITE",  "false").lower() == "true"
COAUTHOR_V2_READ   = os.getenv("COAUTHOR_V2_READ",   "false").lower() == "true"
# Note: COAUTHOR_V2_SHADOW was reserved in rev 2 but the shadow-table mechanism
# is deferred. The two-flag split (WRITE × READ) plus dry-run audit on a
# replica achieves equivalent safety without doubling schema surface.
```

### Migration ↔ live-write conflict semantics

When `WRITE=true` is active, both the migration script and the worker write concurrently. Conflict rules:

- `authors` UPSERT on `name_key`: existing row wins; new aliases append (capped).
- `author_publications` UPSERT on `(author_id, entity_id)`: rows are identical by construction (entity defines `org_id` + `domain_id`); INSERT OR IGNORE.
- `coauthor_edges` UPSERT on PK: `weight = excluded.weight + existing.weight` is **wrong** — would double-count. Correct rule: each `(entity_id, author_a, author_b)` contributes exactly 1 to weight. The migration script and worker both deduplicate via a `coauthor_contributions(entity_id, author_a, author_b)` UNIQUE INSERT-IGNORE log; only on successful contribution insert does the edge weight increment by 1. This makes the operation idempotent under any interleaving.

### Production cutover sequence

1. Deploy F1, F2, F3 (`WRITE=false, READ=false`). Tables exist, code dormant.
2. Run `migrate_coauthor_graph --dry-run` on a prod replica. Audit `/diagnostics` shape on the replica. Confirm `name_key` collapse counts and edge counts look sane.
3. Deploy F4a. Set `WRITE=true`. Worker begins populating V2 tables for new ingest; legacy `entity_relationships` rows are NOT updated from this point forward (per Appendix B item 2).
4. Run `migrate_coauthor_graph` (real) for the legacy backlog. Validate `/diagnostics` shows `coverage_pct == 100`.
5. Deploy F4b. Set `READ=true`. Frontend (still V1) serves V2 data. Monitor errors for 24h.
6. Deploy F4c. Frontend rebuild visible to users.
7. Wait 7 stable days. Deploy F5. Delete legacy `entity_relationships` CO_AUTHOR rows; drop flags.

`READ=false` reverts to legacy reads instantly without redeploy if anything misbehaves at steps 5–6.

---

## 9. Testing strategy

Minimum 80% coverage per project standards; targeting 85% aggregate.

```text
F1  test_coauthor_schema.py              ~15 tests   DDL, FKs, indexes, compound PKs,
                                                     sentinel-zero uniqueness
F2  test_identity_engine.py              ~50 tests   golden file 150+ cases + CJK/mononym/particles
    test_merge_classifier.py             ~30 tests   tiers, disambiguator requirement, ORCID conflict
    test_get_or_create_author_race.py    ~5 tests    concurrent inserts on same name_key
F3  test_worker_coauthor_hook.py         ~25 tests   shadow vs real, debounce, dirty_scopes persistence,
                                                     tenant reassignment
    test_recompute_stats.py              ~20 tests   Louvain vs connected components, 100k-edge perf gate
F4a test_migration_script.py             ~25 tests   dry-run, idempotency, interruption/resume,
                                                     contribution dedup
    test_diagnostics_endpoint.py         ~15 tests   coverage_pct, dirty_queue_depth, scope_breakdown
F4b test_analyzer_v2.py                  ~30 tests   scope, min_weight, search, community,
                                                     super_admin global, regression test below
    test_merge_suggestions_api.py        ~15 tests   confirm/reject + audit log writes
F4c e2e/coauthorship.spec.ts             1 spec      full user flow
    test_network_graph_visual.spec.ts    ~6 cases    visual regression at 320/768/1280/1920
F5  test_legacy_cleanup.py               ~5 tests    asserts no CO_AUTHOR rows remain
```

### Critical regression test

```python
def test_backfill_visibility_after_recompute():
    """Previous design had org_id mismatch where backfill wrote but reader
    could not see. This test seeds entities with mixed org_id (some legacy=0,
    some real), runs migration + recompute, and asserts every admin role
    (super_admin global, org admin, viewer in same org, viewer in different
    org) sees the correct subset. Also asserts an author who publishes
    across two orgs has TWO author_stats rows (one per scope) and TWO edge
    sets, not a leaked cross-org view."""
```

### Performance gate

`test_recompute_stats.py::test_louvain_100k_edges_under_5s` ships with F3. Failing this gate blocks merge of F3.

---

## 10. Out of scope (intentionally)

- **Polars adoption.** Considered. For this refactor specifically, the bottleneck is Louvain (graph algorithm, not DataFrames) and SQL I/O. Polars yields ~zero perf win at current and projected scale, adds ~30 MB and a second DataFrame API to the codebase, and would dilute review focus. A separate "Polars adoption for hot paths" sprint should target `olap.py`, `correlation.py`, and large CSV ingest, where measured ROI is real.
- ORCID live lookup, year filtering, GraphML export, matrix/heatmap alternative view.
- Online incremental centrality.
- GDPR right-to-erasure UI flow for authors. Captured as M-1 follow-up; PII handling on `authors.display_name` and `aliases` deferred until legal review for the broader UKIP corpus.

---

## 11. Observability and rollback

- `/diagnostics` ships permanently in F4a. First place to look if the graph appears empty again. Surfaces: `edges_in_storage`, `edges_after_scope`, `authors_total`, `stats_computed_at`, `dirty_queue_depth`, `last_recompute_ms`, `coverage_pct`, and per-org/domain breakdown.
- Structured logger in `recompute_coauthor_stats` reports `scope`, `nodes`, `edges`, `communities`, `wall_time_ms`. Indexed in logs.
- `author_merge_audit` provides a query path for "who was merged into whom and why" — supports a future unmerge tool.
- Worker uses the existing `circuit_breaker.py` pattern (Sprint 3) for any future external authority callouts triggered during identity resolution. Currently no external calls in the F1–F5 scope, but the wiring is reserved.
- F4 rollback: `COAUTHOR_V2_READ=false` + restart. No data loss — dual-writes remain alive until F5.
- F5 is irreversible without restoring `entity_relationships` from backup. F5 only ships after 7 consecutive stable days post-F4c.

---

## 12. Success criteria (definition of done)

1. `/analytics/coauthorship` renders a populated graph in `default` and in domain-specific scopes for super_admin, admin, and viewer roles.
2. `GET /analyzers/coauthorship/{domain}` p95 < 200ms on current corpus.
3. `recompute_coauthor_stats` completes < 5s for 100k edges (or < 10s with documented gate failure if `python-louvain` cannot meet the 5s target — must be documented before F3 merge).
4. `name_key` collapsing: the current 351-entity corpus reduces from ~7800 string-unique nodes to N canonical nodes (baseline measured during migration dry-run).
5. Zero rows with `relation_type='CO_AUTHOR'` remain in `entity_relationships` after F5.
6. Aggregate test coverage of the coauthorship module ≥ 85%.
7. `/diagnostics` correctly reports a non-zero `edges_after_scope` for every admin user who sees a populated graph (no silent scope drops).

---

## Appendix A — Affected files

### New

```
backend/coauthorship/__init__.py
backend/coauthorship/identity.py
backend/coauthorship/migration.py
backend/coauthorship/recompute.py
backend/coauthorship/diagnostics.py
backend/scripts/migrate_coauthor_graph.py
backend/routers/coauthorship.py
backend/tests/test_coauthor_schema.py
backend/tests/test_identity_engine.py
backend/tests/test_merge_classifier.py
backend/tests/test_get_or_create_author_race.py
backend/tests/test_worker_coauthor_hook.py
backend/tests/test_recompute_stats.py
backend/tests/test_migration_script.py
backend/tests/test_diagnostics_endpoint.py
backend/tests/test_analyzer_v2.py
backend/tests/test_merge_suggestions_api.py
backend/tests/test_legacy_cleanup.py
frontend/app/components/graph/MergeSuggestionsPanel.tsx
frontend/app/components/graph/NodePropertiesPanel.tsx
frontend/app/components/graph/GraphControls.tsx
frontend/e2e/coauthorship.spec.ts
frontend/e2e/network_graph_visual.spec.ts
```

### Modified

```
backend/models.py                          # +7 model classes
backend/main.py                            # router include + lifespan migration
backend/enrichment_worker.py               # write hook + dirty_scopes enqueue + tenant reassignment
backend/analyzers/coauthorship.py          # readers re-pointed at new tables
backend/routers/analytics.py               # remove coauthorship route after move
backend/config.py                          # feature flags (WRITE, SHADOW, READ)
frontend/app/analytics/coauthorship/page.tsx
frontend/app/components/graph/NetworkGraph.tsx
frontend/app/components/graph/useForceLayout.ts
requirements.txt                           # +python-louvain
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
2. Whether the F3 dual-write should also update `entity_relationships` weights (additive) or skip them (since they will be deleted in F5). **Decision: skip.** Keep the legacy table immutable from F3 onward to simplify F5 verification.
3. Whether `author_stats.computed_at` should be exposed in the per-author endpoint response (UI affordance vs API surface bloat). **Decision: expose.** UI shows "stats current as of …" alongside the panel.
4. Long-term home for `author_merge_audit` — keep in the main DB or ship to a separate audit store. Defer until F4a review.

---

## Appendix C — Changelog (rev 2)

Applied from architect review 2026-05-28:
- **C1** Replaced MySQL-only `<=>` with explicit branching + plain `=` in §5 SQL.
- **C2** Switched `org_id` nullable columns on the five new tables to `NOT NULL DEFAULT 0` sentinel; documented in §3.
- **C3** Strong-tier auto-merge now requires a disambiguator (ORCID or shared publication). §4.
- **H1** `name_key` routing for "J. Smith" vs "John Smith" explicitly documented as ambiguous-queue, not auto-merge. §4.
- **H2** F4 split into F4a (migration + diagnostics), F4b (V2 reads), F4c (frontend). §8.
- **H3** Conflict semantics for concurrent migration ↔ worker writes defined via `coauthor_contributions` dedup log. §8.
- **H4** Replaced "~80 LOC pure-Python Louvain" with `python-louvain` dep + perf gate in tests. §5, §9, §12.
- **H5** `dirty_scopes` moved from in-process set to durable `coauthor_dirty_scopes` table. §3, §5.
- **H6** Super_admin global read path documented as `org_id` filter omitted entirely. §5.
- **H7** Entity deletion cascade made explicit via `ON DELETE CASCADE` on `author_publications.entity_id`. §3.
- M-series: indexes added (`(author_id, org_id, domain_id)`, `community_id`); `aliases` size cap; `author_merge_audit` for all merges; `/recompute` rate limit; `/diagnostics` fields `dirty_queue_depth`, `last_recompute_ms`, `coverage_pct`; concurrency + visual-regression tests added.
- L-series: CJK/mononym/particle policy and golden cases. A11y (keyboard nav + ARIA live). Tenancy reassignment policy. Circuit-breaker wiring reserved.

End of design.
