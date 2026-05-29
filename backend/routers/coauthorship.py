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

from fastapi import APIRouter, Depends, HTTPException, Query
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
