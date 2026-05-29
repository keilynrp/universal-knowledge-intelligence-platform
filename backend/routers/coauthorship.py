"""V2 coauthorship API (Sprint 2026-05-28 refactor).

This task (F4a.2/F4a.3) ships diagnostics, an admin recompute trigger, a
merge-suggestions list, and the admin migration endpoint. The V2 network/author
readers and merge confirm/reject actions land in F4b behind COAUTHOR_V2_READ.

Scope translation is critical: tenant_access uses LEGACY_GLOBAL_ORG_ID = -1 for
legacy/global users, but the V2 tables store legacy rows under org_id = 0 (the
NOT NULL DEFAULT sentinel). `_scope_org_id` maps between them — skipping this is
exactly the tenancy mismatch this refactor exists to fix.
"""
from __future__ import annotations

import logging
import time

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.coauthorship.diagnostics import diagnostics as _diagnostics
from backend.coauthorship.recompute import recompute_coauthor_stats
from backend.database import get_db
from backend.tenant_access import is_legacy_global_scope, resolve_request_org_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["coauthorship"])

_LEGACY_GLOBAL_V2_SENTINEL = 0
_RECOMPUTE_MIN_INTERVAL_S = 30
_recompute_last_call: dict[tuple[int | None, str], float] = {}


def _scope_org_id(resolved: int | None) -> int | None:
    """Map the tenant_access result onto the V2 storage convention.

    - super_admin global view -> None (no org filter)
    - legacy/global users (-1) -> 0 (matches the storage default sentinel)
    - real org users           -> org_id unchanged
    """
    if resolved is None:
        return None
    if is_legacy_global_scope(resolved):
        return _LEGACY_GLOBAL_V2_SENTINEL
    return resolved


def _ensure_coauthor_stats_ready(db: Session, *, org_id: int | None, domain_id: str) -> None:
    """Synchronously materialize stats when V2 edges exist but stats do not.

    This is intentionally defensive for production cutover: a Dokploy restart,
    missed worker loop, or manual migration can leave coauthor_edges populated
    while author_stats is empty, which makes the graph look blank. The endpoint
    can repair that state cheaply for the current domain/scope before reading.
    """
    stats_q = db.query(models.AuthorStats).filter_by(domain_id=domain_id)
    edges_q = db.query(models.CoauthorEdge).filter_by(domain_id=domain_id)
    if org_id is not None:
        stats_q = stats_q.filter_by(org_id=org_id)
        edges_q = edges_q.filter_by(org_id=org_id)

    stats_count = stats_q.count()
    edges_count = edges_q.count()
    if stats_count > 0 or edges_count == 0:
        return
    if org_id is not None:
        recompute_coauthor_stats(db, org_id=org_id, domain_id=domain_id)
        return

    scopes = (
        db.query(models.CoauthorEdge.org_id)
        .filter_by(domain_id=domain_id)
        .distinct()
        .all()
    )
    for (scope_org_id,) in scopes:
        recompute_coauthor_stats(db, org_id=scope_org_id, domain_id=domain_id)


