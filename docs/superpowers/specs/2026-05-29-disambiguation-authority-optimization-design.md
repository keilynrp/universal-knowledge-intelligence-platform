# Disambiguation & Authority Optimization — Design Spec

**Date:** 2026-05-29
**Status:** Draft for implementation
**Owner:** Platform / Entity Resolution
**Related plan:** `docs/superpowers/plans/2026-05-29-disambiguation-authority-optimization.md`

---

## 1. Problem statement

The Disambiguation (`/disambiguation`) and Authority Control (`/authority`) modules are
functional but have three classes of gaps that block "top-market" entity resolution:

1. **Scalability** — lexical clustering is O(n²) and in-memory; the authority batch
   resolves N values against 5 external APIs *inside* a single HTTP request; external
   lookups are never cached.
2. **Resolution quality** — matching is purely lexical (`thefuzz`); the strongest
   author signal (coauthorship) carries weight `0.0`; clustering is order-dependent
   (no transitive closure); thresholds are uncalibrated.
3. **Intelligence / differentiation** — reviewer decisions don't feed back into
   scoring; thresholds are global constants; the `score_breakdown`/`evidence` already
   persisted are not surfaced in the UI.

## 2. Goals

- G1. Disambiguation clustering scales to ≥100k distinct values within interactive latency.
- G2. Authority batch resolution never blocks an HTTP request; runs as a background job with progress.
- G3. External authority lookups are cached and resilient (retry + circuit breaker).
- G4. Matching combines lexical + semantic + coauthorship signals with a measured precision/recall.
- G5. An evaluation harness gives a reproducible quality score per algorithm/threshold.
- G6. Reviewer confirm/reject decisions measurably improve future scoring.

## 3. Non-goals

- Replacing the existing Rust engine delegation path (we keep it; we improve the Python fallback).
- Multi-language phonetic matching beyond what `clustering/algorithms.py` already supports.
- A bespoke ML training pipeline — Phase 2 uses pre-trained embeddings + simple learned weights, not a trained deep model.

## 4. Current architecture (as-is)

| Concern | Location |
|---|---|
| Clustering (4 algorithms) | `backend/routers/deps.py:_build_disambig_groups` |
| Disambiguation endpoints | `backend/routers/disambiguation.py` |
| Authority orchestrator | `backend/authority/resolver.py:resolve_all` |
| Scoring engine | `backend/authority/scoring.py:compute_score` |
| Resolvers (5) | `backend/authority/resolvers/{wikidata,viaf,orcid,dbpedia,openalex}.py` |
| Authority endpoints | `backend/routers/authority.py` |
| Circuit breaker (reusable) | `backend/circuit_breaker.py` |
| Background-worker pattern | `backend/enrichment_worker.py` |
| Read-model guard | `backend/services/entity_query.py:entity_base_q` |
| Embeddings store | ChromaDB (already in stack) |
| Coauthorship graph | `backend/coauthorship/` (already built) |

## 5. Design decisions

### Phase 1 — Stabilization & scaling

- **DD1. Caching layer.** New `backend/authority/cache.py` exposing a process-wide
  `TTLCache` keyed by `(source, normalized_value, entity_type)`. Default TTL 7 days,
  maxsize 10_000, configurable via env (`UKIP_AUTHORITY_CACHE_TTL`, `_MAXSIZE`). Wrap each
  resolver call in `resolve_all`. Cache stores the *raw* candidate list (pre-scoring), so
  context-dependent scoring stays correct.
- **DD2. Resilient resolver calls.** New `backend/authority/resilience.py` providing a
  `call_resolver(resolver, value, entity_type)` helper that combines a per-source
  `CircuitBreaker` (reuse `circuit_breaker.py`) with bounded retry (2 attempts, exponential
  backoff 0.5s→1s, jitter). On `CircuitOpenError` or final failure → return `[]` (same
  contract as today). No new heavy dependency; implement backoff inline (avoid `tenacity`).
- **DD3. Async batch job.** Reuse the enrichment-worker pattern. New model
  `AuthorityResolveJob` (status `pending|processing|done|failed`, counters, field, params).
  `POST /authority/resolve/batch` becomes "enqueue + return job id"; a worker coroutine in
  `backend/authority/batch_worker.py` claims jobs atomically (`UPDATE ... WHERE status='pending'`,
  rowcount check) and resolves in chunks. New `GET /authority/jobs/{id}` for progress.
  Keep the old synchronous behavior behind `?sync=true` for small fields / tests.
