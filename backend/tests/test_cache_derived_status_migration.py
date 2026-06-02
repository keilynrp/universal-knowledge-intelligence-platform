"""Task 9 — derived-status cache delegates to the distributed cache.

Headline correctness win: cross-instance invalidation. Setting a domain's
status via one backend instance and invalidating via another (simulating a
different worker process sharing one Redis) makes the first instance miss.
"""
import fakeredis

from backend.cache.base import MISS
from backend.cache.redis_backend import RedisBackend
from backend.services import derived_status_service as svc


def test_status_cache_get_set_invalidate_inprocess():
    """Default in-process wrapper preserves get/set/None-on-miss/invalidate."""
    cache = svc._StatusCache(ttl_seconds=30)
    assert cache.get("science:bundle") is None
    cache.set("science:bundle", {"x": 1})
    assert cache.get("science:bundle") == {"x": 1}
    cache.invalidate("science")
    assert cache.get("science:bundle") is None


def test_invalidate_only_affects_domain_prefix():
    cache = svc._StatusCache(ttl_seconds=30)
    cache.set("science:a", 1)
    cache.set("health:a", 2)
    cache.invalidate("science")
    assert cache.get("science:a") is None
    assert cache.get("health:a") == 2


def test_cross_instance_invalidation():
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    a = RedisBackend(namespace="derived_status", ttl=30, client_factory=lambda: fake)
    b = RedisBackend(namespace="derived_status", ttl=30, client_factory=lambda: fake)
    a.set("science:bundle", {"ready": True})
    # Another worker (instance b) invalidates the domain.
    assert b.invalidate_prefix("science:") == 1
    assert a.get("science:bundle") is MISS


def test_invalidate_derived_status_cache_helper(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    backend = RedisBackend(namespace="derived_status", ttl=30, client_factory=lambda: fake)
    cache = svc._StatusCache(ttl_seconds=30)
    monkeypatch.setattr(cache, "_backend", backend, raising=False)
    monkeypatch.setattr(svc, "status_cache", cache, raising=False)
    cache.set("science:bundle", {"ok": True})
    svc.invalidate_derived_status_cache("science")
    assert cache.get("science:bundle") is None
