"""Admin-only read of the OpenAlex analytical lake.

Two surfaces, both read-only against the lake DuckDB file:
- status: what `python -m backend.openalex_lake.status` prints (ingestion
  phase, backfill progress, table counts, last captured quota snapshot).
- explorer: list the whitelisted analysis views and run bounded, parameterized
  queries against them, so the historical data is browsable from the dashboard
  instead of requiring container-terminal SQL.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend import models
from backend.auth import require_role
from backend.database import get_db
from backend.openalex_lake.config import LakeSettings
from backend.openalex_lake.explore import (
    BadOrderByError,
    UnknownViewError,
    list_views,
    resolve_query,
)
from backend.openalex_lake.status import resolve_status

router = APIRouter(tags=["openalex-lake"])


@router.get("/admin/openalex-lake/status")
def get_openalex_lake_status(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Ingestion status: phase, backfill progress, table counts, quota snapshot.

    Read-only against the lake DuckDB file; safe to call while a pull is
    running (reports `{"lake": "locked"}` instead of erroring) or before the
    first pull has ever run (`{"lake": "not_initialized"}`). `total_issns`
    (the intended backfill scope) comes from distinct journal_metrics.issn_l
    so the dashboard can render a completion percentage.
    """
    total_issns = (
        db.query(models.JournalMetric.issn_l)
        .filter(models.JournalMetric.issn_l.isnot(None))
        .distinct()
        .count()
    )
    return resolve_status(LakeSettings().db_path, total_issns=total_issns or None)


@router.get("/admin/openalex-lake/views")
def get_openalex_lake_views(
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """The explorer's catalog: whitelisted analysis views grouped by axis."""
    return {"axes": list_views()}


@router.get("/admin/openalex-lake/query/{view}")
def query_openalex_lake_view(
    view: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    order_by: Optional[str] = Query(default=None),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    issn_l: Optional[str] = Query(default=None),
    field: Optional[str] = Query(default=None),
    year_min: Optional[int] = Query(default=None, ge=1000, le=3000),
    year_max: Optional[int] = Query(default=None, ge=1000, le=3000),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Bounded, parameterized read of one whitelisted analysis view.

    Filters apply only where the view has the column (harmless elsewhere).
    Friendly non-error states mirror /status: {"lake": "not_initialized"} and
    {"lake": "locked"} come back as 200 so the UI renders them as states.
    """
    try:
        return resolve_query(
            LakeSettings().db_path,
            view,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=order == "desc",
            issn_l=issn_l,
            field=field,
            year_min=year_min,
            year_max=year_max,
        )
    except UnknownViewError:
        raise HTTPException(status_code=404, detail=f"Unknown analysis view: {view}")
    except BadOrderByError as exc:
        raise HTTPException(status_code=422, detail=f"order_by is not a column of {view}: {exc}")