- **DD4. Server-side pagination.** Add `skip`/`limit` to `_build_disambig_groups`
  (slice the *materialized group list*, return `total_groups` separately) and thread it
  through `/disambiguate/{field}` and `/authority/{field}` with an `X-Total-Count` header.

### Phase 2 — Matching quality

- **DD5. Blocking + Union-Find.** New `backend/clustering/blocking.py`. For a value list,
  generate blocking keys (existing `fingerprint`, phonetic code, sorted first-3-token prefix).
  Only compare pairs sharing a block. Feed surviving pairs (similarity ≥ threshold) into a
  `UnionFind` (`backend/clustering/union_find.py`) to get transitive, order-independent
  components. Replaces the greedy `processed`-set loop for `token_sort`/`ngram`. Complexity
  target ~O(n · b) where b = avg block size.
- **DD6. Coauthorship signal.** Implement `_score_coauthorship` in `scoring.py`. For
  `entity_type == "person"`, query the coauthorship graph for overlap between the query
  author's neighbors and the candidate's known collaborators (via OpenAlex evidence).
  Wire its weight (`_W_COAUTH = 0.10`) into `compute_score` only when signal is available;
  dynamic renormalization already handles absence.
- **DD7. Semantic candidate generation.** New `backend/clustering/semantic.py` using the
  existing ChromaDB collection to fetch top-k semantically-similar values as extra blocking
  candidates (captures acronyms / translations that lexical blocking misses). Feature-flagged
  (`UKIP_ENABLE_SEMANTIC_BLOCKING`) so it degrades gracefully when Chroma is empty.
- **DD8. Evaluation harness.** New `backend/eval/entity_resolution_eval.py` + a small
  labeled fixture set under `backend/eval/fixtures/`. Computes precision/recall/F1 of
  produced clusters vs. gold pairs, swept over thresholds and algorithms. Exposed as a
  pytest (`test_eval_quality.py`) that asserts F1 does not regress below a baseline.

  **Measured baseline (threshold 80, gold fixture `gold_pairs.json`, 15 values / 12 gold pairs):**

  | algorithm | precision | recall | F1     |
  |-----------|-----------|--------|--------|
  | legacy    | 1.00      | 0.75   | 0.857  |
  | blocking  | 1.00      | 0.833  | 0.909  |

  Blocking matches legacy precision while lifting recall (transitive + order-independent
  grouping), so `UKIP_USE_BLOCKING` now defaults **ON**. The harness gate is `F1 ≥ 0.75`.
  Set `UKIP_USE_BLOCKING=0` to fall back to the legacy greedy path.

### Phase 3 — Intelligence & differentiation

- **DD9. Feedback-weighted scoring.** New `backend/authority/feedback.py`. Aggregate
  confirm/reject counts per `(field_name, authority_source)` into a learned prior that
  nudges `_score_identifiers`. Stored in a new `AuthorityScoringFeedback` table, updated on
  confirm/reject, read at scoring time (cached).
- **DD10. Adaptive thresholds.** Per `(field_name, domain)` threshold overrides in a
  `ResolutionThreshold` table, falling back to the global constants. Surfaced in the existing
  domain registry UI.
- **DD11. Explainability UI.** Surface `score_breakdown` + `evidence` (already persisted)
  as a candidate "why this matched" popover in `DisambiguationGroupCard` and the review queue.

## 6. Data model additions

- `AuthorityResolveJob` (Phase 1)
- `AuthorityScoringFeedback` (Phase 3)
- `ResolutionThreshold` (Phase 3)

All carry `org_id` for tenant isolation, migrated additively in `backend/main.py` lifespan
(matching the established migration style).

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Embeddings empty / Chroma unavailable | Feature flag; lexical blocking remains the default path |
| Cache returns stale authority data | TTL + manual invalidation endpoint; cache stores raw, scoring stays live |
| Background worker double-processing | Atomic claim + rowcount check (proven in enrichment_worker) |
| Union-Find changes existing group output | Eval harness gates the change; keep old path behind a flag during rollout |
| Feedback loop amplifies reviewer bias | Cap the feedback prior's contribution (±0.05); log it in `evidence` |

## 8. Rollout order (priority)

1. **Phase 1** (caching → retry → async batch → pagination) — unblocks production at scale.
2. **Phase 2** (blocking+Union-Find → coauthorship → semantic → eval harness).
3. **Phase 3** (feedback weighting → adaptive thresholds → explainability UI).

Each task is independently shippable and test-gated.
