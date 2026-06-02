import fakeredis
import pytest

from backend.cache.base import MISS
from backend.cache.redis_backend import RedisBackend


@pytest.fixture
def fake():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def _backend(fake, ns="t", ttl=60):
    return RedisBackend(namespace=ns, ttl=ttl, client_factory=lambda: fake)


def test_json_round_trip(fake):
    b = _backend(fake)
    b.set("k", {"a": [1, 2]})
    assert b.get("k") == {"a": [1, 2]}


def test_float_round_trip(fake):
    b = _backend(fake)
    b.set("k", 0.75)
    assert b.get("k") == 0.75


def test_miss_for_absent_key(fake):
    b = _backend(fake)
    assert b.get("nope") is MISS


def test_stored_null_is_hit_not_miss(fake):
    b = _backend(fake)
    b.set("k", None)
    assert b.get("k") is None  # not MISS


def test_get_or_load_caches_none(fake):
    b = _backend(fake)
    calls = []

    def loader():
        calls.append(1)
        return None

    assert b.get_or_load("k", loader) is None
    assert b.get_or_load("k", loader) is None
    assert len(calls) == 1


def test_delete(fake):
    b = _backend(fake)
    b.set("k", 1)
    assert b.delete("k") is True
    assert b.delete("k") is False


def test_invalidate_prefix_counts(fake):
    b = _backend(fake)
    b.set("dom:a", 1)
    b.set("dom:b", 2)
    b.set("other", 3)
    assert b.invalidate_prefix("dom:") == 2
    assert b.get("other") == 3


def test_exists_prefix(fake):
    b = _backend(fake)
    b.set("dom:a", 1)
    assert b.exists_prefix("dom:") is True
    assert b.exists_prefix("zzz") is False


def test_cross_instance_invalidation(fake):
    a = _backend(fake)
    bb = _backend(fake)
    a.set("dom:x", 1)
    assert bb.invalidate_prefix("dom:") == 1
    assert a.get("dom:x") is MISS


def test_namespaces_isolated(fake):
    a = RedisBackend(namespace="ns1", ttl=60, client_factory=lambda: fake)
    b = RedisBackend(namespace="ns2", ttl=60, client_factory=lambda: fake)
    a.set("k", 1)
    assert b.get("k") is MISS


def test_fail_open_on_get(monkeypatch, fake):
    b = _backend(fake)
    monkeypatch.setattr(
        fake, "get",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")),
    )
    assert b.get("k") is MISS
    assert b.get_or_load("k", lambda: 42) == 42


def test_fail_open_when_client_none():
    b = RedisBackend(namespace="t", ttl=60, client_factory=lambda: None)
    assert b.get("k") is MISS
    assert b.get_or_load("k", lambda: 7) == 7
    assert b.delete("k") is False
    assert b.invalidate_prefix("p") == 0
    assert b.exists_prefix("p") is False


def test_serializer_deserializer(fake):
    b = RedisBackend(
        namespace="t", ttl=60,
        serializer=lambda v: {"wrapped": v},
        deserializer=lambda d: d["wrapped"],
        client_factory=lambda: fake,
    )
    b.set("k", 99)
    assert b.get("k") == 99


def test_corrupt_json_treated_as_miss(fake):
    b = _backend(fake)
    fake.set("ukip:t:k", "{not valid json")
    assert b.get("k") is MISS
