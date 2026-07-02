"""Admin-only read of the OpenAlex analytical lake's operational status.

Surfaces what `python -m backend.openalex_lake.status` prints (ingestion phase,
backfill progress, per-table counts, and the last OpenAlex quota snapshot
captured for free during a pull) so it can be shown in a dashboard instead of
requiring container-terminal access.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend import models
from backend.auth import require_role
from backend.database import get_db
from backend.openalex_lake.config import LakeSettings
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
