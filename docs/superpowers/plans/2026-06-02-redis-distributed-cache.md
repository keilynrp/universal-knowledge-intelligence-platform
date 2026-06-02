# Redis Distributed Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace UKIP's 6 in-process `cachetools`/dict caches with a Redis-backed distributed cache (coherent across worker processes, survives deploys), behaviorally inert until `REDIS_URL` is set.

**Architecture:** Strategy pattern — one `CacheBackend` interface with two implementations (`RedisBackend` / `InProcessBackend`) selected by `REDIS_URL`. JSON serialization, fail-open on Redis errors, key namespacing per cache. Each existing cache keeps its public signature and delegates internals to a `get_cache(namespace, ...)` factory.

**Tech Stack:** Python 3.13, FastAPI, redis-py (`redis>=5`), `fakeredis` (test-only), `cachetools` (in-process backend), pytest.

**Spec:** `docs/superpowers/specs/2026-06-02-redis-distributed-cache-design.md` (read it first).

**Branch:** `feat/redis-distributed-cache` (already created; spec already committed here).

**Interpreter:** `.venv\Scripts\python` (Windows). Tests: `.venv\Scripts\python -m pytest`.

**Commit hooks:** `--no-verify` is BLOCKED by a repo hook. Never bypass. LF→CRLF warnings are benign.

---

## Context: the 6 caches being migrated (verified signatures)

| # | Object | File | Public API (unchanged) | Key | Value | Namespace / TTL |
|---|---|---|---|---|---|---|
| 1 | `ResolverCache` | `backend/authority/cache.py` | `get_or_load(source, value, entity_type, loader)` | tuple `(source, normalize_name(value), entity_type)` | `list[AuthorityCandidate]`/`list[dict]` | `authority:resolver` / 7d |
| 2 | `_cache` | `backend/authority/thresholds.py` | `get_thresholds(...)`, `clear_cache()` | tuple `(org_id, domain_id, field_name)` | `Optional[ResolutionThresholds]` (**caches None!**) | `authority:thresholds` / 300s |
| 3 | `_cache` | `backend/authority/feedback.py` | `get_source_prior(...)`, `record_outcome(...)`, `clear_cache()` | tuple `(org_id, field_name, authority_source)` | `float` | `authority:feedback` / 300s |
| 4 | `status_cache` (`_StatusCache`) | `backend/services/derived_status_service.py` | `get(key)`, `set(key,val)`, `invalidate(domain_id)` | str (`"<domain>:..."`) | dict | `derived_status` / 30s |
| 5/6 | `_analytics_cache`, `_dashboard_cache` (`_SimpleCache`) | `backend/routers/analytics.py` | `get(key)`, `set(key,val)`, `invalidate(prefix)->int`, plus module fns `invalidate_analytics_cache`/`invalidate_analytics_for_domain` | str | dict/list | `analytics` / 300s, `dashboard` / 120s |

