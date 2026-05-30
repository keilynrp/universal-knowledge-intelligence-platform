"""Tests for the authority resolver cache (Phase 1, Task 1).

The cache memoizes external resolver lookups keyed on
(source, normalized_value, entity_type) with a TTL, so repeated
disambiguation passes do not re-hit Wikidata/VIAF/ORCID/etc.
"""
from backend.authority.cache import ResolverCache


def test_cache_returns_stored_candidates_without_recomputing():
    cache = ResolverCache(ttl=60, maxsize=10)
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return [{"authority_id": "Q1"}]

    first = cache.get_or_load("wikidata", "ACME Corp", "organization", loader)
    # normalized-equal key (extra spaces + case) should hit the cache
    second = cache.get_or_load("wikidata", "acme   corp", "organization", loader)

    assert first == second == [{"authority_id": "Q1"}]
    assert calls["n"] == 1  # second call served from cache (normalized key)


def test_cache_distinguishes_entity_type():
    cache = ResolverCache(ttl=60, maxsize=10)
    cache.get_or_load("viaf", "Smith", "person", lambda: ["p"])
    out = cache.get_or_load("viaf", "Smith", "organization", lambda: ["o"])
    assert out == ["o"]


def test_cache_distinguishes_source():
    cache = ResolverCache(ttl=60, maxsize=10)
    cache.get_or_load("wikidata", "Paris", "general", lambda: ["w"])
    out = cache.get_or_load("dbpedia", "Paris", "general", lambda: ["d"])
    assert out == ["d"]


def test_global_cache_singleton():
    from backend.authority.cache import get_resolver_cache

    assert get_resolver_cache() is get_resolver_cache()
