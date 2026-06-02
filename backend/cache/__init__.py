"""Distributed cache package.

`get_cache(namespace, ttl, ...)` returns a CacheBackend: RedisBackend when
REDIS_URL is configured, else InProcessBackend (today's single-process
behavior). Backend selection happens at call time; module-level cache
singletons therefore pick their backend at import time (see the plan's
cross-cutting note A — inject fakeredis in tests, don't monkeypatch REDIS_URL
after import).
"""
from typing import Optional

from backend.cache import config
from backend.cache.base import (  # re-export
    MISS,
    CacheBackend,
    Deserializer,
    Serializer,
    make_key,
)


def get_cache(namespace: str, ttl: int, *, maxsize: int = 1024,
              serializer: Optional[Serializer] = None,
              deserializer: Optional[Deserializer] = None) -> CacheBackend:
    if config.REDIS_URL:
        from backend.cache.redis_backend import RedisBackend
        return RedisBackend(namespace, ttl, serializer=serializer,
                            deserializer=deserializer)
    from backend.cache.inprocess_backend import InProcessBackend
    return InProcessBackend(namespace, ttl, maxsize=maxsize)


__all__ = [
    "get_cache",
    "CacheBackend",
    "Serializer",
    "Deserializer",
    "MISS",
    "make_key",
    "config",
]
