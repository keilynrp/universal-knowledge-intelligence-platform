# Disambiguation & Authority Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the Disambiguation and Authority Control modules to top-market entity-resolution quality and scale, gradually and test-first, by priority order.

**Architecture:** Phase 1 stabilizes and scales (caching, resilient external calls, async batch jobs, server-side pagination). Phase 2 raises matching quality (blocking + Union-Find, coauthorship signal, semantic candidates, evaluation harness). Phase 3 adds intelligence (feedback-weighted scoring, adaptive thresholds, explainability UI).

**Tech Stack:** FastAPI + SQLAlchemy + SQLite/Postgres, `thefuzz`, `cachetools`, ChromaDB (embeddings), existing `backend/circuit_breaker.py` and `enrichment_worker.py` patterns, Next.js frontend, pytest.

**Spec:** `docs/superpowers/specs/2026-05-29-disambiguation-authority-optimization-design.md`

**Conventions (from CLAUDE.md / repo memory):**
- Python env: `.venv/Scripts/python` (Windows). Run tests with `.venv/Scripts/python -m pytest`.
- Tests live in `backend/tests/`; fixtures in `backend/tests/conftest.py` provide `client`, `auth_headers`, `editor_headers`, `viewer_headers`, `db_session`.
- All RawEntity reads go through `backend/services/entity_query.py:entity_base_q`.
- All tables carry `org_id`; migrate additively in `backend/main.py` lifespan.
- Commit per task. Conventional commits. No attribution footer.

---

# PHASE 1 — Stabilization & Scaling (priority 1)

## Task 1: Authority resolution cache

**Files:**
- Create: `backend/authority/cache.py`
- Modify: `backend/authority/resolver.py` (wrap resolver calls)
- Modify: `requirements.txt` (add `cachetools`)
- Test: `backend/tests/test_authority_cache.py`

- [ ] **Step 1: Add dependency**

Add `cachetools` to `requirements.txt`, then `.venv/Scripts/python -m pip install cachetools`.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_authority_cache.py
from backend.authority.cache import ResolverCache

def test_cache_returns_stored_candidates_without_recomputing():
    cache = ResolverCache(ttl=60, maxsize=10)
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return [{"authority_id": "Q1"}]

    first = cache.get_or_load("wikidata", "ACME Corp", "organization", loader)
    second = cache.get_or_load("wikidata", "acme   corp", "organization", loader)  # normalized-equal

    assert first == second == [{"authority_id": "Q1"}]
    assert calls["n"] == 1  # second call served from cache (normalized key)


