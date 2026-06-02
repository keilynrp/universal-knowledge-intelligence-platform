"""In-process cache backend (cachetools.TTLCache) — preserves today's behavior.

Values stay live Python objects (serializer/deserializer are no-ops here),
matching the pre-Redis caches. Selected by the factory when REDIS_URL is unset.
"""
from __future__ import annotations

from threading import Lock
from typing import Any, Callable, Optional

from cachetools import TTLCache

from backend.cache.base import MISS, CacheBackend


class InProcessBackend(CacheBackend):
    def __init__(self, namespace: str, ttl: int, *, maxsize: int = 1024) -> None:
        self._namespace = namespace
        self._ttl = ttl
        self._lock = Lock()
        self._store: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, key: str) -> Any:
        with self._lock:
            return self._store.get(key, MISS)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            self._store[key] = value

    def get_or_load(self, key: str, loader: Callable[[], Any],
                    ttl: Optional[int] = None) -> Any:
        with self._lock:
            cached = self._store.get(key, MISS)
        if cached is not MISS:
            return cached
        result = loader()
        with self._lock:
            self._store[key] = result
        return result

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def invalidate_prefix(self, prefix: str = "") -> int:
        with self._lock:
            matching = [k for k in self._store if k.startswith(prefix)]
            for k in matching:
                del self._store[k]
            return len(matching)

    def exists_prefix(self, prefix: str) -> bool:
        with self._lock:
            return any(k.startswith(prefix) for k in self._store)