**Critical subtleties the plan handles:**
- **Negative caching (cache #2):** `thresholds` caches `None` (a valid "no override" result). The backend must distinguish *absent key* (miss → compute) from *cached `None`* (hit). JSON `null` solves this: a key holding `"null"` is a hit.
- **Tuple keys (caches #2, #3):** keys contain `None` elements (e.g. `org_id=None`, `domain_id=None`). Need deterministic string conversion with a `None` sentinel that cannot collide with a real value.
- **`get_or_load` caches falsy/None results** (it is memoization, not "cache-if-truthy").
- **Private-internals coupling (cache #5/6):** `derived_status_service._compute_executive_dashboard_snapshot` (≈ lines 258–283) reads `_dashboard_cache._lock/._ttl/._store` directly to test "is this domain's dashboard warm?". Migrate it to the new `exists_prefix("dashboard_<domain>")`.

---

## Cross-Cutting Execution Notes (READ FIRST — apply to every task)

These resolve real risks found in plan review against the live code. Violating any of them will break the suite or a call-site.

**A. Module-level singletons + backend selection.** Every migrated cache is a module-level singleton built **at import time** (`_GLOBAL_CACHE`, `_cache`, `status_cache`, `_analytics_cache`, `_dashboard_cache`). `get_cache()` therefore picks the backend once, at import. The default test suite never sets `REDIS_URL`, so all singletons are `InProcessBackend` — that is what keeps "suite unchanged" true. **Do NOT rely on monkeypatching `config.REDIS_URL` after import** to test the Redis path — the singleton is already built. Instead, Redis-path tests MUST inject a `fakeredis`-backed backend directly: either construct `RedisBackend(..., client_factory=lambda: fake)` and exercise it, or replace the module-level singleton (e.g. `monkeypatch.setattr(thresholds, "_backend", RedisBackend(..., client_factory=lambda: fake))`). Never depend on a `REDIS_URL` env var leaking into the suite.

**B. Always stringify keys with `make_key` before any backend call.** Caches #2 and #3 use **tuple** keys (with `None` elements). `RedisBackend` requires `str` keys. Every `get`/`get_or_load`/`delete`/`set` call must pass `make_key(tuple)` — never the raw tuple. (InProcessBackend would tolerate tuples, Redis will not; be consistent.)

**C. Preserve module-level NAMES and the `None`-on-miss contract.** Other modules import these singletons **by name**:
- `backend/routers/analytics_analyzers.py` → `from backend.routers.analytics import _analytics_cache` and does `if cached is not None` (~10 call-sites).
- `backend/routers/admin_data_fixes.py:282` → `from backend.routers.analytics import _analytics_cache`; calls `_analytics_cache.invalidate("coauth_")` expecting an **int** return.
- `backend/tests/test_sprint83.py:14` → `from backend.routers.analytics import _SimpleCache` (the class name itself).
- `backend/tests/conftest.py:342-343` → `_analytics_cache.invalidate()` / `_dashboard_cache.invalidate()` with **no argument**.

Therefore: `_analytics_cache`, `_dashboard_cache`, and `status_cache` must remain the same module-level names, assigned to a **thin wrapper** (NOT a bare `CacheBackend`). The wrapper's `.get()` translates `MISS → None`; `.invalidate(prefix="")` returns `int` and accepts the zero-arg form; `.get`/`.set` keep their shapes. Keep the `_SimpleCache` class defined in `analytics.py` (now as the wrapper, or keep the name) so `test_sprint83.py`'s import survives — or update that test as part of Task 10.

**D. `clear_cache()` return type.** `thresholds.clear_cache()` and `feedback.clear_cache()` currently return `None`; delegating to `invalidate_prefix("")` makes them return `int`. Grep call-sites (`git grep -n "clear_cache()"`) and confirm none depend on the `None` return (tests call it for effect only — fine, but verify).

**E. Preserve exact invalidation prefix strings.** Pass the SAME prefix strings currently given to `_SimpleCache.invalidate` / `_StatusCache.invalidate` straight through to `invalidate_prefix`/`exists_prefix` (application-level prefix, WITHOUT the Redis namespace — the backend prepends `GLOBAL_PREFIX:namespace:`). Examples that must not be normalized: `_StatusCache.invalidate(domain_id)` → prefix `f"{domain_id}:"`; `invalidate_analytics_for_domain` → `f"dashboard_{domain_id}"` (no trailing separator, per `analytics.py`).

---

## File Structure

```
backend/cache/
├── __init__.py          # get_cache(...) factory + re-exports
├── config.py            # env reads: REDIS_URL, UKIP_CACHE_PREFIX, timeouts
├── client.py            # redis-py pool singleton, ping(), close()
├── base.py              # CacheBackend ABC, key-stringify helper, _MISS sentinel
├── inprocess_backend.py # cachetools-backed implementation
└── redis_backend.py     # redis-py JSON implementation, fail-open
backend/tests/
└── test_cache_*.py      # one test module per task (see tasks)
```

`CacheBackend` interface (final):
```
get(key) -> Any | _MISS
set(key, value, ttl=None) -> None
get_or_load(key, loader, ttl=None) -> Any      # caches None results too
delete(key) -> bool
invalidate_prefix(prefix="") -> int            # always int
exists_prefix(prefix) -> bool
```
`get` returns a module-level `_MISS` sentinel (not `None`) so callers can cache `None`. The convenience caches (#4,#5,#6) that want `None`-on-miss translate `_MISS` → `None` in their own thin wrappers (their public `get` keeps returning `None`).

---

## Task 1: Config + Redis client foundation

**Files:**
- Create: `backend/cache/__init__.py` (empty for now)
- Create: `backend/cache/config.py`
- Create: `backend/cache/client.py`
- Modify: `requirements.txt` (add `redis>=5`, `fakeredis>=2` test-only)
- Test: `backend/tests/test_cache_client.py`

- [ ] **Step 1: Add dependencies.** Append to `requirements.txt` after the `cachetools>=5.3.0` line:
```
redis>=5.0.0
# test-only: in-memory Redis used by the cache test suite
fakeredis>=2.21.0
```
Install: `.venv\Scripts\python -m pip install "redis>=5.0.0" "fakeredis>=2.21.0"`

- [ ] **Step 2: Write the failing test** `backend/tests/test_cache_client.py`:
```python
import fakeredis
from backend.cache import client as cache_client


def test_ping_returns_false_when_unconfigured(monkeypatch):
    monkeypatch.setattr(cache_client, "_pool", None, raising=False)
    monkeypatch.setattr(cache_client.config, "REDIS_URL", "", raising=False)
    assert cache_client.ping() is False


def test_get_redis_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(cache_client, "_pool", None, raising=False)
    monkeypatch.setattr(cache_client.config, "REDIS_URL", "", raising=False)
    assert cache_client.get_redis() is None


def test_ping_true_with_fakeredis(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setattr(cache_client, "get_redis", lambda: fake)
    assert cache_client.ping() is True
```

- [ ] **Step 3: Run — expect failure** (`ModuleNotFoundError: backend.cache.client`):
`.venv\Scripts\python -m pytest backend/tests/test_cache_client.py -v`

- [ ] **Step 4: Implement `backend/cache/config.py`:**
```python
"""Runtime configuration for the distributed cache layer."""
import os

# When empty/unset, the cache factory selects the in-process backend
# (today's behavior). Setting this in production is the Redis cutover switch.
REDIS_URL: str = os.environ.get("REDIS_URL", "")

# Namespaces every key so multiple deployments can share one Redis instance.
GLOBAL_PREFIX: str = os.environ.get("UKIP_CACHE_PREFIX", "ukip")

# Keep Redis hiccups from stalling request handlers; fail-open kicks in fast.
SOCKET_CONNECT_TIMEOUT: float = float(os.environ.get("UKIP_CACHE_CONNECT_TIMEOUT", "0.5"))
SOCKET_TIMEOUT: float = float(os.environ.get("UKIP_CACHE_SOCKET_TIMEOUT", "0.5"))
```

- [ ] **Step 5: Implement `backend/cache/client.py`:**
```python
"""Shared redis-py connection pool + lifecycle helpers (fail-open)."""
from __future__ import annotations

import logging
from typing import Optional

from backend.cache import config

logger = logging.getLogger(__name__)

_pool = None  # redis.ConnectionPool | None


def get_redis():
    """Return a process-wide Redis client, or None when unconfigured.

    Never raises on construction; connection errors surface lazily at call
    time and are handled fail-open by the backend.
    """
    global _pool
    if not config.REDIS_URL:
        return None
    if _pool is None:
        import redis
        _pool = redis.ConnectionPool.from_url(
            config.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=config.SOCKET_CONNECT_TIMEOUT,
            socket_timeout=config.SOCKET_TIMEOUT,
        )
    import redis
    return redis.Redis(connection_pool=_pool)


def ping() -> bool:
    """Best-effort reachability probe for startup logging."""
    client = get_redis()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception as exc:  # noqa: BLE001 — fail-open probe
        logger.warning("Redis ping failed: %s", exc)
        return False


def close() -> None:
    """Release the pool on shutdown."""
    global _pool
    if _pool is not None:
        try:
            _pool.disconnect()
        except Exception:  # noqa: BLE001
            pass
        _pool = None
```

- [ ] **Step 6: Run — expect pass:** `.venv\Scripts\python -m pytest backend/tests/test_cache_client.py -v`

- [ ] **Step 7: Commit:**
```bash
git add backend/cache/__init__.py backend/cache/config.py backend/cache/client.py backend/tests/test_cache_client.py requirements.txt
git commit -m "feat: add Redis cache client foundation (config + pool, fail-open)"
```

---

## Task 2: CacheBackend base + key/serialization helpers

**Files:**
- Create: `backend/cache/base.py`
- Test: `backend/tests/test_cache_base.py`

- [ ] **Step 1: Write the failing test** `backend/tests/test_cache_base.py`:
```python
from backend.cache.base import make_key, MISS


def test_make_key_joins_with_none_sentinel():
    assert make_key(("authority", None, "x")) == "authority|\x00|x"


def test_make_key_is_deterministic():
    assert make_key((1, "a")) == make_key((1, "a"))


def test_make_key_distinguishes_none_from_empty_string():
    assert make_key((None,)) != make_key(("",))


def test_miss_is_distinct_singleton():
    assert MISS is MISS
    assert MISS is not None
```

- [ ] **Step 2: Run — expect failure.**
`.venv\Scripts\python -m pytest backend/tests/test_cache_base.py -v`

- [ ] **Step 3: Implement `backend/cache/base.py`:**
```python
"""CacheBackend interface + key/serialization helpers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

# Sentinel returned by get() to distinguish a real cached None from a miss.
class _Miss:
    __slots__ = ()
    def __repr__(self) -> str:  # pragma: no cover
        return "<MISS>"

MISS = _Miss()

# Unlikely-in-data separator + a sentinel for None tuple elements, so
# (None,) and ("",) and ("None",) all produce distinct keys.
_SEP = "|"
_NONE = "\x00"


def make_key(parts) -> str:
    """Deterministically stringify a tuple/str key for Redis."""
    if isinstance(parts, str):
        return parts
    return _SEP.join(_NONE if p is None else str(p) for p in parts)


Serializer = Callable[[Any], Any]      # domain value -> JSON-safe value
Deserializer = Callable[[Any], Any]    # JSON value   -> domain value


class CacheBackend(ABC):
    @abstractmethod
    def get(self, key: str) -> Any: ...          # returns value or MISS
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None: ...
    @abstractmethod
    def get_or_load(self, key: str, loader: Callable[[], Any],
                    ttl: Optional[int] = None) -> Any: ...
    @abstractmethod
    def delete(self, key: str) -> bool: ...
    @abstractmethod
    def invalidate_prefix(self, prefix: str = "") -> int: ...
    @abstractmethod
    def exists_prefix(self, prefix: str) -> bool: ...
```

- [ ] **Step 4: Run — expect pass.** `.venv\Scripts\python -m pytest backend/tests/test_cache_base.py -v`

- [ ] **Step 5: Commit:**
```bash
git add backend/cache/base.py backend/tests/test_cache_base.py
git commit -m "feat: add CacheBackend interface + key/serialization helpers"
```

---

## Task 3: InProcessBackend (cachetools parity)

**Files:**
- Create: `backend/cache/inprocess_backend.py`
- Test: `backend/tests/test_cache_inprocess.py`

- [ ] **Step 1: Write the failing test** covering get/set/MISS, get_or_load caching None, delete, invalidate_prefix (count), exists_prefix, TTL via maxsize honored. Key cases:
```python
from backend.cache.base import MISS
from backend.cache.inprocess_backend import InProcessBackend


def test_get_miss_returns_sentinel():
    b = InProcessBackend(namespace="t", ttl=60)
    assert b.get("k") is MISS

def test_set_then_get():
    b = InProcessBackend(namespace="t", ttl=60)
    b.set("k", {"a": 1})
    assert b.get("k") == {"a": 1}

def test_get_or_load_caches_none():
    b = InProcessBackend(namespace="t", ttl=60)
    calls = []
    def loader():
        calls.append(1); return None
    assert b.get_or_load("k", loader) is None
    assert b.get_or_load("k", loader) is None
    assert len(calls) == 1  # loader ran once; None was cached

def test_delete():
    b = InProcessBackend(namespace="t", ttl=60)
    b.set("k", 1)
    assert b.delete("k") is True
    assert b.delete("k") is False

def test_invalidate_prefix_counts():
    b = InProcessBackend(namespace="t", ttl=60)
    b.set("dom:a", 1); b.set("dom:b", 2); b.set("other", 3)
    assert b.invalidate_prefix("dom:") == 2
    assert b.get("other") == 3

def test_exists_prefix():
    b = InProcessBackend(namespace="t", ttl=60)
    b.set("dom:a", 1)
    assert b.exists_prefix("dom:") is True
    assert b.exists_prefix("zzz") is False
```

- [ ] **Step 2: Run — expect failure.**

- [ ] **Step 3: Implement `backend/cache/inprocess_backend.py`** wrapping `cachetools.TTLCache` (accept `maxsize` to preserve per-cache caps — resolver 10k, feedback 4096, thresholds 2048). Use a `Lock`. `get` returns `MISS` when absent. `get_or_load` stores the loader result even if `None`. `invalidate_prefix`/`exists_prefix` iterate keys. (Serializer/deserializer are no-ops here — values stay live Python objects, matching today's behavior.)

- [ ] **Step 4: Run — expect pass.**

- [ ] **Step 5: Commit:** `git commit -m "feat: add InProcessBackend (cachetools parity, MISS-aware)"`

---

## Task 4: RedisBackend (JSON, fail-open, SCAN+DEL)

**Files:**
- Create: `backend/cache/redis_backend.py`
- Test: `backend/tests/test_cache_redis.py` (uses `fakeredis`)

- [ ] **Step 1: Write failing tests** with a `fakeredis` client injected. Must cover:
  - JSON round-trip for dict/list/float/None.
  - `get` returns `MISS` for absent key; returns `None` (not MISS) for a stored `null`.
  - `get_or_load` caches `None`.
  - `delete` returns True/False.
  - `invalidate_prefix` deletes matching keys via SCAN and returns count.
  - `exists_prefix` True/False.
  - **Fail-open:** a client whose `.get` raises → `get` returns `MISS`, `get_or_load` still returns `loader()` and does not raise.
  - **Cross-instance invalidation (headline):** two `RedisBackend` instances sharing the SAME fakeredis server — set via instance A, `invalidate_prefix` via instance B, then A sees a miss. This proves cross-worker coherence.
```python
import fakeredis, pytest
from backend.cache.base import MISS
from backend.cache.redis_backend import RedisBackend

@pytest.fixture
def fake():
    return fakeredis.FakeStrictRedis(decode_responses=True)

def _backend(fake, ns="t", ttl=60):
    return RedisBackend(namespace=ns, ttl=ttl, client_factory=lambda: fake)

def test_json_round_trip(fake):
    b = _backend(fake)
    b.set("k", {"a": [1, 2]}); assert b.get("k") == {"a": [1, 2]}

def test_stored_null_is_hit_not_miss(fake):
    b = _backend(fake)
    b.set("k", None)
    assert b.get("k") is None  # not MISS

def test_cross_instance_invalidation(fake):
    a = _backend(fake); bb = _backend(fake)
    a.set("dom:x", 1)
    assert bb.invalidate_prefix("dom:") == 1
    assert a.get("dom:x") is MISS

def test_fail_open_on_get(monkeypatch, fake):
    b = _backend(fake)
    monkeypatch.setattr(fake, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert b.get("k") is MISS
    assert b.get_or_load("k", lambda: 42) == 42
```

- [ ] **Step 2: Run — expect failure.**

- [ ] **Step 3: Implement `backend/cache/redis_backend.py`.** Notes:
  - Constructor: `RedisBackend(namespace, ttl, serializer=None, deserializer=None, client_factory=None)`. `client_factory` defaults to `backend.cache.client.get_redis` (injectable for tests).
  - Full key = `f"{config.GLOBAL_PREFIX}:{namespace}:{key}"`.
  - `set`: `client.set(fullkey, json.dumps(serializer(value)), ex=ttl or self._ttl)`.
  - `get`: read raw; if `None` → `MISS`; else `deserializer(json.loads(raw))`. Wrap in try/except → `MISS` (fail-open). JSON decode error → treat as `MISS` (optionally `delete`).
  - `get_or_load`: `v = self.get(key); if v is not MISS: return v; result = loader(); try self.set(...) except: pass; return result`.
  - `delete`: `bool(client.delete(fullkey))`, fail-open → False.
  - `invalidate_prefix`: `SCAN MATCH f"{GLOBAL_PREFIX}:{namespace}:{prefix}*"`, batch `DEL`, return count. Fail-open → 0.
  - `exists_prefix`: `SCAN MATCH ... COUNT 1`, return True on first hit. Fail-open → False.
  - serializer/deserializer default to identity.

- [ ] **Step 4: Run — expect pass.**

- [ ] **Step 5: Commit:** `git commit -m "feat: add RedisBackend (JSON, fail-open, SCAN-based prefix ops)"`

---

## Task 5: get_cache factory + cross-backend parity

**Files:**
- Modify: `backend/cache/__init__.py`
- Test: `backend/tests/test_cache_factory.py`

- [ ] **Step 1: Write failing tests:**
  - `get_cache(...)` returns `InProcessBackend` when `config.REDIS_URL` is empty.
  - returns `RedisBackend` when `REDIS_URL` set (monkeypatch `config.REDIS_URL` + `client_factory` via a seam, or assert type).
  - **Parity:** a shared battery (`set/get/get_or_load None/delete/invalidate_prefix/exists_prefix`) run against both backends yields identical observable results.

- [ ] **Step 2: Run — expect failure.**

- [ ] **Step 3: Implement `get_cache` in `backend/cache/__init__.py`:**
```python
from typing import Optional
from backend.cache import config
from backend.cache.base import CacheBackend, Serializer, Deserializer, MISS  # re-export

def get_cache(namespace: str, ttl: int, *, maxsize: int = 1024,
              serializer: Optional[Serializer] = None,
              deserializer: Optional[Deserializer] = None) -> CacheBackend:
    if config.REDIS_URL:
        from backend.cache.redis_backend import RedisBackend
        return RedisBackend(namespace, ttl, serializer=serializer, deserializer=deserializer)
    from backend.cache.inprocess_backend import InProcessBackend
    return InProcessBackend(namespace, ttl, maxsize=maxsize)
```
Note: backend selection is evaluated at `get_cache(...)` call time, and existing caches build their singleton at import. See cross-cutting note **A** — Redis-path tests must inject `fakeredis` directly (not monkeypatch `REDIS_URL` post-import).

- [ ] **Step 4: Run — expect pass.**

- [ ] **Step 5: Commit:** `git commit -m "feat: add get_cache factory + cross-backend parity tests"`

---

## Tasks 6–10: Migrate each cache (preserve public signatures)

> **Migration rule for every task below:** the module's PUBLIC functions/classes keep their exact signatures. Only the cache internals change to delegate to `get_cache(...)`. Run the cache's EXISTING tests after each migration — they must still pass with `REDIS_URL` unset (in-process backend). Add one new test per migration that asserts the namespaced delegation works (e.g., via a `fakeredis`-backed `get_cache`).

### Task 6: ResolverCache → get_cache
**Files:** Modify `backend/authority/cache.py`; Test `backend/tests/test_cache_resolver_migration.py`.
- Keep `get_or_load(source, value, entity_type, loader)` and `get_resolver_cache()` signatures.
- Build key: `make_key((source, normalize_name(value), entity_type))`.
- Serializer: normalize each candidate to a dict — `asdict(c) if is_dataclass(c) else c`. **Deserializer MUST reconstruct `AuthorityCandidate(**d)`** (a `list[AuthorityCandidate]`), NOT return `list[dict]`. Reason: `backend/authority/resolver.py` `resolve_all` does `raw.extend(future.result())` into a `list[AuthorityCandidate]` and then accesses attributes (`c.canonical_label`, `c.score_breakdown`, `c.evidence`, scoring-engine application). Returning dicts would raise `AttributeError` on the first candidate. Add a test that round-trips a candidate with **all fields populated** (incl. `aliases: list[str]` and the optional fields) and asserts an `AuthorityCandidate` with equal field values comes back.
- Thread-safety note: the current `get_or_load` releases the lock between miss-check and store, so two threads can both run the loader on a cold key (last write wins). `RedisBackend.get_or_load` has the same non-atomic semantics. This is intentional (no stampede lock) — do NOT "fix" it with a distributed lock.
- Internals call `get_cache("authority:resolver", ttl=_DEFAULT_TTL, maxsize=_DEFAULT_MAXSIZE, serializer=..., deserializer=...).get_or_load(key, loader)`.
- Commit: `refactor: back ResolverCache with distributed cache (signature unchanged)`

### Task 7: thresholds → get_cache (negative caching!)
**Files:** Modify `backend/authority/thresholds.py`; Test `backend/tests/test_cache_thresholds_migration.py`.
- Keep `get_thresholds(...)` and `clear_cache()`.
- Key: `make_key((org_id, domain_id, field_name))`.
- Value: `Optional[ResolutionThresholds]`. Serializer: `None → None`; else `asdict(t)`. Deserializer: `None → None`; else `ResolutionThresholds(**d)`. **Must cache `None`** (negative result) — use `get_or_load` so the computed `None` is stored and the next call is a hit. Add a test: two calls with a scope that has no override invoke the DB loader only once.
- `clear_cache()` → `get_cache(...).invalidate_prefix("")`.
- Commit: `refactor: back threshold cache with distributed cache (preserves negative caching)`

### Task 8: feedback → get_cache (point delete)
**Files:** Modify `backend/authority/feedback.py`; Test `backend/tests/test_cache_feedback_migration.py`.
- Keep `get_source_prior(...)`, `record_outcome(...)`, `get_source_priors(...)`, `clear_cache()`.
- Key: `make_key((org_id, field_name, authority_source))`. Value: `float` (JSON-native).
- `get_source_prior` → `get_or_load(make_key(key), loader)` — stringify the tuple via `make_key` before the backend call (note B), in BOTH `get_source_prior` and `record_outcome`.
- `record_outcome`'s `_cache.pop(scope_key, None)` → `get_cache(...).delete(make_key(scope_key))`.
- `clear_cache()` → `invalidate_prefix("")`.
- Test: `record_outcome` evicts exactly that scope key (cross-instance: set prior via A, record_outcome via B deletes it, A misses).
- Commit: `refactor: back feedback prior cache with distributed cache (point eviction via delete)`

### Task 9: derived_status _StatusCache → get_cache
**Files:** Modify `backend/services/derived_status_service.py`; Test `backend/tests/test_cache_derived_status_migration.py`.
- Keep `status_cache.get/set`, `status_cache.invalidate(domain_id)`, and `invalidate_derived_status_cache(domain_id)`.
- Reimplement `_StatusCache` as a thin wrapper over `get_cache("derived_status", ttl=30)`: `get` translates `MISS → None`; `set` delegates; `invalidate(domain_id)` → `invalidate_prefix(f"{domain_id}:")`.
- Test the headline correctness win: cross-instance invalidation (set domain status via A, `invalidate_derived_status_cache(domain)` via B, A misses).
- Commit: `refactor: back derived-status cache with distributed cache (cross-worker invalidation)`

### Task 10: analytics _SimpleCache ×2 + fix snapshot coupling
**Files:** Modify `backend/routers/analytics.py` AND `backend/services/derived_status_service.py`; Test `backend/tests/test_cache_analytics_migration.py`.
- Keep `_SimpleCache` as a **thin wrapper class** in `analytics.py` (preserve the name — `test_sprint83.py:14` imports it) whose internals delegate to `get_cache`. Its `.get()` translates `MISS → None`; `.set()` delegates; `.invalidate(prefix="")` delegates to `invalidate_prefix` and returns `int`, accepting the zero-arg form. Assign the SAME module-level names: `_analytics_cache = _SimpleCache("analytics", ttl=300)`, `_dashboard_cache = _SimpleCache("dashboard", ttl=120)` (see cross-cutting note C — these are imported by name elsewhere).
- Keep `invalidate_analytics_cache(prefix)` and `invalidate_analytics_for_domain(domain_id)` behavior. Preserve exact prefixes (note E): `invalidate_analytics_for_domain` passes `f"dashboard_{domain_id}"` (no trailing separator) to `_dashboard_cache.invalidate`.
- **Untracked call-site to preserve:** `backend/routers/admin_data_fixes.py:282` does `from backend.routers.analytics import _analytics_cache` then `_analytics_cache.invalidate("coauth_")` and uses the **int** return. The wrapper's `.invalidate` returning int keeps this working — add a test asserting it.
- **Fix the private-internals coupling:** rewrite `_compute_executive_dashboard_snapshot` (≈ lines 258–283) to use `_dashboard_cache.exists_prefix(<app-prefix>)` instead of `_dashboard_cache._lock/._ttl/._store`. Preserve the existing `bare`-derivation (`"dashboard_all"` for scope `all`, else `f"dashboard_{bare}"`) and pass that string as the **application-level** prefix (the backend prepends `GLOBAL_PREFIX:dashboard:`, producing `SCAN MATCH ukip:dashboard:dashboard_all*`). Preserve warm→READY / cold→STALE and keep the `except` fallback.
- Tests: analytics get/set/invalidate parity; `admin_data_fixes` int-return; snapshot reports READY when a matching `dashboard_<domain>` key exists and STALE when not (run against a `fakeredis`-backed wrapper).
- Commit: `refactor: back analytics caches with distributed cache; fix dashboard snapshot coupling`

---

## Task 11: Lifespan hooks + ops docs

**Files:** Modify `backend/main.py`; Modify `.env.example`; Test `backend/tests/test_cache_lifespan.py` (or extend an existing startup test).

- [ ] **Step 1:** In `backend/main.py` lifespan startup (inside the guarded worker/init `try` block), add a non-blocking probe:
```python
from backend.cache import client as cache_client
if cache_client.ping():
    logger.info("Redis cache reachable — distributed cache active")
else:
    logger.info("Redis not configured/reachable — using in-process cache")
```
- [ ] **Step 2:** In the lifespan cleanup block (after `engine_client` close), add:
```python
from backend.cache import client as cache_client
cache_client.close()
```
- [ ] **Step 3:** Add to `.env.example` with comments:
```
# Distributed cache (optional). Unset => in-process caches (single-process only).
# Set to a managed Redis URL to enable cross-worker, deploy-surviving caching.
REDIS_URL=
UKIP_CACHE_PREFIX=ukip
# Fail-open timeouts (seconds) — keep small so Redis hiccups don't stall requests.
UKIP_CACHE_CONNECT_TIMEOUT=0.5
UKIP_CACHE_SOCKET_TIMEOUT=0.5
```
- [ ] **Step 4:** Test that startup does not crash with `REDIS_URL` unset (use existing `UKIP_SKIP_STARTUP_SIDE_EFFECTS` patterns or a direct `cache_client.ping()`/`close()` call test).
- [ ] **Step 5: Commit:** `git commit -m "feat: wire Redis cache probe + close into lifespan; document REDIS_URL"`

---

## Task 12: Full-suite verification

- [ ] **Step 1:** `.venv\Scripts\python -m pytest backend/tests -q` — expect the full suite green (≈2478+ passing, no new failures), proving the in-process backend preserves today's behavior with `REDIS_URL` unset.
- [ ] **Step 2:** Run only the new cache suite for a fast signal: `.venv\Scripts\python -m pytest backend/tests/test_cache_*.py -v`.
- [ ] **Step 3:** Sanity grep — confirm no remaining direct `TTLCache(` instantiations in the migrated modules, and confirm every `_analytics_cache` call-site (incl. `backend/routers/admin_data_fixes.py:282` and `backend/routers/analytics_analyzers.py`) still resolves against the wrapper: `git grep -n "TTLCache(\|_analytics_cache\|_dashboard_cache\|status_cache" backend/`. Verify the wrapper names/types are intact and `clear_cache()` call-sites (`git grep -n "clear_cache()"`) don't depend on a `None` return.
- [ ] **Step 4:** No commit needed (per-task commits cover the work).

---

## Definition of Done

- [ ] `backend/cache/` package: `config`, `client`, `base`, `inprocess_backend`, `redis_backend`, `get_cache` factory.
- [ ] All 6 caches delegate to `get_cache(...)`; every public signature unchanged; ~20 call-sites untouched.
- [ ] Negative caching (thresholds) and point-delete (feedback) preserved.
- [ ] `derived_status` snapshot uses `exists_prefix` (no private-internals access).
- [ ] `redis>=5` in requirements; `fakeredis` test-only.
- [ ] Lifespan `ping()` (startup log) + `close()` (shutdown); `.env.example` documents `REDIS_URL`.
- [ ] Full backend suite green with `REDIS_URL` unset.
- [ ] `fakeredis` tests prove fail-open + cross-worker invalidation (the headline correctness win).

## Out of scope (future sub-projects)
- Task queue / worker decoupling (sub-project 2).
- Deep health endpoints + full graceful drain (movement #3).
- L1 in-process tier, hit-rate metrics, tag-based invalidation (YAGNI).
