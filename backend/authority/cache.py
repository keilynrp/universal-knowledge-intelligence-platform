"""TTL cache for external authority resolver lookups (Phase 1, Task 1).

External authority sources (Wikidata, VIAF, ORCID, DBpedia, OpenAlex) are slow
and rate-limited. The same field value is frequently resolved repeatedly across
disambiguation passes, so we memoize candidate lists keyed on a normalized
``(source, value, entity_type)`` tuple with a configurable TTL.

The cache stores whatever the loader returns (typically a list of candidate
dicts or ``AuthorityCandidate`` objects); it is value-agnostic.
"""
from __future__ import annotations

import os
from threading import Lock
from typing import Callable

from cachetools import TTLCache

from backend.authority.normalize import normalize_name

# Defaults: one week TTL, 10k distinct keys. Overridable via env for ops tuning.
_DEFAULT_TTL = int(os.environ.get("UKIP_AUTHORITY_CACHE_TTL", 7 * 24 * 3600))
_DEFAULT_MAXSIZE = int(os.environ.get("UKIP_AUTHORITY_CACHE_MAXSIZE", 10_000))


class ResolverCache:
    """Thread-safe TTL cache keyed on the normalized lookup tuple."""

    def __init__(self, ttl: int | None = None, maxsize: int | None = None) -> None:
        self._cache: TTLCache = TTLCache(
            maxsize=maxsize or _DEFAULT_MAXSIZE,
            ttl=ttl or _DEFAULT_TTL,
        )
        self._lock = Lock()

    @staticmethod
    def _key(source: str, value: str, entity_type: str) -> tuple[str, str, str]:
        return (source, normalize_name(value), entity_type)

    def get_or_load(
        self,
        source: str,
        value: str,
        entity_type: str,
        loader: Callable[[], object],
    ):
        """Return the cached result for the key, or compute it via ``loader``.

        The loader is invoked outside the lock so concurrent misses for
        different keys do not serialize on each other.
        """
        key = self._key(source, value, entity_type)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        result = loader()
        with self._lock:
            self._cache[key] = result
        return result


_GLOBAL_CACHE = ResolverCache()


def get_resolver_cache() -> ResolverCache:
    """Return the process-wide resolver cache singleton."""
    return _GLOBAL_CACHE
