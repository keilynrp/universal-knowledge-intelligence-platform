"""Read-only exploration of the lake's analysis views (Lake Explorer backend).

Powers the admin UI: list the whitelisted views (grouped by analytical axis)
and run bounded, parameterized queries against one of them. Security posture:

- The view name must be a key of ANALYSIS_VIEWS — nothing user-supplied ever
  reaches SQL as an identifier except after that whitelist check.
- `order_by` is validated against the view's actual columns (introspected via
  DESCRIBE on the read-only connection).
- Filters are fixed, known columns bound as parameters — no raw predicates.
- Row caps keep responses dashboard-sized.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import duckdb

from backend.openalex_lake.store import LakeStore
from backend.openalex_lake.views import ANALYSIS_VIEWS, VIEWS_BY_AXIS

MAX_LIMIT = 500
DEFAULT_LIMIT = 50

# Filterable columns: filter name -> (column, SQL operator). A filter is applied
# only when the target view actually has that column, so every filter is safe to
# send to every view (it just no-ops elsewhere).
_EQ_FILTERS = ("issn_l", "field")
_YEAR_COLUMNS = ("publication_year", "cited_year")  # first one present wins


class UnknownViewError(ValueError):
    """Requested view is not one of the whitelisted analysis views."""


class BadOrderByError(ValueError):
    """Requested order_by is not a column of the view."""


def list_views() -> list[dict]:
    """The explorer's catalog: views grouped by analytical axis."""
    return [
        {"axis": axis, "views": list(views)}
        for axis, views in VIEWS_BY_AXIS.items()
    ]


def _view_columns(con, view: str) -> list[str]:
    # `view` is whitelist-checked by the caller; DESCRIBE takes no parameters.
    return [row[0] for row in con.execute(f"DESCRIBE {view}").fetchall()]


def query_view(
    db_path: str,
    view: str,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    order_by: Optional[str] = None,
    descending: bool = True,
    issn_l: Optional[str] = None,
    field: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
) -> dict:
    """Run a bounded, parameterized read of one whitelisted analysis view.

    Returns {view, columns, rows, total, limit, offset}. `total` is the count
    under the same filters so the UI can paginate.
    """
    if view not in ANALYSIS_VIEWS:
        raise UnknownViewError(view)
    limit = max(1, min(int(limit), MAX_LIMIT))
    offset = max(0, int(offset))

    with LakeStore(db_path, read_only=True) as store:
        con = store.con
        columns = _view_columns(con, view)

        clauses: list[str] = []
        params: list[Any] = []
        for name, value in (("issn_l", issn_l), ("field", field)):
            if value is not None and name in columns:
                clauses.append(f"{name} = ?")
                params.append(value)
        year_col = next((c for c in _YEAR_COLUMNS if c in columns), None)
        if year_col:
            if year_min is not None:
                clauses.append(f"{year_col} >= ?")
                params.append(int(year_min))
            if year_max is not None:
                clauses.append(f"{year_col} <= ?")
                params.append(int(year_max))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        if order_by is not None and order_by not in columns:
            raise BadOrderByError(order_by)
        order = (
            f" ORDER BY {order_by} {'DESC' if descending else 'ASC'}"
            if order_by
            else ""
        )

        total = con.execute(f"SELECT count(*) FROM {view}{where}", params).fetchone()[0]
        rows = con.execute(
            f"SELECT * FROM {view}{where}{order} LIMIT {limit} OFFSET {offset}",
            params,
        ).fetchall()

    return {
        "view": view,
        "columns": columns,
        "rows": [list(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def resolve_query(db_path: str, view: str, **kwargs) -> dict:
    """query_view with the same friendly non-error states as resolve_status."""
    if not os.path.exists(db_path):
        return {"lake": "not_initialized", "db_path": db_path}
    try:
        return query_view(db_path, view, **kwargs)
    except duckdb.OperationalError:
        # Same lock semantics as status: a pull holds the single-writer lock.
        return {"lake": "locked", "db_path": db_path,
                "hint": "a pull is currently running; re-check once it finishes"}
