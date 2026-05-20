"""
Entity Read-Model Query Service
================================
Centralises the three mandatory guards that every RawEntity query must apply:

  1. Exclude ``source = 'graph_materializer'``  (graph-derived synthetic rows)
  2. Apply domain-scope filter via ``resolve_domain_filter``
  3. Apply org-level isolation via ``scope_query_to_org`` (when org_id is given)

Usage::

    from backend.services.entity_query import entity_base_q, count_total, count_enriched

    # Scoped base query — chain .filter(), .limit(), .all() as needed
    q = entity_base_q(db, "domain:science", org_id=request_org_id)
    entities = q.filter(models.RawEntity.quality_score > 0.8).all()

    # Count helpers
    total     = count_total(db, "domain:science", org_id)
    enriched  = count_enriched(db, "domain:science", org_id)

Routers that have been migrated to use this module
(add yours when you refactor):
  - backend/services/derived_status_service.py
  - backend/routers/entities.py      (enrich-stats, domain-stats)
  - backend/routers/analytics.py     (dashboard/summary, /stats)
  - backend/routers/disambiguation.py (field-group queries)
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, Query

from backend import models
from backend.domain_scope import parse_scope, resolve_domain_filter
from backend.schemas import EnrichmentStatus
from backend.tenant_access import scope_query_to_org

# The internal source tag written by the graph materialiser.
_GRAPH_MATERIALIZER_SOURCE = "graph_materializer"


def entity_base_q(
    db: Session,
    scope: str,
    org_id: Optional[int] = None,
) -> Query:
    """Return a SQLAlchemy Query for RawEntity with all three mandatory guards applied.

    Args:
        db:      Active SQLAlchemy session.
        scope:   Domain scope string (e.g. ``"all"``, ``"domain:science"``,
                 ``"legacy_default"``).  Parsed internally via ``parse_scope``.
        org_id:  Org ID for multi-tenant isolation.  Pass ``None`` to skip org
                 scoping (e.g. in admin utilities or tests without a tenant context).

    Returns:
        A Query that callers can further filter, limit, order, and execute.

    WARNING: Do NOT pass ``org_id=None`` in request-handling code where a real
    tenant context exists — doing so would return cross-org data silently.
    """
    parsed = parse_scope(scope)

    q: Query = db.query(models.RawEntity).filter(
        models.RawEntity.source != _GRAPH_MATERIALIZER_SOURCE
    )

    domain_filt = resolve_domain_filter(parsed, models.RawEntity)
    if domain_filt is not None:
        q = q.filter(domain_filt)

    if org_id is not None:
        q = scope_query_to_org(q, models.RawEntity, org_id)

    return q


def count_total(
    db: Session,
    scope: str,
    org_id: Optional[int] = None,
) -> int:
    """Return the total count of non-derived entities in the given scope."""
    return entity_base_q(db, scope, org_id).count()


def count_by_status(
    db: Session,
    scope: str,
    status: EnrichmentStatus,
    org_id: Optional[int] = None,
) -> int:
    """Return the count of entities with the given ``EnrichmentStatus`` in scope."""
    return (
        entity_base_q(db, scope, org_id)
        .filter(models.RawEntity.enrichment_status == status)
        .count()
    )


def count_enriched(
    db: Session,
    scope: str,
    org_id: Optional[int] = None,
) -> int:
    """Convenience wrapper: count entities with ``EnrichmentStatus.completed``."""
    return count_by_status(db, scope, EnrichmentStatus.completed, org_id)
