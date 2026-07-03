import io
import re
import json
import logging

import duckdb
import openpyxl
import pandas as pd

from backend.database import engine
from backend.schema_registry import registry

logger = logging.getLogger(__name__)

# Only allow attribute names that are valid SQL identifiers.
# This is a defense-in-depth check on top of the DataFrame column whitelist.
_SAFE_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _is_safe_identifier(name: str) -> bool:
    """Return True if name is a safe SQL identifier (no injection risk)."""
    return bool(_SAFE_IDENTIFIER_RE.match(name))


def _safe_parse(val) -> dict:
    if pd.isna(val) or not val:
        return {}
    try:
        return json.loads(val)
    except (ValueError, TypeError):
        return {}


def _project_domain_attributes(df: pd.DataFrame, domain) -> pd.DataFrame:
    """Add a column for each domain attribute that lives inside the entity JSON.

    Attributes are read from the merged JSON stores where ``attributes_json``
    (written by the API/BibTeX importers and the enrichment worker) is
    authoritative and ``normalized_json`` (populated only by the generic CSV
    wizard for unmapped columns) is the fallback.

    Attributes that are already physical ``raw_entities`` columns are left
    untouched. The ``is_core`` flag is intentionally *not* used to gate
    projection: some domains (e.g. science) mark fields like ``journal``/``year``
    as core yet still store them in ``attributes_json`` rather than as columns.
    """
    has_attr = "attributes_json" in df.columns
    has_norm = "normalized_json" in df.columns
    if has_attr or has_norm:
        empty = pd.Series([{} for _ in range(len(df))], index=df.index)
        attr_dicts = df["attributes_json"].apply(_safe_parse) if has_attr else empty
        norm_dicts = df["normalized_json"].apply(_safe_parse) if has_norm else empty
        for attr in domain.attributes:
            if attr.name in df.columns:
                continue  # physical column — keep as-is
            if not _is_safe_identifier(attr.name):
                continue  # defense-in-depth: never materialize unsafe names
            df[attr.name] = [
                a.get(attr.name) if a.get(attr.name) is not None else n.get(attr.name)
                for n, a in zip(norm_dicts, attr_dicts)
            ]

    # Extract epistemic paradigm dimension from attributes_json
    if domain.epistemology and "attributes_json" in df.columns:
        attrs_parsed = df["attributes_json"].apply(_safe_parse)
        df["paradigm"] = attrs_parsed.apply(
            lambda a: (a.get("epistemic_profile") or {}).get("dominant", None)
        )

    return df


