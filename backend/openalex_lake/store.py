"""DuckDB persistence for the OpenAlex lake.

Idempotent: re-ingesting a work replaces its rows (INSERT OR REPLACE on the
declared primary keys), so incremental refreshes and retries are safe. Table and
column names are validated against the schema — no identifier comes from network
data — to keep the SQL injection surface at zero.
"""
from __future__ import annotations

import os
import re
from typing import Optional

import duckdb

from backend.openalex_lake.schema import DDL_STATEMENTS, PRIMARY_KEYS
from backend.openalex_lake.views import create_analysis_views

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_KNOWN_TABLES = frozenset(PRIMARY_KEYS.keys())


def _safe_identifier(name: str) -> str:
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return name


class LakeStore:
    """Thin wrapper over a persistent (or in-memory) DuckDB lake."""

    def __init__(self, db_path: str = ":memory:"):
        if db_path != ":memory:":
            parent = os.path.dirname(os.path.abspath(db_path))
            os.makedirs(parent, exist_ok=True)
        self.con = duckdb.connect(db_path)
        self._create_schema()

    def _create_schema(self) -> None:
        for ddl in DDL_STATEMENTS:
            self.con.execute(ddl)
        # Views are cheap and always valid over the (possibly empty) facts.
        create_analysis_views(self.con)

    def insert_rows(self, table: str, rows: list[dict]) -> int:
        """Idempotently upsert rows into `table`. Returns rows written."""
        if not rows:
            return 0
        if table not in _KNOWN_TABLES:
            raise ValueError(f"unknown table: {table!r}")
        columns = [_safe_identifier(c) for c in rows[0].keys()]
        col_sql = ", ".join(columns)
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT OR REPLACE INTO {table} ({col_sql}) VALUES ({placeholders})"
        params = [[row.get(c) for c in columns] for row in rows]
        self.con.executemany(sql, params)
        return len(params)

    def ingest_work_rows(self, rows_by_table: dict[str, list[dict]]) -> int:
        """Persist the output of transform_work; returns total rows written."""
        written = 0
        for table, rows in rows_by_table.items():
            written += self.insert_rows(table, rows)
        return written

    # ---- incremental-refresh watermark -----------------------------------
    def get_watermark(self, key: str) -> Optional[str]:
        res = self.con.execute("SELECT value FROM _meta WHERE key = ?", [key]).fetchone()
        return res[0] if res else None

    def set_watermark(self, key: str, value: str) -> None:
        self.con.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES (?, ?)", [key, value]
        )

    def count(self, table: str) -> int:
        table = _safe_identifier(table)
        if table not in _KNOWN_TABLES:
            raise ValueError(f"unknown table: {table!r}")
        return self.con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def summary(self) -> dict[str, int]:
        """Row counts per fact/dim table — a quick post-ingest sanity view."""
        return {table: self.count(table) for table in sorted(_KNOWN_TABLES)}

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> "LakeStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
