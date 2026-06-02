"""Adaptive resolution-threshold lookup (Phase 3, Task 11).

Resolves the effective ``ResolutionThresholds`` for a scope using a
most-specific-wins precedence:

    1. (org_id, domain_id, field_name)   — fully specific
    2. (org_id, NULL,      field_name)   — field-level, any domain
    3. None                              — caller falls back to global defaults

Lookups are memoized in a short-TTL distributed cache to keep per-candidate
scoring cheap. A ``None`` result (no override for the scope) is cached too
(negative caching), so repeated misses don't re-hit the DB.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Optional

from backend import models
from backend.authority.scoring import ResolutionThresholds
from backend.cache import get_cache, make_key

logger = logging.getLogger(__name__)

_NAMESPACE = "authority:thresholds"
_TTL = 300
_MAXSIZE = 2048


def _serialize_thresholds(value: Any) -> Any:
    """ResolutionThresholds | None -> JSON-safe. None stays None (cached)."""
    if value is None:
        return None
    return asdict(value)


def _deserialize_thresholds(value: Any) -> Any:
    if value is None:
        return None
    return ResolutionThresholds(**value)


_backend = get_cache(
    _NAMESPACE,
    ttl=_TTL,
    maxsize=_MAXSIZE,
    serializer=_serialize_thresholds,
    deserializer=_deserialize_thresholds,
)


def clear_cache() -> int:
    """Evict all cached thresholds. Returns the number of keys removed."""
    return _backend.invalidate_prefix("")


def _row_to_thresholds(row: models.ResolutionThreshold) -> ResolutionThresholds:
    return ResolutionThresholds(
        exact=row.exact, probable=row.probable, ambiguous=row.ambiguous
    )


def get_thresholds(
    db,
    field_name: str,
    domain_id: Optional[str] = None,
    org_id: Optional[int] = None,
) -> Optional[ResolutionThresholds]:
    """Return the most specific override for the scope, or ``None``."""
    key = make_key((org_id, domain_id, field_name))

    def _load() -> Optional[ResolutionThresholds]:
        result: Optional[ResolutionThresholds] = None
        try:
            q = db.query(models.ResolutionThreshold).filter(
                models.ResolutionThreshold.org_id == org_id,
                models.ResolutionThreshold.field_name == field_name,
            )
            # Prefer an exact domain match, then a field-level (domain IS NULL) row.
            candidates = q.all()
            exact = next((r for r in candidates if r.domain_id == domain_id), None)
            field_level = next((r for r in candidates if r.domain_id is None), None)
            chosen = exact or field_level
            if chosen is not None:
                result = _row_to_thresholds(chosen)
        except Exception as exc:  # defensive: scoring must not fail on lookup
            logger.debug("get_thresholds failed for %s: %s", key, exc)
            result = None
        return result

    # get_or_load caches the computed value even when it is None (negative cache).
    return _backend.get_or_load(key, _load)
