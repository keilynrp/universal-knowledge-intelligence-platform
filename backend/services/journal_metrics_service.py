from datetime import datetime, timezone
from statistics import median as _median
from typing import Optional, Tuple
from sqlalchemy import func, nullslast
from sqlalchemy.orm import Session

from backend.models import JournalMetric, RawEntity
from backend.schemas_enrichment import JournalMetrics


def upsert_journal_metric(
    db: Session,
    jm: JournalMetrics,
    org_id: Optional[int],
    doaj: Optional[dict] = None,
) -> Optional[JournalMetric]:
    """Insert or update the JournalMetric row for (org_id, issn_l).

    OpenAlex provides the base record; DOAJ (when present) overrides APC
    amount/currency/source and the is_in_doaj flag. Returns None if no ISSN-L.
    """
    if not jm or not jm.issn_l:
        return None

    row = (
        db.query(JournalMetric)
        .filter(JournalMetric.org_id == org_id, JournalMetric.issn_l == jm.issn_l)
        .first()
    )
    if row is None:
        row = JournalMetric(org_id=org_id, issn_l=jm.issn_l)
        db.add(row)

    row.source_id = jm.source_id or row.source_id
    row.display_name = jm.display_name or row.display_name
    if jm.two_yr_mean_citedness is not None:
        row.two_yr_mean_citedness = jm.two_yr_mean_citedness
    if jm.h_index is not None:
        row.h_index = jm.h_index
    if jm.works_2yr is not None:
        row.works_2yr = jm.works_2yr
    if jm.nif_field:
        # OpenAlex primary subfield → the NIF normalization bucket. Only overwrite
        # when present so a later cached/pre-subfield upsert can't wipe it.
        row.nif_field = jm.nif_field
    row.if_metric_kind = "openalex_2yr_mean_citedness"

    # APC: OpenAlex baseline
    if jm.apc_usd is not None:
        row.apc_usd = jm.apc_usd
        row.apc_currency = "USD"
        row.apc_source = "openalex"
    if jm.is_in_doaj is not None:
        row.is_in_doaj = jm.is_in_doaj

    # DOAJ override wins
    if doaj:
        if doaj.get("apc_amount") is not None:
            row.apc_usd = doaj["apc_amount"]  # nominal amount; currency carries the unit
            row.apc_currency = doaj.get("apc_currency")
            row.apc_source = "doaj"
        if doaj.get("is_in_doaj") is not None:
            row.is_in_doaj = doaj["is_in_doaj"]

    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()
    return row


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------
_SORT_COLUMNS = {
    "nif": JournalMetric.normalized_impact_factor,
    "citedness": JournalMetric.two_yr_mean_citedness,
    "apc": JournalMetric.apc_usd,
    "h_index": JournalMetric.h_index,
    "nif_bayes": JournalMetric.nif_bayes,
}


def _scoped(db: Session, org_id: Optional[int]):
    return db.query(JournalMetric).filter(JournalMetric.org_id == org_id)


def get_journal_metric(db: Session, org_id: Optional[int], issn_l: str) -> Optional[JournalMetric]:
    return _scoped(db, org_id).filter(JournalMetric.issn_l == issn_l).first()


def list_journal_metrics(
    db: Session,
    org_id: Optional[int],
    sort_by: str = "nif",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    field: Optional[str] = None,
) -> Tuple[list, int]:
    col = _SORT_COLUMNS[sort_by]  # caller validates sort_by; KeyError → 422 upstream
    q = _scoped(db, org_id)
    if field:
        q = q.filter(JournalMetric.nif_field == field)
    total = q.count()
    direction = col.desc() if order == "desc" else col.asc()
    rows = q.order_by(nullslast(direction)).offset(offset).limit(limit).all()
    return rows, total


def journal_stats(db: Session, org_id: Optional[int]) -> dict:
    rows = _scoped(db, org_id).all()
    by_cur: dict = {}
    for r in rows:
        if r.apc_usd is None:
            continue
        by_cur.setdefault(r.apc_currency, []).append(r.apc_usd)
    apc_distribution = [
        {
            "currency": cur,
            "count": len(v),
            "min": min(v),
            "max": max(v),
            "median": float(_median(v)),
        }
        for cur, v in sorted(by_cur.items(), key=lambda kv: (kv[0] is None, kv[0]))
    ]
    total = len(rows)
    in_doaj = sum(1 for r in rows if r.is_in_doaj)
    open_access_share = {
        "in_doaj": in_doaj,
        "total": total,
        "pct": round(in_doaj / total * 100, 1) if total else 0.0,
    }
    by_field: dict = {}
    for r in rows:
        if r.normalized_impact_factor is None:
            continue
        by_field.setdefault(r.nif_field, []).append(r.normalized_impact_factor)
    nif_by_field = sorted(
        [
            {
                "nif_field": f,
                "journal_count": len(v),
                "mean_nif": round(sum(v) / len(v), 4),
            }
            for f, v in by_field.items()
        ],
        key=lambda d: d["mean_nif"],
        reverse=True,
    )
    return {
        "apc_distribution": apc_distribution,
        "open_access_share": open_access_share,
        "nif_by_field": nif_by_field,
    }


def works_count_by_issn(db: Session, org_id: Optional[int],
                        issns: Optional[list[str]] = None) -> dict[str, int]:
    """Count works (raw_entities) per journal ISSN, org-scoped.

    Mirrors the read scoping of the journal endpoints: filters
    raw_entities.org_id == org_id (IS NULL when org_id is None). Optional
    `issns` narrows the count to a specific set of journals (e.g. one page).
    """
    q = (db.query(RawEntity.enrichment_issn_l, func.count(RawEntity.id))
           .filter(RawEntity.enrichment_issn_l.isnot(None))
           .filter(RawEntity.org_id == org_id))
    if issns:
        q = q.filter(RawEntity.enrichment_issn_l.in_(issns))
    return {issn: cnt for issn, cnt in q.group_by(RawEntity.enrichment_issn_l).all()}
