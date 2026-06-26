"""Map OpenAlex raw `work.type` values to stable, locale-independent category
codes used by the work-type facet, filter, and badges. Single source of truth;
mirrored by frontend/app/lib/workType.ts."""
from typing import Optional

from sqlalchemy import and_, func

CATEGORY_CODES = ["article", "book", "thesis", "preprint", "dataset", "other", "unclassified"]

_RAW_TO_CODE = {
    "article": "article", "review": "article", "letter": "article", "editorial": "article",
    "book": "book", "monograph": "book", "book-chapter": "book", "reference-entry": "book",
    "dissertation": "thesis",
    "preprint": "preprint",
    "dataset": "dataset",
}
_KNOWN_RAWS = set(_RAW_TO_CODE)


def category_for(raw: Optional[str]) -> str:
    """Return the category code for a raw OpenAlex type. None -> 'unclassified',
    unmapped non-null -> 'other'."""
    if raw is None:
        return "unclassified"
    return _RAW_TO_CODE.get(raw.strip().lower(), "other")


def work_type_filter(col, code: str):
    """Return a SQLAlchemy boolean expression selecting rows in `code`, or None if
    `code` is not a known category. `col` is RawEntity.enrichment_work_type."""
    if code == "unclassified":
        return col.is_(None)
    if code == "other":
        return and_(col.isnot(None), func.lower(col).notin_(_KNOWN_RAWS))
    raws = [r for r, c in _RAW_TO_CODE.items() if c == code]
    if not raws:
        return None
    return func.lower(col).in_(raws)
