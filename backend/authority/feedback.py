"""Feedback-weighted source priors for the scoring engine (Phase 3, Task 10).

Users confirm or reject authority candidates. Aggregating those outcomes per
``(org_id, field_name, authority_source)`` yields a learned prior: a source
whose candidates are consistently confirmed earns a small identifier boost,
while a consistently-rejected source earns a small penalty. The adjustment is
**bounded** to ±``_MAX_ADJUSTMENT`` so feedback tunes, but never dominates, the
weighted score — and is logged in the candidate ``evidence`` for auditability.

The prior is derived from running counters (cheap, idempotent) and memoized in
a short-TTL cache to avoid a DB round-trip on every candidate scored.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend import models
from backend.cache import MISS, get_cache, make_key

logger = logging.getLogger(__name__)

# Maximum absolute nudge applied to a source's identifier prior.
_MAX_ADJUSTMENT = 0.05
# Require a minimum number of observations before trusting the signal, and use
# it to damp small samples toward zero (confidence scaling).
_MIN_OBSERVATIONS = 3

_NAMESPACE = "authority:feedback"
_TTL = 300
_MAXSIZE = 4096

# Values are plain floats (JSON-native); identity (de)serialization is fine.
_backend = get_cache(_NAMESPACE, ttl=_TTL, maxsize=_MAXSIZE)


def clear_cache() -> int:
    """Drop all memoized priors (used by tests and after bulk updates)."""
    return _backend.invalidate_prefix("")


def compute_adjustment(confirmed: int, rejected: int) -> float:
    """Map confirm/reject counts to a bounded prior adjustment in ±0.05.

    - Below ``_MIN_OBSERVATIONS`` total outcomes → 0.0 (not enough signal).
    - Otherwise scale the confirm/reject balance by a confidence factor that
      grows with sample size, then clamp to ±``_MAX_ADJUSTMENT``.
    Symmetric: all-confirm → +cap, all-reject → −cap, balanced → 0.
    """
    confirmed = max(0, int(confirmed or 0))
    rejected = max(0, int(rejected or 0))
    total = confirmed + rejected
    if total < _MIN_OBSERVATIONS:
        return 0.0
    balance = (confirmed - rejected) / total  # [-1, 1]
    confidence = total / (total + _MIN_OBSERVATIONS)  # (0, 1), → 1 as total grows
    adj = balance * confidence * _MAX_ADJUSTMENT
    adj = max(-_MAX_ADJUSTMENT, min(_MAX_ADJUSTMENT, adj))
    return round(adj, 4)


def _scope_key(org_id: Optional[int], field_name: str, authority_source: str):
    return (org_id, field_name, authority_source)


def record_outcome(
    db,
    field_name: str,
    authority_source: str,
    *,
    confirmed: bool = False,
    rejected: bool = False,
    org_id: Optional[int] = None,
) -> models.AuthorityScoringFeedback:
    """Increment the confirm/reject counter for a scope (upsert).

    Caller is responsible for committing the session. Invalidates the cached
    prior for the affected scope.
    """
    row = (
        db.query(models.AuthorityScoringFeedback)
        .filter_by(org_id=org_id, field_name=field_name, authority_source=authority_source)
        .first()
    )
    if row is None:
        row = models.AuthorityScoringFeedback(
            org_id=org_id,
            field_name=field_name,
            authority_source=authority_source,
            confirmed=0,
            rejected=0,
        )
        db.add(row)
        # Flush so a subsequent call within the same uncommitted transaction
        # finds and increments this row instead of inserting a duplicate
        # (the session may have autoflush disabled).
        db.flush()
    if confirmed:
        row.confirmed = (row.confirmed or 0) + 1
    if rejected:
        row.rejected = (row.rejected or 0) + 1
    _backend.delete(make_key(_scope_key(org_id, field_name, authority_source)))
    return row


def get_source_prior(
    db,
    field_name: str,
    authority_source: str,
    org_id: Optional[int] = None,
) -> float:
    """Return the bounded prior adjustment for a scope (0.0 when unknown)."""
    scope = _scope_key(org_id, field_name, authority_source)
    key = make_key(scope)

    def _load() -> float:
        try:
            row = (
                db.query(models.AuthorityScoringFeedback)
                .filter_by(org_id=org_id, field_name=field_name, authority_source=authority_source)
                .first()
            )
            return compute_adjustment(row.confirmed, row.rejected) if row else 0.0
        except Exception as exc:  # defensive: scoring must not fail on feedback lookup
            logger.debug("get_source_prior failed for %s: %s", scope, exc)
            return 0.0

    return _backend.get_or_load(key, _load)


def get_source_priors(
    db,
    field_name: str,
    org_id: Optional[int] = None,
) -> dict[str, float]:
    """Return ``{authority_source: adjustment}`` for all sources of a field."""
    try:
        rows = (
            db.query(models.AuthorityScoringFeedback)
            .filter_by(org_id=org_id, field_name=field_name)
            .all()
        )
    except Exception as exc:
        logger.debug("get_source_priors failed for (%s, %s): %s", org_id, field_name, exc)
        return {}
    return {
        r.authority_source: compute_adjustment(r.confirmed, r.rejected)
        for r in rows
    }
