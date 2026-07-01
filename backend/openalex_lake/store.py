"""DuckDB persistence for the OpenAlex lake.

Idempotent: re-ingesting a work replaces its rows (INSERT OR REPLACE on the
declared primary keys), so incremental refreshes and retries are safe. Table and
column names are validated against the schema — no identifier comes from network
data — to keep the SQL injection surface at zero.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from typing import Optional

import duckdb
import pandas as pd

from backend.openalex_lake.schema import DDL_STATEMENTS, PRIMARY_KEYS
from backend.openalex_lake.views import create_analysis_views

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_KNOWN_TABLES = frozenset(PRIMARY_KEYS.keys())


def _safe_identifier(name: str) -> str:
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(f"unsafe identifier: {name!r}")
    return name


def dedup_by_pk(table: str, rows: list[dict]) -> list[dict]:
    """Keep one row per primary key (last write wins).

    Required before a bulk `INSERT OR REPLACE ... SELECT`: DuckDB rejects a
    single INSERT whose source has two rows with the same PK. Dimension rows
    (author/institution/topic/source) repeat heavily across works, so this also
    shrinks the write a lot.
    """
    pk = PRIMARY_KEYS.get(table)
    if not pk:
        return rows
    seen: dict[tuple, dict] = {}
    for row in rows:
        seen[tuple(row.get(c) for c in pk)] = row
    return list(seen.values())


class LakeStore:
    """Thin wrapper over a persistent (or in-memory) DuckDB lake."""

    def __init__(self, db_path: str = ":memory:", read_only: bool = False):
        if read_only:
            # For status/queries while a scheduled writer may hold the file.
            self.con = duckdb.connect(db_path, read_only=True)
            return
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
        """Idempotently bulk-upsert rows into `table`. Returns rows written.

        Uses a vectorized `INSERT OR REPLACE ... SELECT * FROM <df>` (orders of
        magnitude faster than a row-by-row executemany). Input is deduped by PK
        first so the single INSERT never has conflicting keys within itself.
        """
        if not rows:
            return 0
        if table not in _KNOWN_TABLES:
            raise ValueError(f"unknown table: {table!r}")
        rows = dedup_by_pk(table, rows)
        column_names = list(rows[0].keys())
        columns = [_safe_identifier(c) for c in column_names]
        col_sql = ", ".join(columns)
        df = pd.DataFrame(rows, columns=column_names)  # noqa: F841 - used via DuckDB scan
        self.con.register("_lake_ingest", df)
        try:
            self.con.execute(
                f"INSERT OR REPLACE INTO {table} ({col_sql}) SELECT {col_sql} FROM _lake_ingest"
            )
        finally:
            self.con.unregister("_lake_ingest")
        return len(rows)

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


class RowBuffer:
    """Accumulate transform_work output across many works and flush in bulk.

    Per-work inserts dominate wall time on a large pull. Buffering turns that
    into one vectorized `INSERT OR REPLACE ... SELECT` per table per flush;
    insert_rows dedups the accumulated batch by primary key, so heavily-repeated
    dimension rows (author/topic/institution/source) collapse to one write each.
    """

    def __init__(self, store: LakeStore, flush_every: int = 1000):
        self.store = store
        self.flush_every = flush_every
        self._buffers: dict[str, list[dict]] = defaultdict(list)
        self._pending = 0

    def add_work_rows(self, rows_by_table: dict[str, list[dict]]) -> None:
        for table, rows in rows_by_table.items():
            if rows:
                self._buffers[table].extend(rows)
        self._pending += 1
        if self._pending >= self.flush_every:
            self.flush()

    def flush(self) -> None:
        for table, rows in self._buffers.items():
            if rows:
                self.store.insert_rows(table, rows)  # dedups by PK internally
        self._buffers.clear()
        self._pending = 0
