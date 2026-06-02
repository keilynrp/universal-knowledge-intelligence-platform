"""Task 8 — feedback prior cache delegates to the distributed cache, with
point eviction (record_outcome deletes exactly the affected scope key)."""
import fakeredis

from backend.authority import feedback as feedback_mod
from backend.cache.redis_backend import RedisBackend


class _Row:
    def __init__(self, confirmed=0, rejected=0):
        self.confirmed = confirmed
        self.rejected = rejected


class _Query:
    def __init__(self, row):
        self._row = row

    def filter_by(self, **k):
        return self

    def first(self):
        return self._row


class _DB:
    def __init__(self, row=None):
        self.row = row
        self.calls = 0

    def query(self, *a, **k):
        self.calls += 1
        return _Query(self.row)


def _inject(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    backend = RedisBackend(
        namespace="authority:feedback", ttl=60,
        client_factory=lambda: fake,
    )
    monkeypatch.setattr(feedback_mod, "_backend", backend, raising=False)
    return backend


def test_get_source_prior_caches(monkeypatch):
    _inject(monkeypatch)
    db = _DB(row=_Row(confirmed=10, rejected=0))
    a = feedback_mod.get_source_prior(db, "author", "wikidata", org_id=1)
    b = feedback_mod.get_source_prior(db, "author", "wikidata", org_id=1)
    assert a == b
    assert db.calls == 1  # second call served from cache


def test_record_outcome_evicts_scope(monkeypatch):
    backend = _inject(monkeypatch)
    db = _DB(row=_Row(confirmed=10, rejected=0))
    feedback_mod.get_source_prior(db, "author", "wikidata", org_id=1)
    assert backend.get(feedback_mod.make_key((1, "author", "wikidata"))) is not feedback_mod.MISS

    # record_outcome on a fresh db (row gets mutated in place here) must evict.
    db2 = _DB(row=_Row(confirmed=10, rejected=0))
    feedback_mod.record_outcome(db2, "author", "wikidata", confirmed=True, org_id=1)
    assert backend.get(feedback_mod.make_key((1, "author", "wikidata"))) is feedback_mod.MISS


def test_clear_cache_returns_int(monkeypatch):
    _inject(monkeypatch)
    db = _DB(row=_Row(confirmed=5, rejected=0))
    feedback_mod.get_source_prior(db, "author", "viaf", org_id=None)
    assert isinstance(feedback_mod.clear_cache(), int)