@router.get("/analyzers/coauthorship/{domain_id}")
def coauthorship_network_v2(
    response: Response,
    domain_id: str,
    min_weight: int = Query(default=1, ge=1),
    limit: int | None = Query(default=100, ge=1, le=500),
    community_id: int | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=80),
    force_refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Co-authorship network served from materialized V2 tables (author_stats +
    coauthor_edges). Behind COAUTHOR_V2_READ; when off, falls through to the
    legacy analyzer so behaviour is unchanged until cutover."""
    from backend import config

    if not config.COAUTHOR_V2_READ:
        from backend.routers.analytics import _legacy_coauthorship_network
        return _legacy_coauthorship_network(
            response=response,
            domain_id=domain_id,
            min_weight=min_weight,
            limit=limit,
            force_refresh=force_refresh,
            db=db,
            current_user=current_user,
        )

    response.headers["Cache-Control"] = "no-store"
    org_id = _scope_org_id(resolve_request_org_id(db, current_user))
    _ensure_coauthor_stats_ready(db, org_id=org_id, domain_id=domain_id)

    q = (
        db.query(models.AuthorStats, models.Author)
        .join(models.Author, models.Author.id == models.AuthorStats.author_id)
        .filter(models.AuthorStats.domain_id == domain_id)
    )
    if org_id is not None:
        q = q.filter(models.AuthorStats.org_id == org_id)
    if community_id is not None:
        q = q.filter(models.AuthorStats.community_id == community_id)
    if search:
        q = q.filter(models.Author.display_name.ilike(f"%{search}%"))
    q = q.order_by(models.AuthorStats.centrality.desc())
    if limit:
        q = q.limit(limit)
    rows = q.all()

    node_ids = [a.id for _s, a in rows]
    nodes = [
        {
            "id": str(a.id),
            "label": a.display_name,
            "degree": s.degree,
            "centrality": s.centrality,
            "community_id": s.community_id,
            "total_publications": s.publication_count,
        }
        for s, a in rows
    ]

    if not node_ids:
        edge_rows = []
    else:
        node_id_set = set(node_ids)
        edge_q = (
            db.query(models.CoauthorEdge)
            .filter(models.CoauthorEdge.domain_id == domain_id)
            .filter(models.CoauthorEdge.author_a_id.in_(node_ids))
            .filter(models.CoauthorEdge.author_b_id.in_(node_ids))
            .filter(models.CoauthorEdge.weight >= min_weight)
        )
        if org_id is not None:
            edge_q = edge_q.filter(models.CoauthorEdge.org_id == org_id)
        # Both endpoints must be in the surviving node set (the .in_ filters
        # already guarantee this, but keep the guard explicit for limit pruning).
        edge_rows = [
            e for e in edge_q.all()
            if e.author_a_id in node_id_set and e.author_b_id in node_id_set
        ]

    edges = [
        {"source": str(e.author_a_id), "target": str(e.author_b_id), "weight": e.weight}
        for e in edge_rows
    ]

    latest = max((s.computed_at for s, _ in rows), default=None)
    stale = False
    if latest is not None:
        # SQLite can return naive datetimes; normalize before comparing.
        latest_aware = latest if latest.tzinfo else latest.replace(tzinfo=timezone.utc)
        stale = latest_aware < datetime.now(timezone.utc) - timedelta(minutes=5)
    coverage = _diagnostics(db, org_id=org_id, domain_id=domain_id)["coverage_pct"]

    return {
        "domain_id": domain_id,
        "nodes": nodes,
        "edges": edges,
        "computed_at": latest.isoformat() if latest else None,
        "stale": stale,
        "coverage_pct": coverage,
    }


def _entity_title_year(entity) -> tuple[str, int | None]:
    """Best-effort (title, year) from a RawEntity's attributes_json, falling
    back to primary_label for the title."""
    import json as _json

    title = entity.primary_label or f"entity {entity.id}"
    year = None
    try:
        attrs = _json.loads(entity.attributes_json or "{}")
    except (ValueError, TypeError):
        attrs = {}
    title = attrs.get("title") or title
    for key in ("publication_year", "year", "enrichment_year"):
        val = attrs.get(key)
        if val:
            try:
                year = int(str(val)[:4])
                break
            except (ValueError, TypeError):
                continue
    return title, year


@router.get("/analyzers/coauthorship/{domain_id}/author/{author_id}")
def coauthorship_author_detail(
    domain_id: str,
    author_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict:
    """Detail for one author within a scope: identity header, stats, top
    publications (by year desc), and top collaborators (by edge weight desc).
    Served from the V2 tables; no legacy equivalent."""
    org_id = _scope_org_id(resolve_request_org_id(db, current_user))

    author = db.query(models.Author).filter_by(id=author_id).first()
    if author is None:
        raise HTTPException(status_code=404, detail="author not found")

    stats_q = db.query(models.AuthorStats).filter_by(
        author_id=author_id, domain_id=domain_id
    )
    if org_id is not None:
        stats_q = stats_q.filter_by(org_id=org_id)
    stats = stats_q.first()

    # Publications in this scope.
    pub_q = db.query(models.AuthorPublication).filter_by(
        author_id=author_id, domain_id=domain_id
    )
    if org_id is not None:
        pub_q = pub_q.filter_by(org_id=org_id)
    pub_rows = pub_q.all()
    entity_ids = [p.entity_id for p in pub_rows]
    publications = []
    if entity_ids:
        for ent in db.query(models.RawEntity).filter(models.RawEntity.id.in_(entity_ids)).all():
            title, year = _entity_title_year(ent)
            publications.append({"entity_id": ent.id, "title": title, "year": year})
        publications.sort(key=lambda p: (p["year"] is not None, p["year"] or 0), reverse=True)
        publications = publications[:20]

    # Collaborators: edges incident to this author in scope, by weight desc.
    edge_q = db.query(models.CoauthorEdge).filter(
        models.CoauthorEdge.domain_id == domain_id,
        (models.CoauthorEdge.author_a_id == author_id)
        | (models.CoauthorEdge.author_b_id == author_id),
    )
    if org_id is not None:
        edge_q = edge_q.filter(models.CoauthorEdge.org_id == org_id)
    edges = sorted(edge_q.all(), key=lambda e: e.weight, reverse=True)[:50]
    other_ids = [
        (e.author_b_id if e.author_a_id == author_id else e.author_a_id) for e in edges
    ]
    other_names = {
        a.id: a.display_name
        for a in db.query(models.Author).filter(models.Author.id.in_(other_ids)).all()
    } if other_ids else {}
    collaborators = [
        {
            "author_id": oid,
            "name": other_names.get(oid),
            "weight": e.weight,
        }
        for e, oid in zip(edges, other_ids)
    ]

    return {
        "author_id": author.id,
        "display_name": author.display_name,
        "orcid": author.orcid,
        "aliases": author.aliases_list,
        "metrics": {
            "degree": stats.degree if stats else 0,
            "centrality": stats.centrality if stats else 0.0,
            "community_id": stats.community_id if stats else None,
            "publication_count": stats.publication_count if stats else len(pub_rows),
        },
        "publications": publications,
        "collaborators": collaborators,
    }


@router.get("/analyzers/coauthorship/{domain_id}/diagnostics")
def coauthorship_diagnostics(
    domain_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict:
    """Pipeline counters for one scope: storage -> scope filter -> stats."""
    org_id = _scope_org_id(resolve_request_org_id(db, current_user))
    return _diagnostics(db, org_id=org_id, domain_id=domain_id)


class RecomputeResponse(BaseModel):
    domain_id: str
    scopes_recomputed: int = Field(description="Number of (org, domain) scopes recomputed.")
    results: list[dict]


@router.post("/analyzers/coauthorship/{domain_id}/recompute", response_model=RecomputeResponse)
def coauthorship_recompute(
    domain_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
) -> RecomputeResponse:
    """Force a synchronous recompute of author_stats for the caller's scope.

    Rate-limited to one call per scope per 30s (in-memory, per process) so an
    operator can't hammer the (potentially seconds-long) Louvain job.
    """
    org_id = _scope_org_id(resolve_request_org_id(db, current_user))

    rl_key = (org_id, domain_id)
    now = time.monotonic()
    last = _recompute_last_call.get(rl_key)
    if last is not None and (now - last) < _RECOMPUTE_MIN_INTERVAL_S:
        retry_in = int(_RECOMPUTE_MIN_INTERVAL_S - (now - last))
        raise HTTPException(
            status_code=429,
            detail=f"recompute throttled; retry in ~{retry_in}s",
            headers={"Retry-After": str(retry_in)},
        )
    _recompute_last_call[rl_key] = now

    # Determine which scopes to recompute. A scoped user recomputes their own;
    # a super-admin global view recomputes every org that has edges in the domain.
    if org_id is not None:
        target_orgs = [org_id]
    else:
        target_orgs = [
            row[0]
            for row in db.query(models.CoauthorEdge.org_id)
            .filter(models.CoauthorEdge.domain_id == domain_id)
            .distinct()
            .all()
        ]

    results = []
    for oid in target_orgs:
        results.append({
            "org_id": oid,
            **recompute_coauthor_stats(db, org_id=oid, domain_id=domain_id),
        })
    return RecomputeResponse(
        domain_id=domain_id, scopes_recomputed=len(results), results=results
    )


@router.get("/coauthorship/merge-suggestions")
def list_merge_suggestions(
    status: str = Query(default="pending", pattern="^(pending|merged|rejected)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
) -> list[dict]:
    """List author merge suggestions (ambiguous identity pairs) for review."""
    rows = (
        db.query(models.AuthorMergeSuggestion)
        .filter(models.AuthorMergeSuggestion.status == status)
        .order_by(models.AuthorMergeSuggestion.created_at.desc())
        .limit(limit)
        .all()
    )
    author_ids = {r.author_a_id for r in rows} | {r.author_b_id for r in rows}
    names = {
        a.id: a.display_name
        for a in db.query(models.Author).filter(models.Author.id.in_(author_ids)).all()
    } if author_ids else {}
    return [
        {
            "id": r.id,
            "author_a_id": r.author_a_id,
            "author_a_name": names.get(r.author_a_id),
            "author_b_id": r.author_b_id,
            "author_b_name": names.get(r.author_b_id),
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ── F4b.3: merge-suggestions confirm / reject ───────────────────────────────


def _enqueue_author_scopes(db, author_id: int, reason: str) -> None:
    """Mark every (org, domain) scope the author has publications in as dirty."""
    scopes = (
        db.query(models.AuthorPublication.org_id, models.AuthorPublication.domain_id)
        .filter(models.AuthorPublication.author_id == author_id)
        .distinct()
        .all()
    )
    for org_id, domain_id in scopes:
        db.merge(models.CoauthorDirtyScope(org_id=org_id, domain_id=domain_id, reason=reason))


@router.post("/coauthorship/merge-suggestions/generate")
def generate_merge_suggestions_endpoint(
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_role("super_admin", "admin")),
) -> dict:
    """Scan authors and enqueue ambiguous (last+initial) pairs for review.
    Idempotent — safe to re-run; existing pairs are skipped."""
    from backend.coauthorship.suggestions import generate_merge_suggestions

    return generate_merge_suggestions(db)


@router.post("/coauthorship/merge-suggestions/{suggestion_id}/confirm")
def confirm_merge_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
) -> dict:
    """Confirm an ambiguous pair as the same person: merge author_b into
    author_a (manual tier), repoint rows, write the audit, and enqueue the
    surviving author's scopes for recompute."""
    from backend.coauthorship.identity import merge_authors

    s = db.query(models.AuthorMergeSuggestion).filter_by(id=suggestion_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="merge suggestion not found")
    if s.status != "pending":
        raise HTTPException(status_code=409, detail=f"suggestion already {s.status}")

    winner = db.query(models.Author).filter_by(id=s.author_a_id).first()
    loser = db.query(models.Author).filter_by(id=s.author_b_id).first()
    if winner is None or loser is None:
        raise HTTPException(status_code=409, detail="one of the authors no longer exists")

    merge_authors(
        db, winner, loser,
        tier="manual",
        reason=s.reason or "manual merge",
        performed_by=current_user.id,
        evidence={"suggestion_id": s.id},
    )
    _enqueue_author_scopes(db, winner.id, reason="merge")

    s.status = "merged"
    s.resolved_at = datetime.now(timezone.utc)
    s.resolved_by = current_user.id
    db.commit()
    return {
        "status": "merged",
        "winner_author_id": winner.id,
        "loser_author_id": s.author_b_id,
    }


