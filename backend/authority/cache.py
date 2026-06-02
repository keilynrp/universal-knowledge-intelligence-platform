"""TTL cache for external authority resolver lookups (Phase 1, Task 1).

External authority sources (Wikidata, VIAF, ORCID, DBpedia, OpenAlex) are slow
and rate-limited. The same field value is frequently resolved repeatedly across
disambiguation passes, so we memoize candidate lists keyed on a normalized
``(source, value, entity_type)`` tuple with a configurable TTL.

Backed by the distributed cache layer (``backend.cache.get_cache``): in-process
by default, Redis-backed (cross-worker, deploy-surviving) when ``REDIS_URL`` is
set. The public signature is unchanged.
"""
from __future__ import annotations

import os
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from backend.authority.base import AuthorityCandidate
from backend.authority.normalize import normalize_name
from backend.cache import get_cache, make_key

# Defaults: one week TTL, 10k distinct keys. Overridable via env for ops tuning.
_DEFAULT_TTL = int(os.environ.get("UKIP_AUTHORITY_CACHE_TTL", 7 * 24 * 3600))
_DEFAULT_MAXSIZE = int(os.environ.get("UKIP_AUTHORITY_CACHE_MAXSIZE", 10_000))

_NAMESPACE = "authority:resolver"


def _serialize_candidates(value: Any) -> Any:
    """Normalize a list of AuthorityCandidate (or dicts) to JSON-safe dicts."""
    if isinstance(value, list):
        return [asdict(c) if is_dataclass(c) else c for c in value]
    return value


def _deserialize_candidates(value: Any) -> Any:
    """Reconstruct AuthorityCandidate objects from JSON dicts.

    ``resolver.resolve_all`` extends a ``list[AuthorityCandidate]`` with the
    cached result and then accesses attributes (``c.canonical_label`` etc.), so
    the deserializer MUST return dataclass instances, not raw dicts.
    """
    if isinstance(value, list):
        return [
            AuthorityCandidate(**c) if isinstance(c, dict) else c
            for c in value
        ]
    return value


class ResolverCache:
    """Thread-safe TTL cache keyed on the normalized lookup tuple."""

    def __init__(self, ttl: int | None = None, maxsize: int | None = None) -> None:
        self._backend = get_cache(
            _NAMESPACE,
            ttl=ttl or _DEFAULT_TTL,
            maxsize=maxsize or _DEFAULT_MAXSIZE,
            serializer=_serialize_candidates,
            deserializer=_deserialize_candidates,
        )

    @staticmethod
    def _key(source: str, value: str, entity_type: str) -> str:
        return make_key((source, normalize_name(value), entity_type))

    def get_or_load(
        self,
        source: str,
        value: str,
        entity_type: str,
        loader: Callable[[], object],
    ):
        """Return the cached result for the key, or compute it via ``loader``.

        Memoizes whatever the loader returns (including falsy/empty lists). The
        loader runs outside any lock, matching the original non-stampede-locked
        semantics: concurrent cold misses may both run the loader (last write
        wins) — this is intentional.
        """
        return self._backend.get_or_load(
            self._key(source, value, entity_type), loader
        )


_GLOBAL_CACHE = ResolverCache()


def get_resolver_cache() -> ResolverCache:
    """Return the process-wide resolver cache singleton."""
    return _GLOBAL_CACHE