def test_cache_distinguishes_entity_type():
    cache = ResolverCache(ttl=60, maxsize=10)
    cache.get_or_load("viaf", "Smith", "person", lambda: ["p"])
    out = cache.get_or_load("viaf", "Smith", "organization", lambda: ["o"])
    assert out == ["o"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_authority_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.authority.cache`.

- [ ] **Step 4: Implement minimal cache**

```python
# backend/authority/cache.py
from __future__ import annotations
import os
from threading import Lock
from typing import Callable
from cachetools import TTLCache
from backend.authority.normalize import normalize_name


class ResolverCache:
    def __init__(self, ttl: int | None = None, maxsize: int | None = None) -> None:
        ttl = ttl or int(os.environ.get("UKIP_AUTHORITY_CACHE_TTL", 7 * 24 * 3600))
        maxsize = maxsize or int(os.environ.get("UKIP_AUTHORITY_CACHE_MAXSIZE", 10_000))
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._lock = Lock()

    @staticmethod
    def _key(source: str, value: str, entity_type: str) -> tuple[str, str, str]:
        return (source, normalize_name(value), entity_type)

    def get_or_load(self, source: str, value: str, entity_type: str, loader: Callable):
        key = self._key(source, value, entity_type)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        result = loader()
        with self._lock:
            self._cache[key] = result
        return result


_GLOBAL_CACHE = ResolverCache()


def get_resolver_cache() -> ResolverCache:
    return _GLOBAL_CACHE
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_authority_cache.py -v` → PASS.

- [ ] **Step 6: Wire cache into the orchestrator**

In `backend/authority/resolver.py`, inside the `ThreadPoolExecutor` block in `resolve_all`,
replace the direct `resolver.resolve(...)` submission with a cached loader:

```python
from backend.authority.cache import get_resolver_cache
# ...
cache = get_resolver_cache()
futures = {
    pool.submit(
        cache.get_or_load,
        resolver.source_name, value, entity_type,
        lambda r=resolver: r.resolve(value, entity_type),
    ): resolver.source_name
    for resolver in _RESOLVERS
}
```

- [ ] **Step 7: Run the full authority suite**

Run: `.venv/Scripts/python -m pytest backend/tests/test_sprint15.py backend/tests/test_sprint16.py backend/tests/test_authority_cache.py -v` → all PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/authority/cache.py backend/authority/resolver.py backend/tests/test_authority_cache.py requirements.txt
git commit -m "feat(authority): cache external resolver lookups (TTL, normalized key)"
```

---

## Task 2: Resilient resolver calls (retry + circuit breaker)

**Files:**
- Create: `backend/authority/resilience.py`
- Modify: `backend/authority/resolver.py`
- Test: `backend/tests/test_authority_resilience.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_authority_resilience.py
from backend.authority.resilience import ResilientResolver
from backend.circuit_breaker import CircuitBreaker


class _Flaky:
    source_name = "flaky"
    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0
    def resolve(self, value, entity_type):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient")
        return [{"id": value}]


def test_retries_then_succeeds():
    r = ResilientResolver(_Flaky(fail_times=1), CircuitBreaker("flaky", failure_threshold=5), max_attempts=2, base_delay=0)
    assert r.resolve("X", "person") == [{"id": "X"}]


def test_returns_empty_after_exhausting_retries():
    flaky = _Flaky(fail_times=99)
    r = ResilientResolver(flaky, CircuitBreaker("flaky", failure_threshold=5), max_attempts=2, base_delay=0)
    assert r.resolve("X", "person") == []   # never raises (contract)


def test_open_circuit_short_circuits_to_empty():
    cb = CircuitBreaker("flaky", failure_threshold=1, recovery_timeout=999)
    flaky = _Flaky(fail_times=99)
    r = ResilientResolver(flaky, cb, max_attempts=1, base_delay=0)
    r.resolve("X", "person")          # trips the breaker
    calls_before = flaky.calls
    r.resolve("Y", "person")          # should NOT call the resolver again
    assert flaky.calls == calls_before
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_authority_resilience.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# backend/authority/resilience.py
from __future__ import annotations
import logging
import random
import time
from backend.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)


class ResilientResolver:
    """Wraps a resolver with a circuit breaker + bounded exponential backoff.

    Preserves the resolver contract: never raises, returns [] on failure.
    """
    def __init__(self, resolver, breaker: CircuitBreaker, max_attempts: int = 2, base_delay: float = 0.5):
        self.resolver = resolver
        self.source_name = resolver.source_name
        self.breaker = breaker
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    def resolve(self, value: str, entity_type: str):
        try:
            return self.breaker.call(self._resolve_with_retry, value, entity_type)
        except CircuitOpenError:
            logger.info("Circuit open for '%s' — returning [] for '%s'", self.source_name, value)
            return []
        except Exception as exc:  # defensive: contract is never-raise
            logger.warning("ResilientResolver '%s' final failure: %s", self.source_name, exc)
            return []

    def _resolve_with_retry(self, value: str, entity_type: str):
        last_exc = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self.resolver.resolve(value, entity_type)
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_attempts:
                    delay = self.base_delay * (2 ** (attempt - 1)) + random.uniform(0, self.base_delay)
                    time.sleep(delay)
        raise last_exc if last_exc else RuntimeError("resolver failed")
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_authority_resilience.py -v` → PASS.

- [ ] **Step 5: Wire into the orchestrator**

In `backend/authority/resolver.py`, build one breaker per source at module load and wrap each
resolver in `ResilientResolver`, then call `.resolve` through the cache loader (compose with Task 1):

```python
from backend.authority.resilience import ResilientResolver
from backend.circuit_breaker import CircuitBreaker

_BREAKERS = {r.source_name: CircuitBreaker(r.source_name, failure_threshold=3, recovery_timeout=60.0) for r in _RESOLVERS}
_RESILIENT = [ResilientResolver(r, _BREAKERS[r.source_name]) for r in _RESOLVERS]
# iterate _RESILIENT instead of _RESOLVERS in resolve_all's loader
```

- [ ] **Step 6: Run authority suite**

Run: `.venv/Scripts/python -m pytest backend/tests/ -k "authority or sprint15 or sprint16 or resilience or cache" -v` → PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/authority/resilience.py backend/authority/resolver.py backend/tests/test_authority_resilience.py
git commit -m "feat(authority): resilient resolver calls (retry + circuit breaker)"
```

---

## Task 3: Async batch resolution job

**Files:**
- Modify: `backend/models.py` (add `AuthorityResolveJob`)
- Modify: `backend/main.py` (migration + worker task spawn)
- Create: `backend/authority/batch_worker.py`
- Modify: `backend/routers/authority.py` (`/authority/resolve/batch` enqueues; add `/authority/jobs/{id}`)
- Test: `backend/tests/test_authority_batch_job.py`

- [ ] **Step 1: Write the failing test (model + enqueue)**

```python
# backend/tests/test_authority_batch_job.py
def test_batch_enqueue_returns_job_pending(client, editor_headers):
    res = client.post("/authority/resolve/batch",
                      json={"field_name": "author", "entity_type": "person", "limit": 5},
                      headers=editor_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "pending"
    assert "job_id" in body


def test_job_status_endpoint(client, editor_headers):
    job_id = client.post("/authority/resolve/batch",
                         json={"field_name": "author", "entity_type": "person", "limit": 5},
                         headers=editor_headers).json()["job_id"]
    res = client.get(f"/authority/jobs/{job_id}", headers=editor_headers)
    assert res.status_code == 200
    assert res.json()["status"] in {"pending", "processing", "done", "failed"}


def test_sync_flag_preserves_legacy_behavior(client, editor_headers):
    res = client.post("/authority/resolve/batch?sync=true",
                      json={"field_name": "author", "entity_type": "person", "limit": 1},
                      headers=editor_headers)
    assert res.status_code == 201
    assert "records" in res.json()   # legacy synchronous shape
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_authority_batch_job.py -v` → FAIL.

- [ ] **Step 3: Add the model**

In `backend/models.py`:

```python
class AuthorityResolveJob(Base):
    __tablename__ = "authority_resolve_jobs"
    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=True, index=True)
    field_name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    params_json = Column(Text, nullable=True)          # limit, skip_existing, ...
    status = Column(String, default="pending", index=True)  # pending|processing|done|failed
    total = Column(Integer, default=0)
    processed = Column(Integer, default=0)
    records_created = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Add additive migration in `backend/main.py` lifespan**

Follow the existing `inspect(engine).get_table_names()` / `CREATE TABLE` style used for prior
migrations; create `authority_resolve_jobs` if missing.

- [ ] **Step 5: Implement the worker**

```python
# backend/authority/batch_worker.py
"""Background worker that drains AuthorityResolveJob rows (atomic claim)."""
import asyncio, json, logging
from datetime import datetime, timezone
from sqlalchemy import update
from backend.database import SessionLocal
from backend import models
from backend.authority.resolver import resolve_all
from backend.authority.hierarchical_fallback import apply_hierarchical_fallback
from backend.authority.base import ResolveContext

logger = logging.getLogger(__name__)
_POLL_SECONDS = 3


def _claim_one(db):
    job = db.query(models.AuthorityResolveJob).filter_by(status="pending").order_by(models.AuthorityResolveJob.id).first()
    if not job:
        return None
    res = db.execute(update(models.AuthorityResolveJob)
                     .where(models.AuthorityResolveJob.id == job.id, models.AuthorityResolveJob.status == "pending")
                     .values(status="processing"))
    db.commit()
    return job if res.rowcount == 1 else None


def _run_job(db, job): ...  # resolve distinct field values (chunked), persist records, update counters

async def run_batch_worker():
    while True:
        try:
            db = SessionLocal()
            job = _claim_one(db)
            if job:
                _run_job(db, job)
            db.close()
        except Exception:
            logger.exception("batch worker iteration failed")
        await asyncio.sleep(_POLL_SECONDS)
```

Spawn it in the lifespan with `asyncio.create_task(run_batch_worker())` (mirror the enrichment worker)
and reset stale `processing` jobs to `pending` on startup.

- [ ] **Step 6: Refactor the endpoint**

In `backend/routers/authority.py`, `resolve_authority_batch` gains `sync: bool = Query(False)`.
When `sync` → keep current synchronous body. Otherwise create a `pending` job row and return
`{"job_id": ..., "status": "pending"}`. Add `GET /authority/jobs/{job_id}` (org-scoped) returning
status + counters.

- [ ] **Step 7: Run to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_authority_batch_job.py -v` → PASS.
Then run prior authority tests to confirm no regression.

- [ ] **Step 8: Commit**

```bash
git add backend/models.py backend/main.py backend/authority/batch_worker.py backend/routers/authority.py backend/tests/test_authority_batch_job.py
git commit -m "feat(authority): async batch resolution job with progress endpoint"
```

---

## Task 4: Server-side pagination for grouping endpoints

**Files:**
- Modify: `backend/routers/deps.py:_build_disambig_groups` (accept `skip`/`limit`, return total)
- Modify: `backend/routers/disambiguation.py:disambiguate_field`
- Modify: `backend/routers/authority.py:get_authority_view`
- Modify: `frontend/app/authority/DisambiguationTab.tsx` (server pagination)
- Test: `backend/tests/test_disambig_pagination.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_disambig_pagination.py
def test_disambiguate_paginates_and_reports_total(client, auth_headers, seeded_variation_groups):
    res = client.get("/disambiguate/author?threshold=80&skip=0&limit=5", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert len(body["groups"]) <= 5
    assert body["total_groups"] >= len(body["groups"])
    assert res.headers["X-Total-Count"] == str(body["total_groups"])
```

(Add a `seeded_variation_groups` fixture that inserts ≥12 near-duplicate values for `author`.)

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_disambig_pagination.py -v` → FAIL.

- [ ] **Step 3: Implement**

`_build_disambig_groups` materializes the full group list (unchanged), then returns
`(groups[skip:skip+limit], len(groups))`. Endpoints pass `skip`/`limit` (`Query(ge=0)` /
`Query(ge=1, le=500)`), set `response.headers["X-Total-Count"]`, and return the page.

- [ ] **Step 4: Run to verify it passes** → PASS.

- [ ] **Step 5: Update the frontend**

In `DisambiguationTab.tsx`, replace client `.slice()` with server `skip`/`limit` query params;
read total from `X-Total-Count`; refetch on page change.

- [ ] **Step 6: Frontend build check**

Run: `cd frontend && npm run build` (or `tsc --noEmit`) → no type errors.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/deps.py backend/routers/disambiguation.py backend/routers/authority.py frontend/app/authority/DisambiguationTab.tsx backend/tests/test_disambig_pagination.py
git commit -m "feat(disambiguation): server-side pagination with X-Total-Count"
```

> **Phase 1 checkpoint:** Run full backend suite `.venv/Scripts/python -m pytest backend/tests/ -q`. All green before starting Phase 2.

---

# PHASE 2 — Matching Quality (priority 2)

## Task 5: Union-Find utility

**Files:**
- Create: `backend/clustering/union_find.py`
- Test: `backend/tests/test_union_find.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_union_find.py
from backend.clustering.union_find import UnionFind

def test_transitive_closure():
    uf = UnionFind(["a", "b", "c", "d"])
    uf.union("a", "b")
    uf.union("b", "c")          # a-b-c connected; d alone
    comps = uf.components()
    assert sorted(len(c) for c in comps) == [1, 3]
    assert uf.connected("a", "c") is True
    assert uf.connected("a", "d") is False
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** path-compression + union-by-rank `UnionFind` with `add`, `union`,
  `find`, `connected`, `components() -> list[list]`.

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Commit** `feat(clustering): add Union-Find for transitive grouping`.

---

## Task 6: Blocking-based clustering

**Files:**
- Create: `backend/clustering/blocking.py`
- Modify: `backend/routers/deps.py:_build_disambig_groups` (`token_sort`/`ngram` paths use blocking + Union-Find behind flag `UKIP_USE_BLOCKING`)
- Test: `backend/tests/test_blocking_clustering.py`

- [ ] **Step 1: Failing test** — assert (a) order-independence (shuffling input yields the same
  components) and (b) transitive grouping (A≈B, B≈C ⇒ {A,B,C}), and (c) results match the legacy
  greedy output on a small fixture within tolerance.

```python
def test_blocking_is_order_independent():
    from backend.clustering.blocking import cluster_values
    vals = ["Univ of Texas", "University of Texas", "U. of Texas", "MIT"]
    a = cluster_values(vals, threshold=80)
    b = cluster_values(list(reversed(vals)), threshold=80)
    norm = lambda groups: sorted(sorted(g) for g in groups)
    assert norm(a) == norm(b)

def test_blocking_transitive():
    from backend.clustering.blocking import cluster_values
    groups = cluster_values(["John Smith", "J. Smith", "Smith, John"], threshold=70)
    assert any(len(g) == 3 for g in groups)
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `blocking_keys(value) -> set[str]` (fingerprint + phonetic + sorted
  first-3-token prefix) and `cluster_values(values, threshold)` → build blocks, compare only
  intra-block pairs with `fuzz.token_sort_ratio`, union ≥threshold pairs, return components.

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Integrate** behind `UKIP_USE_BLOCKING` in `_build_disambig_groups`; legacy path
  remains default until the eval harness (Task 9) validates the switch.

- [ ] **Step 6: Run disambiguation suite → PASS.**

- [ ] **Step 7: Commit** `feat(clustering): blocking + Union-Find clustering (flagged)`.

---

## Task 7: Coauthorship scoring signal

**Files:**
- Modify: `backend/authority/scoring.py` (`_score_coauthorship`, wire weight)
- Create: `backend/authority/coauthorship_signal.py` (graph lookup adapter)
- Modify: `backend/authority/resolver.py` (pass coauthor context)
- Modify: `backend/authority/base.py:ResolveContext` (add `coauthors: list[str] | None`)
- Test: `backend/tests/test_coauthorship_signal.py`

- [ ] **Step 1: Failing test**

```python
def test_coauthorship_boosts_score_for_shared_collaborators():
    from backend.authority.scoring import compute_score
    high, *_ = compute_score(value="J Smith", authority_source="openalex", authority_id="A1",
                             canonical_label="John Smith", description="MIT",
                             coauthors_overlap=0.8)
    low, *_ = compute_score(value="J Smith", authority_source="openalex", authority_id="A1",
                            canonical_label="John Smith", description="MIT",
                            coauthors_overlap=0.0)
    assert high > low
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `_score_coauthorship(overlap)` returning the overlap directly (0–1);
  add `coauthors_overlap` param to `compute_score`; set `nominal_weights["coauthorship"] = _W_COAUTH`
  only when overlap is provided (dynamic renormalization already handles `0.0`/absence).

- [ ] **Step 4: Implement the adapter** in `coauthorship_signal.py`: given query author + candidate
  evidence, compute Jaccard overlap of collaborator sets from `backend/coauthorship/`. Resolver
  computes overlap per candidate when `entity_type == "person"` and a coauthor context exists.

- [ ] **Step 5: Run → PASS.** Run authority suite → PASS.

- [ ] **Step 6: Commit** `feat(authority): activate coauthorship scoring signal for persons`.

---

## Task 8: Semantic candidate generation (ChromaDB)

**Files:**
- Create: `backend/clustering/semantic.py`
- Modify: `backend/clustering/blocking.py` (merge semantic neighbors into blocks when flag on)
- Test: `backend/tests/test_semantic_blocking.py`

- [ ] **Step 1: Failing test** (mock the Chroma collection) — assert semantic neighbors are added
  as extra comparison candidates and that an empty/unavailable Chroma degrades to lexical-only.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `semantic_neighbors(value, k) -> list[str]` querying the existing
  Chroma collection; guard with `UKIP_ENABLE_SEMANTIC_BLOCKING` and try/except → `[]` on failure.

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Commit** `feat(clustering): semantic candidate generation via embeddings (flagged)`.

---

## Task 9: Evaluation harness

**Files:**
- Create: `backend/eval/entity_resolution_eval.py`
- Create: `backend/eval/fixtures/gold_pairs.json` (small labeled set: matching/non-matching value pairs)
- Test: `backend/tests/test_eval_quality.py`

- [ ] **Step 1: Failing test**

```python
def test_blocking_does_not_regress_below_baseline():
    from backend.eval.entity_resolution_eval import evaluate
    metrics = evaluate(algorithm="blocking", threshold=80)
    assert metrics["f1"] >= 0.75   # baseline gate; tune from first measured run
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `evaluate(algorithm, threshold)` → cluster the fixture values, derive
  predicted same-cluster pairs, compare to gold pairs, return `{precision, recall, f1}`. Add a
  sweep helper `evaluate_sweep()` printing a table across thresholds/algorithms.

- [ ] **Step 4: Run → PASS** (set the baseline from the first real measurement).

- [ ] **Step 5: Validate the Phase-2 switch** — with the harness green, flip `UKIP_USE_BLOCKING`
  default to `True` (and document in spec/README). Re-run the disambiguation suite.

- [ ] **Step 6: Commit** `feat(eval): entity-resolution quality harness + enable blocking by default`.

> **Phase 2 checkpoint:** full suite green; record the measured precision/recall/F1 baseline in the spec.

---

# PHASE 3 — Intelligence & Differentiation (priority 3)

## Task 10: Feedback-weighted scoring

**Files:**
- Modify: `backend/models.py` (`AuthorityScoringFeedback`)
- Modify: `backend/main.py` (migration)
- Create: `backend/authority/feedback.py`
- Modify: `backend/routers/authority.py` (confirm/reject update feedback)
- Modify: `backend/authority/scoring.py` (apply capped prior)
- Test: `backend/tests/test_scoring_feedback.py`

- [ ] **Step 1: Failing test** — confirming records from a source repeatedly raises that source's
  prior (bounded ±0.05); the contribution is logged in `evidence`.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `AuthorityScoringFeedback(field_name, authority_source, confirmed, rejected, org_id)`;
  `feedback.py` computes a `[-0.05, +0.05]` adjustment from confirm/reject ratio (cached); confirm/reject
  endpoints increment counters; `_score_identifiers` adds the adjustment and appends an `evidence` line.

- [ ] **Step 4: Run → PASS.** Re-run eval harness to confirm no F1 regression.

- [ ] **Step 5: Commit** `feat(authority): feedback-weighted source priors (bounded, audited)`.

---

## Task 11: Adaptive thresholds per field/domain

**Files:**
- Modify: `backend/models.py` (`ResolutionThreshold`)
- Modify: `backend/main.py` (migration)
- Modify: `backend/authority/scoring.py` (accept override thresholds)
- Modify: `backend/routers/disambiguation.py` + `authority.py` (load overrides)
- Modify: `frontend/app/domains/page.tsx` (threshold editor)
- Test: `backend/tests/test_adaptive_thresholds.py`

- [ ] **Step 1: Failing test** — a `(field, domain)` override changes the resolution_status
  boundaries; absence falls back to global constants.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** model + lookup (org/domain/field scoped) + plumb optional thresholds
  into `compute_score`; expose CRUD endpoint reused by the domain registry UI.

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Frontend** threshold editor in the domain registry; `tsc --noEmit` clean.

- [ ] **Step 6: Commit** `feat(authority): adaptive per-field/domain resolution thresholds`.

---

## Task 12: Explainability UI

**Files:**
- Modify: `frontend/app/components/DisambiguationGroupCard.tsx` (candidate "why" popover)
- Modify: `frontend/app/authority/ReviewQueueRecordsTable.tsx` (breakdown column)
- Test: `frontend/` component test or Playwright E2E (`e2e-runner`)

- [ ] **Step 1: Write a component/E2E test** asserting the popover renders `score_breakdown`
  bars and `evidence` lines for a candidate (data already returned by the API).

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** a `ScoreBreakdown` sub-component (bars per signal: identifiers/name/
  affiliation/coauthorship) + evidence list; mount it in the card and the review table row.

- [ ] **Step 4: Run → PASS;** `npm run build` clean.

- [ ] **Step 5: Commit** `feat(ui): explainable scoring breakdown + evidence in disambiguation/review`.

> **Phase 3 checkpoint:** full backend suite + frontend build green; eval F1 ≥ recorded baseline.

---

## Cross-cutting reminders

- After each task: `code-reviewer` (and `security-reviewer` for the new endpoints/models per repo rules).
- Keep `org_id` isolation on every new query (`scope_query_to_org` / `entity_base_q`).
- Feature-flag every behavior change that can alter existing output; flip defaults only after the eval harness gates it.
- Update `MEMORY.md` topic files as each phase lands.
