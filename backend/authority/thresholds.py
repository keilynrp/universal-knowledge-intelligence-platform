"""Adaptive resolution-threshold lookup (Phase 3, Task 11).

Resolves the effective ``ResolutionThresholds`` for a scope using a
most-specific-wins precedence:

    1. (org_id, domain_id, field_name)   — fully specific
    2. (org_id, NULL,      field_name)   — field-level, any domain
    3. None                              — caller falls back to global defaults

Lookups are memoized in a short-TTL cache to keep per-candidate scoring cheap.
"""
from __future__ import annotations

import logging
from typing import Optional

from cachetools import TTLCache

from backend import models
from backend.authority.scoring import ResolutionThresholds

logger = logging.getLogger(__name__)

_cache: TTLCache = TTLCache(maxsize=2048, ttl=300)


def clear_cache() -> None:
    _cache.clear()


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
    key = (org_id, domain_id, field_name)
    if key in _cache:
        return _cache[key]

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

    _cache[key] = result
    return result
