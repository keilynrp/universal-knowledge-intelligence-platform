"""Redis-backed cache (JSON values, fail-open, SCAN-based prefix ops).

Cross-worker coherent and deploy-surviving. Every Redis error is swallowed
fail-open: reads degrade to a miss, writes/invalidations become no-ops, so a
Redis hiccup never breaks a request handler.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from backend.cache import config
from backend.cache.base import MISS, CacheBackend, Deserializer, Serializer

logger = logging.getLogger(__name__)

_SCAN_BATCH = 256


def _identity(value: Any) -> Any:
    return value


class RedisBackend(CacheBackend):
    def __init__(self, namespace: str, ttl: int, *,
                 serializer: Optional[Serializer] = None,
                 deserializer: Optional[Deserializer] = None,
                 client_factory: Optional[Callable[[], Any]] = None) -> None:
        self._namespace = namespace
        self._ttl = ttl
        self._serialize = serializer or _identity
        self._deserialize = deserializer or _identity
        if client_factory is None:
            from backend.cache import client as cache_client
            client_factory = cache_client.get_redis
        self._client_factory = client_factory
        self._prefix = f"{config.GLOBAL_PREFIX}:{namespace}:"

    # -- key helpers -------------------------------------------------------
    def _full(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def _client(self):
        try:
            return self._client_factory()
        except Exception as exc:  # noqa: BLE001 — fail-open
            logger.warning("Redis client unavailable: %s", exc)
            return None

    # -- API ---------------------------------------------------------------
    def get(self, key: str) -> Any:
        client = self._client()
        if client is None:
            return MISS
        try:
            raw = client.get(self._full(key))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis get failed (%s): %s", key, exc)
            return MISS
        if raw is None:
            return MISS
        try:
            return self._deserialize(json.loads(raw))
        except (ValueError, TypeError) as exc:
            logger.warning("Redis value decode failed (%s): %s", key, exc)
            try:
                client.delete(self._full(key))
            except Exception:  # noqa: BLE001
                pass
            return MISS

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        client = self._client()
        if client is None:
            return
        try:
            payload = json.dumps(self._serialize(value))
        except (TypeError, ValueError) as exc:
            logger.warning("Redis value encode failed (%s): %s", key, exc)
            return
        try:
            client.set(self._full(key), payload, ex=ttl or self._ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis set failed (%s): %s", key, exc)

    def get_or_load(self, key: str, loader: Callable[[], Any],
                    ttl: Optional[int] = None) -> Any:
        cached = self.get(key)
        if cached is not MISS:
            return cached
        result = loader()
        self.set(key, result, ttl=ttl)
        return result

    def delete(self, key: str) -> bool:
        client = self._client()
        if client is None:
            return False
        try:
            return bool(client.delete(self._full(key)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis delete failed (%s): %s", key, exc)
            return False

    def invalidate_prefix(self, prefix: str = "") -> int:
        client = self._client()
        if client is None:
            return 0
        match = f"{self._prefix}{prefix}*"
        count = 0
        try:
            batch: list[str] = []
            for full_key in client.scan_iter(match=match, count=_SCAN_BATCH):
                batch.append(full_key)
                if len(batch) >= _SCAN_BATCH:
                    count += int(client.delete(*batch))
                    batch = []
            if batch:
                count += int(client.delete(*batch))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis invalidate_prefix failed (%s): %s", prefix, exc)
            return count
        return count

    def exists_prefix(self, prefix: str) -> bool:
        client = self._client()
        if client is None:
            return False
        match = f"{self._prefix}{prefix}*"
        try:
            for _ in client.scan_iter(match=match, count=1):
                return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis exists_prefix failed (%s): %s", prefix, exc)
            return False
        return False
