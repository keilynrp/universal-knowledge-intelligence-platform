"""Read-only API for the Retrospective Intelligence Layer (Phase 4).

Exposes point-in-time reconstruction, current-vs-prior comparison, time-series,
and cohort queries over the append-only history. All endpoints are tenant-scoped
and read-only — they never mutate operational or retrospective tables.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from dataclasses import asdict

from backend import models
from backend.auth import require_role
from backend.database import get_db
from backend.retrospective import export, features, query
from backend.tenant_access import resolve_request_org_id

router = APIRouter(prefix="/retrospective", tags=["retrospective"])

_READ_ROLES = ("super_admin", "admin", "editor", "viewer")
_EXPORT_ROLES = ("super_admin", "admin")


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


# ── Warehouse export (Phase 5) ──────────────────────────────────────────────

@router.get("/export/readiness")
def export_readiness(
    current_user: models.User = Depends(require_role(*_EXPORT_ROLES)),
):
    """Warehouse export capability status (``configured`` / ``not_configured``)."""
    return export.export_readiness()


def _run_and_validate(result: export.ExportResult, schema, org_scope: Optional[int]) -> dict:
    report = export.validate_export(result, schema, org_scope=org_scope)
    return {
        "readiness": export.export_readiness(),
        "manifest": asdict(result.manifest),
        "validation": asdict(report),
    }


@router.post("/export/events")
def export_events(
    dataset_version: str = Query("v1"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_EXPORT_ROLES)),
):
    """Generate a tenant-scoped, versioned events dataset + auditable manifest.

    Works with no warehouse configured (readiness reports ``not_configured``); the
    dataset and manifest are still produced and validated for inspection.
    """
    org_scope = resolve_request_org_id(db, current_user)
    result = export.export_events(db, org_scope=org_scope, dataset_version=dataset_version)
    return _run_and_validate(result, export.EVENT_EXPORT_SCHEMA, org_scope)


@router.post("/export/snapshots")
def export_snapshots(
    dataset_version: str = Query("v1"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_EXPORT_ROLES)),
):
    """Generate a tenant-scoped, versioned snapshots dataset + auditable manifest."""
    org_scope = resolve_request_org_id(db, current_user)
    result = export.export_snapshots(db, org_scope=org_scope, dataset_version=dataset_version)
    return _run_and_validate(result, export.SNAPSHOT_EXPORT_SCHEMA, org_scope)


# ── ML feature readiness (Phase 6) ──────────────────────────────────────────

_FEATURE_SAMPLE_CAP = 200


@router.post("/features/journal-nif")
def build_journal_nif_features(
    dataset_version: str = Query("v1"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role(*_EXPORT_ROLES)),
):
    """Generate an OFFLINE journal-NIF feature dataset for validation.

    Point-in-time, leakage-checked, lineage-complete. Does NOT train or serve a
    model — returns dataset quality metrics and a capped row sample.
    """
    org_scope = resolve_request_org_id(db, current_user)
    ds = features.build_journal_nif_dataset(db, org_scope=org_scope, dataset_version=dataset_version)
    return {
        "dataset_id": ds.dataset_id,
        "dataset_version": ds.dataset_version,
        "org_scope": ds.org_scope,
        "created_at": ds.created_at,
        "leakage_ok": ds.leakage_ok,
        "quality": ds.quality,
        "rows": [asdict(r) for r in ds.rows[:_FEATURE_SAMPLE_CAP]],
        "row_sample_capped": len(ds.rows) > _FEATURE_SAMPLE_CAP,
    }
