import fakeredis
import pytest

from backend.cache import config, get_cache
from backend.cache.base import MISS
from backend.cache.inprocess_backend import InProcessBackend
from backend.cache.redis_backend import RedisBackend


def test_factory_returns_inprocess_when_unconfigured(monkeypatch):
    monkeypatch.setattr(config, "REDIS_URL", "", raising=False)
    backend = get_cache("ns", ttl=60)
    assert isinstance(backend, InProcessBackend)


def test_factory_returns_redis_when_configured(monkeypatch):
    monkeypatch.setattr(config, "REDIS_URL", "redis://localhost:6379/0", raising=False)
    backend = get_cache("ns", ttl=60)
    assert isinstance(backend, RedisBackend)


def _battery(backend):
    """Observable behavior battery shared across backends."""
    results = {}
    results["miss"] = backend.get("absent") is MISS
    backend.set("a:1", {"v": 1})
    results["get"] = backend.get("a:1") == {"v": 1}

    calls = []

    def loader():
        calls.append(1)
        return None

    results["load_none_1"] = backend.get_or_load("a:none", loader) is None
    results["load_none_2"] = backend.get_or_load("a:none", loader) is None
    results["load_once"] = len(calls) == 1

    backend.set("a:2", 2)
    results["delete_hit"] = backend.delete("a:2") is True
    results["delete_miss"] = backend.delete("a:2") is False

    results["exists"] = backend.exists_prefix("a:") is True
    results["count"] = backend.invalidate_prefix("a:") >= 2
    return results


@pytest.fixture
def fake():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_cross_backend_parity(fake):
    inproc = InProcessBackend("ns", ttl=60)
    redis_b = RedisBackend("ns", ttl=60, client_factory=lambda: fake)
    assert _battery(inproc) == _battery(redis_b)
