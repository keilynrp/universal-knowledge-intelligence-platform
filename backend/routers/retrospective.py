"""Read-only API for the Retrospective Intelligence Layer (Phase 4).

Exposes point-in-time reconstruction, current-vs-prior comparison, time-series,
and cohort queries over the append-only history. All endpoints are tenant-scoped
and read-only — they never mutate operational or retrospective tables.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend import models
from backend.auth import require_role
from backend.database import get_db
from backend.retrospective import query
from backend.tenant_access import resolve_request_org_id

router = APIRouter(prefix="/retrospective", tags=["retrospective"])

_READ_ROLES = ("super_admin", "admin", "editor", "viewer")


def _journal_current(db: Session, org_id: Optional[int], issn_l: str) -> Optional[dict]:
    """Current journal-metric state, shaped like a journal_metric snapshot payload."""
    row = (
        db.query(models.JournalMetric)
        .filter(models.JournalMetric.org_id == org_id, models.JournalMetric.issn_l == issn_l)
        .first()
    )
    if row is None:
        return None
    return {
        "nif": row.normalized_impact_factor,
        "nif_bayes": row.nif_bayes,
        "two_yr_mean_citedness": row.two_yr_mean_citedness,
        "works_2yr": row.works_2yr,
        "nif_field": row.nif_field,
    }


@router.get("/snapshot")
def get_point_in_time(
    snapshot_type: str = Query(...),
    subject_id: str = Query(...),
    as_of: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_READ_ROLES)),
):
    """Latest snapshot at or before ``as_of`` (typed missing-history if none)."""
    org_id = resolve_request_org_id(db, current_user)
    res = query.point_in_time_snapshot(
        db, org_id=org_id, snapshot_type=snapshot_type, subject_id=subject_id, as_of=as_of
    )
    return {
        "found": res.found,
        "snapshot_type": res.snapshot_type,
        "subject_id": res.subject_id,
        "valid_at": res.valid_at,
        "payload": res.payload,
        "missing_reason": res.missing_reason,
    }


@router.get("/journals/{issn_l}/timeseries")
def journal_timeseries(
    issn_l: str,
    since: Optional[datetime] = Query(None),
    until: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_READ_ROLES)),
):
    """Ordered journal-metric snapshot history for one journal."""
    org_id = resolve_request_org_id(db, current_user)
    return {
        "issn_l": issn_l,
        "series": query.snapshot_time_series(
            db, org_id=org_id, snapshot_type="journal_metric",
            subject_id=issn_l, since=since, until=until,
        ),
    }


@router.get("/journals/{issn_l}/compare")
def journal_compare(
    issn_l: str,
    as_of: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_READ_ROLES)),
):
    """Compare a journal's current metric state with its snapshot at ``as_of``."""
    org_id = resolve_request_org_id(db, current_user)
    current = _journal_current(db, org_id, issn_l)
    if current is None:
        raise HTTPException(status_code=404, detail="Journal not found")
    res = query.compare_to_snapshot(
        db, org_id=org_id, snapshot_type="journal_metric",
        subject_id=issn_l, as_of=as_of, current=current,
    )
    return {
        "issn_l": issn_l,
        "found_prior": res.found_prior,
        "as_of": res.as_of,
        "prior_valid_at": res.prior_valid_at,
        "current": res.current,
        "prior": res.prior,
        "changed_fields": res.changed_fields,
        "missing_reason": res.missing_reason,
    }


@router.get("/cohort")
def cohort(
    event_type: str = Query(...),
    since: datetime = Query(...),
    until: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_READ_ROLES)),
):
    """Subjects whose first event of ``event_type`` occurred within [since, until]."""
    org_id = resolve_request_org_id(db, current_user)
    members = query.cohort_by_first_event(
        db, org_id=org_id, event_type=event_type, since=since, until=until
    )
    return {"event_type": event_type, "since": since, "until": until,
            "count": len(members), "members": members}
