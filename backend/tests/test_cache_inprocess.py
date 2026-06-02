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
        calls.append(1)
        return None

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
    b.set("dom:a", 1)
    b.set("dom:b", 2)
    b.set("other", 3)
    assert b.invalidate_prefix("dom:") == 2
    assert b.get("other") == 3


def test_invalidate_prefix_empty_clears_all():
    b = InProcessBackend(namespace="t", ttl=60)
    b.set("a", 1)
    b.set("b", 2)
    assert b.invalidate_prefix("") == 2
    assert b.get("a") is MISS


def test_exists_prefix():
    b = InProcessBackend(namespace="t", ttl=60)
    b.set("dom:a", 1)
    assert b.exists_prefix("dom:") is True
    assert b.exists_prefix("zzz") is False
