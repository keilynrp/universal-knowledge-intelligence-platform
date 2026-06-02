"""Task 6 — ResolverCache delegates to the distributed cache backend.

The default suite (no REDIS_URL) keeps the in-process backend, so existing
behavior is unchanged. These tests additionally inject a fakeredis-backed
RedisBackend to prove namespaced delegation and AuthorityCandidate
reconstruction across a JSON round-trip.
"""
import fakeredis

from backend.authority import cache as resolver_cache_mod
from backend.authority.base import AuthorityCandidate
from backend.authority.cache import ResolverCache, get_resolver_cache
from backend.cache.redis_backend import RedisBackend


def test_get_or_load_signature_unchanged():
    c = ResolverCache()
    calls = []

    def loader():
        calls.append(1)
        return [AuthorityCandidate("wikidata", "Q1", "Albert Einstein")]

    first = c.get_or_load("wikidata", "Einstein, Albert", "person", loader)
    second = c.get_or_load("wikidata", "Einstein, Albert", "person", loader)
    assert len(calls) == 1
    assert first == second
    assert isinstance(first[0], AuthorityCandidate)


def test_get_resolver_cache_returns_singleton():
    assert get_resolver_cache() is get_resolver_cache()


def test_candidate_round_trip_through_redis(monkeypatch):
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    c = ResolverCache()
    backend = RedisBackend(
        namespace="authority:resolver", ttl=60,
        serializer=resolver_cache_mod._serialize_candidates,
        deserializer=resolver_cache_mod._deserialize_candidates,
        client_factory=lambda: fake,
    )
    monkeypatch.setattr(c, "_backend", backend, raising=False)

    full = AuthorityCandidate(
        authority_source="viaf",
        authority_id="12345",
        canonical_label="Marie Curie",
        aliases=["Maria Skłodowska", "M. Curie"],
        description="Physicist",
        confidence=0.91,
        uri="https://viaf.org/viaf/12345",
        score_breakdown={"identifiers": 0.35, "name": 0.25},
        evidence=["orcid match"],
        resolution_status="exact_match",
        merged_sources=["wikidata"],
        hierarchy_distance=2,
    )

    calls = []

    def loader():
        calls.append(1)
        return [full]

    out1 = c.get_or_load("viaf", "Curie, Marie", "person", loader)
    out2 = c.get_or_load("viaf", "Curie, Marie", "person", loader)
    assert len(calls) == 1  # second call is a cache hit
    got = out2[0]
    assert isinstance(got, AuthorityCandidate)
    assert got == full
