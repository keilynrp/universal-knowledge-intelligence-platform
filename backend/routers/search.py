"""
Phase 12 Sprint 53 — Full-Text Search (FTS5)
  GET  /search          — global search across entities + authority + annotations
  POST /search/rebuild  — rebuild FTS index (admin+)
"""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

# ── FTS helpers ───────────────────────────────────────────────────────────────

_UNSAFE_RE = re.compile(r'[^\w\s\-]', re.UNICODE)


def _fts_query(raw: str) -> str:
    """
    Convert a raw user string into a safe FTS5 MATCH expression.
    - Strips characters that could break the FTS5 parser.
    - Appends '*' to every token for prefix matching (autocomplete feel).
    """
    cleaned = _UNSAFE_RE.sub(" ", raw).strip()
    tokens  = [t for t in cleaned.split() if t]
    if not tokens:
        return '""'
    return " ".join(f'"{t}"*' for t in tokens)


def _rebuild(db: Session) -> int:
    """Drop + repopulate the search_index FTS5 table. Returns row count."""
    db.execute(text("DELETE FROM search_index"))

    db.execute(text("""
        INSERT INTO search_index (doc_type, doc_id, title, body, href)
        SELECT
            'entity',
            id,
            COALESCE(entity_name, ''),
            COALESCE(sku, '') || ' ' ||
            COALESCE(brand_capitalized, '') || ' ' ||
            COALESCE(enrichment_concepts, ''),
            '/entities/' || id
        FROM raw_entities
    """))

    db.execute(text("""
        INSERT INTO search_index (doc_type, doc_id, title, body, href)
        SELECT
            'authority',
            id,
            COALESCE(canonical_label, original_value, ''),
            COALESCE(description, '') || ' ' || COALESCE(original_value, ''),
            '/authority'
        FROM authority_records
    """))

    db.execute(text("""
        INSERT INTO search_index (doc_type, doc_id, title, body, href)
        SELECT
            'annotation',
            id,
            COALESCE(content, ''),
            '',
            '/disambiguation'
        FROM annotations
    """))

    db.commit()

    row = db.execute(text("SELECT COUNT(*) FROM search_index")).fetchone()
    return row[0] if row else 0


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def global_search(
    q:     str = Query(min_length=1, max_length=300),
    limit: int = Query(default=20, ge=1, le=100),
    skip:  int = Query(default=0, ge=0),
    doc_type: str | None = Query(default=None, description="entity | authority | annotation"),
    db:    Session      = Depends(get_db),
    _:     models.User  = Depends(get_current_user),
):
    """
    Full-text search across entities, authority records, and annotations.
    Returns ranked results with navigation hrefs.
    """
    fts_expr = _fts_query(q)

    type_filter = ""
    params: dict = {"expr": fts_expr}
    if doc_type:
        type_filter = "AND doc_type = :doc_type"
        params["doc_type"] = doc_type

    count_sql = text(f"""
        SELECT COUNT(*)
        FROM search_index
        WHERE search_index MATCH :expr {type_filter}
    """)
    rows_sql = text(f"""
        SELECT doc_type, doc_id, title, body, href, rank
        FROM search_index
        WHERE search_index MATCH :expr {type_filter}
        ORDER BY rank
        LIMIT :limit OFFSET :skip
    """)
    params["limit"] = limit
    params["skip"]  = skip

    try:
        total = db.execute(count_sql, params).fetchone()[0]
        rows  = db.execute(rows_sql,  params).fetchall()
    except Exception as exc:
        # FTS5 parse error (rare after sanitisation)
        logger.warning("FTS5 query failed for %r: %s", q, exc)
        raise HTTPException(status_code=422, detail=f"Invalid search query: {exc}")

    items = [
        {
            "doc_type": r[0],
            "doc_id":   r[1],
            "title":    r[2],
            "snippet":  (r[3] or "")[:120],
            "href":     r[4],
        }
        for r in rows
    ]

    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.post("/rebuild", status_code=200)
def rebuild_index(
    db: Session    = Depends(get_db),
    _:  models.User = Depends(require_role("super_admin", "admin")),
):
    """Force a full rebuild of the FTS5 search index. Admin+ only."""
    count = _rebuild(db)
    return {"indexed": count}
