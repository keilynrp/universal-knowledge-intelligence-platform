"""Shared redis-py connection pool + lifecycle helpers (fail-open)."""
from __future__ import annotations

import logging

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
