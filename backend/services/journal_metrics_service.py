from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from backend.models import JournalMetric
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