class DuckDBOLAPEngine:
    """
    In-Memory OLAP Engine leveraging DuckDB to build Data Cubes out of the
    domain-agnostic entities stored in SQLite.
    """

    def _load_domain_df(self, domain) -> pd.DataFrame:
        """Load raw_entities and project domain-specific attributes."""
        df = pd.read_sql_table("raw_entities", engine)
        return _project_domain_attributes(df, domain)

    @staticmethod
    def generate_cube_metrics(domain_id: str) -> dict:
        domain = registry.get_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain '{domain_id}' not found")

        df = pd.read_sql_table("raw_entities", engine)
        df = _project_domain_attributes(df, domain)

        valid_columns: set[str] = set(df.columns)

        metrics: dict = {
            "domain_id": domain.id,
            "domain_name": domain.name,
            "total_records": 0,
            "distributions": {},
            "cube_metrics": {},
        }

        if len(df) == 0:
            return metrics

        con = duckdb.connect()
        con.register("df", df)

        metrics["total_records"] = con.execute("SELECT COUNT(*) FROM df").fetchone()[0]

        skip_fields = {"primary_label", "title", "canonical_id", "doi", "nct_id"}

        for attr in domain.attributes:
            if attr.name in skip_fields:
                continue
            if attr.name not in valid_columns:
                continue
            if not _is_safe_identifier(attr.name):
                logger.warning(f"OLAP: skipping unsafe attribute name '{attr.name}'")
                continue

            if attr.type == "string" or attr.name in df.columns:
                try:
                    col = f'"{attr.name}"'
                    query = (
                        f"SELECT CAST({col} AS VARCHAR) AS label, "
                        f"COUNT(*) AS value "
                        f"FROM df "
                        f"WHERE {col} IS NOT NULL "
                        f"GROUP BY {col} "
                        f"ORDER BY value DESC "
                        f"LIMIT 8"
                    )
                    res_df = con.execute(query).df()

                    if not res_df.empty:
                        res_df["label"] = res_df["label"].replace(
                            {"None": "Unknown", "nan": "Unknown"}
                        )
                        metrics["distributions"][attr.label] = res_df.to_dict(orient="records")
                except Exception as e:
                    logger.debug(f"OLAP: skipping distribution for '{attr.name}': {e}")

        return metrics

    def get_dimensions(self, domain_id: str) -> list:
        """
        Return domain attributes enriched with their distinct value count.
        Used by the OLAP Cube Explorer to populate the dimension selector.
        """
        domain = registry.get_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain '{domain_id}' not found")

        df = self._load_domain_df(domain)
        skip_fields = {"primary_label", "title", "canonical_id", "doi", "nct_id"}

        result = []
        for attr in domain.attributes:
            if attr.name in skip_fields:
                continue
            if not _is_safe_identifier(attr.name):
                continue
            distinct = int(df[attr.name].nunique()) if attr.name in df.columns and len(df) > 0 else 0
            result.append({
                "name": attr.name,
                "label": attr.label,
                "type": attr.type,
                "distinct_count": distinct,
            })

        # Add epistemic paradigm as a virtual dimension
        if domain.epistemology and "paradigm" in df.columns:
            distinct = int(df["paradigm"].dropna().nunique()) if len(df) > 0 else 0
            result.append({
                "name": "paradigm",
                "label": "Epistemic Paradigm",
                "type": "string",
                "distinct_count": distinct,
            })

        return result

    def query_cube(
        self,
        domain_id: str,
        group_by: list,
        filters: dict | None = None,
    ) -> dict:
        """
        Group entities by 1 or 2 dimensions with optional equality filters.
        Returns rows sorted by count descending, capped at 200.
        """
        if not 1 <= len(group_by) <= 2:
            raise ValueError("group_by must specify 1 or 2 dimensions")

        domain = registry.get_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain '{domain_id}' not found")

        attr_names = {a.name for a in domain.attributes}
        # Include virtual dimensions (e.g., paradigm from epistemic classification)
        if domain.epistemology:
            attr_names.add("paradigm")
        valid_columns_schema = set()
        for dim in group_by:
            if not _is_safe_identifier(dim):
                raise ValueError(f"Unsafe dimension name: '{dim}'")
            if dim not in attr_names:
                raise ValueError(f"Dimension '{dim}' is not in domain '{domain_id}'")
            valid_columns_schema.add(dim)

        df = self._load_domain_df(domain)

        # Apply equality filters (field must exist in schema and DataFrame)
        if filters:
            for field, value in (filters or {}).items():
                if not _is_safe_identifier(field):
                    continue
                if field in df.columns and value is not None:
                    df = df[df[field].astype(str) == str(value)]

        empty_response = {
            "domain_id": domain_id,
            "group_by": group_by,
            "filters": filters or {},
            "total": 0,
            "rows": [],
        }
        if len(df) == 0:
            return empty_response

        # Secondary whitelist: dimensions must exist in the real DataFrame
        valid_columns_df = set(df.columns)
        for dim in group_by:
            if dim not in valid_columns_df:
                return empty_response

        con = duckdb.connect()
        con.register("df", df)

        select_cols = ", ".join([f'CAST("{d}" AS VARCHAR) AS "{d}"' for d in group_by])
        groupby_clause = ", ".join([f'"{d}"' for d in group_by])
        sql = (
            f"SELECT {select_cols}, COUNT(*) AS count "
            f"FROM df "
            f"GROUP BY {groupby_clause} "
            f"ORDER BY count DESC "
            f"LIMIT 200"
        )
        result_df = con.execute(sql).df()
        total = int(result_df["count"].sum()) if not result_df.empty else 0

        # NULL grouping values come back as pandas NaN. Coerce to None so the
        # response is JSON-compliant — Starlette's JSONResponse uses
        # allow_nan=False and would raise (HTTP 500) on a leaked NaN.
        rows = [
            {
                "values": {d: (None if pd.isna(row[d]) else row[d]) for d in group_by},
                "count": int(row["count"]),
                "pct": round(row["count"] / total * 100, 1) if total > 0 else 0.0,
            }
            for _, row in result_df.iterrows()
        ]

        return {
            "domain_id": domain_id,
            "group_by": group_by,
            "filters": filters or {},
            "total": total,
            "rows": rows,
        }

    def export_to_excel(self, domain_id: str, dimension: str) -> bytes:
        """
        Export a single-dimension GROUP BY result as an Excel workbook.
        Returns raw bytes suitable for a StreamingResponse.
        """
        if not _is_safe_identifier(dimension):
            raise ValueError(f"Unsafe dimension name: '{dimension}'")

        data = self.query_cube(domain_id, [dimension])
        domain = registry.get_domain(domain_id)
        attr_map = {a.name: a for a in domain.attributes}
        dim_label = attr_map[dimension].label if dimension in attr_map else dimension

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Cube Data"

        # Header row
        ws.append([dim_label, "Count", "% of Total"])
        for row in data["rows"]:
            ws.append([row["values"][dimension], row["count"], row["pct"]])
        ws.append([])
        ws.append(["Total", data["total"], 100.0])

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()


olap_engine = DuckDBOLAPEngine()
