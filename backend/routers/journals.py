"""Read-only journal-metrics endpoints (NIF + APC surfacing)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import get_current_user
from backend.database import get_db
from backend.tenant_access import resolve_request_org_id, scope_query_to_org
from backend.services.entity_service import EntityService
from backend.services.journal_metrics_service import (
    get_journal_metric,
    list_journal_metrics,
    journal_stats,
    works_count_by_issn,
)

router = APIRouter(tags=["journals"])

_SORT_BY = {"nif", "citedness", "apc", "h_index", "nif_bayes"}
_ORDER = {"asc", "desc"}
_METRIC_SIGNALS = {"nif_bayes_ready"}


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
    metric_signal: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if sort_by not in _SORT_BY:
        raise HTTPException(422, f"sort_by must be one of {sorted(_SORT_BY)}")
    if order not in _ORDER:
        raise HTTPException(422, "order must be 'asc' or 'desc'")
    if metric_signal is not None and metric_signal not in _METRIC_SIGNALS:
        raise HTTPException(422, f"metric_signal must be one of {sorted(_METRIC_SIGNALS)}")
    org_id = resolve_request_org_id(db, user)
    rows, total = list_journal_metrics(
        db,
        org_id,
        sort_by,
        order,
        limit,
        offset,
        field,
        metric_signal,
    )
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


@router.get("/journals/{issn_l}/works", response_model=list[schemas.Entity])
def list_journal_works(
    response: Response,
    issn_l: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """List the catalog records (works) linked to a journal by ISSN-L.

    Complements the works_count surfaced on the journal rows: this resolves the
    actual records behind that count, each carrying the attached NIF + Bayes
    signal so callers can jump straight from a journal to its works.
    """
    org_id = resolve_request_org_id(db, user)
    query = scope_query_to_org(
        db.query(models.RawEntity).filter(models.RawEntity.enrichment_issn_l == issn_l),
        models.RawEntity,
        org_id,
    )
    total = query.count()
    works = query.order_by(models.RawEntity.id.asc()).offset(offset).limit(limit).all()
    EntityService.attach_journal_metrics(db, works, org_id)
    response.headers["X-Total-Count"] = str(total)
    return works
