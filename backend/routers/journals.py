"""Read-only journal-metrics endpoints (NIF + APC surfacing)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import get_current_user
from backend.database import get_db
from backend.tenant_access import resolve_request_org_id
from backend.services.journal_metrics_service import (
    get_journal_metric,
    list_journal_metrics,
    journal_stats,
    works_count_by_issn,
)

router = APIRouter(tags=["journals"])

_SORT_BY = {"nif", "citedness", "apc", "h_index"}
_ORDER = {"asc", "desc"}


@router.get("/journals/stats", response_model=schemas.JournalStatsResponse)
def get_journal_stats(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, user)
    return journal_stats(db, org_id)


@router.get("/journals", response_model=list[schemas.JournalMetricResponse])
def list_journals(
    response: Response,
    sort_by: str = Query("nif"),
    order: str = Query("desc"),
    field: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if sort_by not in _SORT_BY:
        raise HTTPException(422, f"sort_by must be one of {sorted(_SORT_BY)}")
    if order not in _ORDER:
        raise HTTPException(422, "order must be 'asc' or 'desc'")
    org_id = resolve_request_org_id(db, user)
    rows, total = list_journal_metrics(db, org_id, sort_by, order, limit, offset, field)
    response.headers["X-Total-Count"] = str(total)
    items = [schemas.JournalMetricResponse.model_validate(r) for r in rows]
    counts = works_count_by_issn(db, org_id, issns=[r.issn_l for r in rows])
    for it in items:
        it.works_count = counts.get(it.issn_l, 0)
    return items


@router.get("/journals/{issn_l}", response_model=schemas.JournalMetricResponse)
def get_journal(
    issn_l: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    org_id = resolve_request_org_id(db, user)
    row = get_journal_metric(db, org_id, issn_l)
    if row is None:
        raise HTTPException(404, "journal not found")
    resp = schemas.JournalMetricResponse.model_validate(row)
    resp.works_count = works_count_by_issn(db, org_id, issns=[issn_l]).get(issn_l, 0)
    return resp