@router.post("/coauthorship/merge-suggestions/{suggestion_id}/reject")
def reject_merge_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
) -> dict:
    """Mark an ambiguous pair as distinct people — they stay separate."""
    s = db.query(models.AuthorMergeSuggestion).filter_by(id=suggestion_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="merge suggestion not found")
    if s.status != "pending":
        raise HTTPException(status_code=409, detail=f"suggestion already {s.status}")
    s.status = "rejected"
    s.resolved_at = datetime.now(timezone.utc)
    s.resolved_by = current_user.id
    db.commit()
    return {"status": "rejected"}


# ── F4a.3: admin one-shot migration trigger ─────────────────────────────────


class MigrateCoauthorRequest(BaseModel):
    dry_run: bool = Field(
        default=True,
        description="Scan + report counts without writing. Defaults true for safety.",
    )
    domain: str | None = Field(
        default=None, max_length=64,
        description="Restrict to one domain_id. None = all domains.",
    )


@router.post("/admin/data-fixes/migrate-coauthor-graph")
def migrate_coauthor_graph_endpoint(
    payload: MigrateCoauthorRequest,
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_role("super_admin", "admin")),
) -> dict:
    """Run the one-shot legacy -> V2 coauthorship migration. Idempotent.
    Defaults to dry-run; callers must explicitly opt out to mutate data."""
    from backend.coauthorship.migration import migrate_coauthor_graph

    logger.info(
        "migrate-coauthor-graph dispatched dry_run=%s domain=%s",
        payload.dry_run, payload.domain,
    )
    try:
        stats = migrate_coauthor_graph(db, dry_run=payload.dry_run, domain=payload.domain)
    except Exception:
        logger.exception("coauthor graph migration failed")
        raise HTTPException(status_code=500, detail="coauthor graph migration failed")
    return {"mode": "dry-run" if payload.dry_run else "applied", **stats}
