"""Task 7 — threshold cache delegates to the distributed cache, preserving
negative caching (a computed ``None`` is stored and re-served as a hit)."""
import fakeredis

from backend.authority import thresholds as thresholds_mod
from backend.authority.scoring import ResolutionThresholds
from backend.cache.base import make_key
from backend.cache.redis_backend import RedisBackend


class _FakeQuery:
    def filter(self, *a, **k):
        return self

    def all(self):
        return []


class _FakeDB:
    def __init__(self):
        self.calls = 0

    def query(self, *a, **k):
        self.calls += 1
        return _FakeQuery()


def test_negative_result_cached_only_one_db_hit(monkeypatch):
    """A scope with no override caches None — loader (DB) runs once."""
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    backend = RedisBackend(
        namespace="authority:thresholds", ttl=60,
        serializer=thresholds_mod._serialize_thresholds,
        deserializer=thresholds_mod._deserialize_thresholds,
        client_factory=lambda: fake,
    )
    monkeypatch.setattr(thresholds_mod, "_backend", backend, raising=False)

    db = _FakeDB()
    r1 = thresholds_mod.get_thresholds(db, "author", domain_id=None, org_id=None)
    r2 = thresholds_mod.get_thresholds(db, "author", domain_id=None, org_id=None)
    assert r1 is None and r2 is None
    assert db.calls == 1  # negative result was cached


def test_threshold_round_trip(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    backend = RedisBackend(
        namespace="authority:thresholds", ttl=60,
        serializer=thresholds_mod._serialize_thresholds,
        deserializer=thresholds_mod._deserialize_thresholds,
        client_factory=lambda: fake,
    )
    t = ResolutionThresholds(exact=0.9, probable=0.7, ambiguous=0.5)
    backend.set(make_key((1, "sci", "author")), t)
    got = backend.get(make_key((1, "sci", "author")))
    assert isinstance(got, ResolutionThresholds)
    assert got == t


def test_clear_cache_returns_int(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    backend = RedisBackend(
        namespace="authority:thresholds", ttl=60,
        serializer=thresholds_mod._serialize_thresholds,
        deserializer=thresholds_mod._deserialize_thresholds,
        client_factory=lambda: fake,
    )
    monkeypatch.setattr(thresholds_mod, "_backend", backend, raising=False)
    db = _FakeDB()
    thresholds_mod.get_thresholds(db, "author", domain_id=None, org_id=None)
    cleared = thresholds_mod.clear_cache()
    assert isinstance(cleared, int)
