"""Storage + scope counters consumed by the /diagnostics endpoint.

These expose the full pipeline (raw storage -> scope filter -> materialized
stats) so an operator can see exactly where edges are lost — the tooling that
would have caught the original tenancy-scope bug this refactor fixes.
"""
from __future__ import annotations

from sqlalchemy import func

from backend import models


def diagnostics(db, *, org_id: int | None, domain_id: str) -> dict:
    """Row counts at each step of the scope pipeline for one (org, domain).

    org_id=None means an unscoped (super-admin global) view.
    """
    edges_total = db.query(models.CoauthorEdge).count()
    edge_scope_q = db.query(models.CoauthorEdge).filter_by(domain_id=domain_id)
    if org_id is not None:
        edge_scope_q = edge_scope_q.filter_by(org_id=org_id)
    edges_scoped = edge_scope_q.count()

    authors_total = db.query(models.Author).count()
    dirty_depth = db.query(models.CoauthorDirtyScope).count()
    last_stats = (
        db.query(func.max(models.AuthorStats.computed_at))
        .filter(models.AuthorStats.domain_id == domain_id)
        .scalar()
    )

    # coverage_pct = entities with materialized publications / eligible entities
    eligible_q = db.query(models.RawEntity).filter(models.RawEntity.domain == domain_id)
    if org_id is not None and org_id > 0:
        eligible_q = eligible_q.filter(models.RawEntity.org_id == org_id)
    eligible_entities = eligible_q.count()

    processed_q = db.query(
        func.count(func.distinct(models.AuthorPublication.entity_id))
    ).filter(models.AuthorPublication.domain_id == domain_id)
    if org_id is not None:
        processed_q = processed_q.filter(models.AuthorPublication.org_id == org_id)
    processed_entities = processed_q.scalar() or 0

    coverage = (processed_entities / eligible_entities * 100) if eligible_entities else 0.0

    breakdown = dict(
        db.query(models.CoauthorEdge.org_id, func.count())
        .group_by(models.CoauthorEdge.org_id)
        .all()
    )

    return {
        "edges_in_storage": edges_total,
        "edges_after_scope": edges_scoped,
        "authors_total": authors_total,
        "stats_computed_at": last_stats.isoformat() if last_stats else None,
        "dirty_queue_depth": dirty_depth,
        "coverage_pct": round(coverage, 2),
        "scope_breakdown": {"by_org": {str(k): v for k, v in breakdown.items()}},
    }
