# Redis Distributed Cache — Design Spec

**Date:** 2026-06-02
**Status:** Approved (brainstorming)
**Sub-project:** 1 of 2 in the "Redis as enabler" initiative (this = distributed cache + Redis foundation; sub-project 2 = task queue, separate spec).

---

## Goal

Replace UKIP's 5+ in-process `cachetools`/dict caches with a Redis-backed distributed cache so cache state is **coherent across worker processes** and **survives deploys**, while introducing the shared Redis foundation (client, config, connection pool) that the later task-queue sub-project will build on. The change is **behaviorally inert until `REDIS_URL` is configured in production** — `REDIS_URL` is the rollout switch.

## Non-Goals (YAGNI)

- No task queue / worker decoupling (that is sub-project 2).
- No deep health check or full graceful shutdown (movement #3 — only a non-blocking Redis `ping()` at startup and `close()` at shutdown are added here).
- No L1 in-process tier in front of Redis.
- No invalidation-by-tags, no hit-rate metrics. Future iterations if justified.

## Background: current cache surface

All in-process, invisible across workers, lost on every deploy:

| Cache | File | Interface shape | Value type | TTL |
|---|---|---|---|---|
| `ResolverCache` | `backend/authority/cache.py` | `get_or_load(source, value, entity_type, loader)` | `list[AuthorityCandidate]` or `list[dict]` | 7 days |
| thresholds `_cache` | `backend/authority/thresholds.py` | module TTLCache, get-or-compute + `clear_cache()` | float/dict | 300s |
| feedback `_cache` | `backend/authority/feedback.py` | module TTLCache, get-or-compute + `pop` | float/dict | 300s |
| `_StatusCache` | `backend/services/derived_status_service.py` | `get(key)` / `set(key,val)` / `invalidate(domain_id)` | dict | 30s |
| `_SimpleCache` ×2 | `backend/routers/analytics.py` | `get(key)` / `set(key,val)` / `invalidate(prefix)` | dict/list | 300s / 120s |

**Latent correctness bug this fixes:** `invalidate_derived_status_cache(domain_id)` is called from `enrichment_worker.py:475` and `graph_materializer.py:628`, but today it only evicts the *calling process's* cache. Other workers keep serving stale derived status. A Redis-backed cache makes invalidation propagate across all processes.

---

## Architecture

**Strategy pattern: one cache interface, two backends selected by `REDIS_URL`.**

```
            CacheBackend (interface)
        get / set / get_or_load / invalidate_prefix
                       |
          ┌────────────┴────────────┐
   RedisBackend                InProcessBackend
   (JSON, TTL, fail-open,      (wraps cachetools.TTLCache,
    SCAN+DEL)                   parity with today)
   selected when               selected when
   REDIS_URL is set            REDIS_URL is unset
   (production)                (tests / local dev)
```

### Decisions (all approved)

1. **Backend selection by `REDIS_URL`.** Set → `RedisBackend`; unset → `InProcessBackend` (today's behavior). This keeps the cheap test tier intact (suite runs with no Redis) and allows local dev without Redis. `REDIS_URL` is therefore also the production rollout switch: setting it = cutover, unsetting it = rollback. No separate feature flag, no data migration (caches are ephemeral and self-repopulate).

2. **Fail-open.** Any Redis exception (timeout, outage, failover) is logged and treated as a cache *miss* → value is recomputed via the `loader`/source. App availability never depends on Redis. Errors never propagate to the request.

3. **JSON serialization with boundary adapters.** The backend serializes/deserializes JSON. Caches storing plain numbers/dicts use JSON directly. `ResolverCache` (which stores `AuthorityCandidate` dataclasses) passes a serializer/deserializer pair: serialize normalizes to `list[dict]` (via `dataclasses.asdict` when needed), deserialize reconstructs `AuthorityCandidate` when the call-site expects objects. No pickle.

4. **Key namespacing.** Each cache gets a prefix (`authority:resolver`, `authority:thresholds`, `authority:feedback`, `derived_status`, `analytics`, `dashboard`). `invalidate_prefix(prefix)` maps to `SCAN MATCH <global_prefix>:<ns>:<prefix>*` + `DEL` on Redis, and to key-filtering on the in-process backend. A global prefix (`UKIP_CACHE_PREFIX`) namespaces the whole app so multiple deployments can share one Redis instance.

---

## Components & File Structure

All new code under `backend/cache/`:

```
backend/cache/
├── __init__.py          # Public API: get_cache(namespace, ttl, serializer=None,
│                        #   deserializer=None) -> CacheBackend
├── base.py              # CacheBackend (ABC/Protocol): get, set, get_or_load,
│                        #   invalidate_prefix; Serializer/Deserializer types
├── redis_backend.py     # RedisBackend — JSON, TTL, fail-open, SCAN+DEL.
│                        #   Uses the shared redis-py pool; lazy connection.
├── inprocess_backend.py # InProcessBackend — wraps cachetools.TTLCache behind
│                        #   the same interface (parity with current behavior).
├── client.py            # redis-py connection pool singleton built from REDIS_URL;
│                        #   ping() helper for the startup probe; close() for shutdown.
└── config.py            # REDIS_URL, UKIP_CACHE_PREFIX, socket_connect_timeout,
                         #   socket_timeout.
```

### Central factory

```python
from backend.cache import get_cache
_resolver_cache = get_cache("authority:resolver", ttl=7 * 24 * 3600,
                            serializer=..., deserializer=...)
```

`get_cache` decides the backend once based on `REDIS_URL`. Call-sites are backend-agnostic.

### Interface (CacheBackend)

```
get(key: str) -> Any | None
set(key: str, value: Any, ttl: int | None = None) -> None
get_or_load(key: str, loader: Callable[[], Any], ttl: int | None = None) -> Any
invalidate_prefix(prefix: str = "") -> int   # returns count evicted
```

The two existing interface shapes both map onto this:
- `get`/`set`/`invalidate(prefix)` caches (analytics, derived_status) map directly.
- `get_or_load(...)` caches (ResolverCache) build a namespaced key from their tuple and call `get_or_load`.

### New dependencies

- `redis>=5` (redis-py — URL connection, pooling). Added to `requirements.txt`.
- `fakeredis` — **test-only**, optional; used only by tests that exercise the Redis path.

### Foundation hooks in `backend/main.py` lifespan

- **Startup:** non-blocking `client.ping()` to log Redis reachability. Fail-open: on failure, log a warning and continue.
- **Shutdown:** `client.close()` added to the existing cleanup block.
- Deep health/liveness endpoints and full graceful drain are out of scope (movement #3).

---

## Per-cache migration mapping

| Current cache | Namespace | JSON mapping | Invalidation mapping |
|---|---|---|---|
| `ResolverCache` | `authority:resolver` | `AuthorityCandidate`/dict ↔ `asdict`/reconstruct | TTL (7d) |
| thresholds `_cache` | `authority:thresholds` | float/dict direct | TTL 300s; `clear_cache()` → `invalidate_prefix("")` |
| feedback `_cache` | `authority:feedback` | float/dict direct | TTL 300s; `pop` → `invalidate_prefix(scope_key)` |
| `_StatusCache` | `derived_status` | dict direct | TTL 30s; `invalidate(domain)` → `invalidate_prefix("<domain>:")` |
| `_SimpleCache` (analytics) | `analytics` | dict/list direct | TTL 300s; `invalidate(prefix)` |
| `_SimpleCache` (dashboard) | `dashboard` | dict/list direct | TTL 120s; `invalidate(prefix)` |

### Two notable cases

**1. `ResolverCache` — the only one storing objects.** Its public `get_or_load(source, value, entity_type, loader)` signature is **preserved**. Internally it builds the namespaced key `authority:resolver:<source>:<normalize_name(value)>:<entity_type>` and delegates to the backend's `get_or_load` with a serializer (normalize to `list[dict]`) and deserializer (reconstruct `AuthorityCandidate` when expected). `backend/authority/resolver.py:170` does not change.

**2. `derived_status` — the correctness win.** `invalidate(domain)` becomes `invalidate_prefix("<domain>:")` on Redis, so eviction propagates to **all** processes, fixing the latent cross-worker staleness bug.

### Migration principle

**Preserve every public signature; change only the cache internals.** Each existing cache (`get_or_load`, `status_cache.get/set/invalidate`, `invalidate_analytics_cache`, `clear_cache`, etc.) keeps its API and delegates to `get_cache(...)`. The ~20 call-sites do not change. Low risk, bounded diff, migrated one cache per commit.

---

## Error Handling

- Every Redis operation in `RedisBackend` is wrapped; on exception → `logger.warning` (throttled / debug-level on hot paths to avoid log spam) + fail-open fallback (treat as miss / no-op).
- Connection errors during the startup `ping()` are logged and swallowed (service still boots).
- JSON (de)serialization errors are treated as a miss (and the bad key may be deleted) rather than raising.

## Testing Strategy

- **Default suite unchanged:** tests run with `REDIS_URL` unset → `InProcessBackend` → existing cache tests (`test_adaptive_thresholds`, `test_derived_status`, `test_concept_hierarchy`, `conftest.py` cache invalidation) pass without modification. No Redis dependency in the default suite.
- **New `RedisBackend` tests using `fakeredis`** (in-memory, no real Redis): JSON round-trip, fail-open (client raises → falls back to loader), `invalidate_prefix` via SCAN+DEL, and the headline test — **two backend instances sharing one `fakeredis` server → cross-"worker" invalidation** (proves the derived_status correctness win).
- **Parity tests:** the same get/set/get_or_load/invalidate battery run against both backends to guarantee identical behavior.
- TDD per repo rules, 80%+ coverage on new code.

## Rollout

- Merge is inert: `REDIS_URL` unset → `InProcessBackend` → zero behavior change.
- **Cutover:** set `REDIS_URL` in the production environment. **Rollback:** unset it. No data migration (caches self-repopulate).
- Call-sites migrated one-per-commit (resolver → thresholds → feedback → derived_status → analytics/dashboard), each green before the next.
- `REDIS_URL`, `UKIP_CACHE_PREFIX`, and recommended timeouts documented in `.env.example` + an ops note.

## Definition of Done

- `backend/cache/` package with `CacheBackend`, `RedisBackend`, `InProcessBackend`, `client`, `config`, and `get_cache` factory.
- All 6 caches delegate to `get_cache(...)` with public signatures unchanged.
- `redis>=5` in requirements; `fakeredis` test-only.
- Startup `ping()` + shutdown `close()` hooks in lifespan.
- Full backend suite passes unchanged with `REDIS_URL` unset.
- New `fakeredis` tests prove fail-open + cross-worker invalidation.
- `.env.example` + ops note updated.
