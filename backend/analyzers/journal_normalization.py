from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Optional

from sqlalchemy.orm import Session

from backend.models import JournalMetric
from backend.retrospective.emit import emit_journal_metric_normalized


def normalize_impact_factors(db: Session, org_id: Optional[int]) -> int:
    """Compute field-normalized IF for all journals with a metric.

    NIF = two_yr_mean_citedness / median(metric within the same nif_field bucket).
    Returns the count of rows updated.
    """
    q = db.query(JournalMetric).filter(JournalMetric.two_yr_mean_citedness.isnot(None))
    if org_id is not None:
        q = q.filter(JournalMetric.org_id == org_id)
    rows = q.all()

    # Bucket by the OpenAlex primary subfield (populated by the enrichment
    # pipeline). Journals whose subfield is unknown fall back to a shared "all"
    # bucket so they are still normalized against each other rather than skipped.
    buckets: dict[str, list[JournalMetric]] = defaultdict(list)
    for r in rows:
        buckets[r.nif_field or "all"].append(r)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    updated = 0
    for field, group in buckets.items():
        med = median([r.two_yr_mean_citedness for r in group])
        if not med:
            continue
        for r in group:
            prior_nif = r.normalized_impact_factor
            new_nif = round(r.two_yr_mean_citedness / med, 4)
            r.normalized_impact_factor = new_nif
            r.nif_field = field
            r.nif_updated_at = now
            updated += 1
            emit_journal_metric_normalized(
                db,
                org_id=r.org_id,
                issn_l=r.issn_l,
                new_nif=new_nif,
                prior_nif=prior_nif,
                nif_field=field,
                field_median=med,
                occurred_at=now,
                source_id=r.source_id,
            )
    db.flush()
    return updated
