from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Optional

from sqlalchemy.orm import Session

from backend.models import JournalMetric


def normalize_impact_factors(db: Session, org_id: Optional[int]) -> int:
    """Compute field-normalized IF for all journals with a metric.

    NIF = two_yr_mean_citedness / median(metric within the same nif_field bucket).
    Returns the count of rows updated.
    """
    q = db.query(JournalMetric).filter(JournalMetric.two_yr_mean_citedness.isnot(None))
    if org_id is not None:
        q = q.filter(JournalMetric.org_id == org_id)
    rows = q.all()

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
            r.normalized_impact_factor = round(r.two_yr_mean_citedness / med, 4)
            r.nif_field = field
            r.nif_updated_at = now
            updated += 1
    db.flush()
    return updated
