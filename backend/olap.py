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


def _explode_items(value, item_key=None, separator=", ") -> list:
    """Normalize a multi-valued cell into a clean list of item strings.

    Accepts a delimited string (split on ``separator``), a list of strings, or a
    list of dicts (pull ``item_key`` from each). Empty/whitespace items are
    dropped so they never become a spurious facet bucket.
    """
    if value is None:
        return []
    # A scalar NaN is a float; guard before treating value as a container.
    if isinstance(value, float):
        return []

    raw_items: list
    if isinstance(value, str):
        raw_items = value.split(separator) if separator else [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raw_items = [value]

    items: list[str] = []
    for el in raw_items:
        if item_key and isinstance(el, dict):
            el = el.get(item_key)
        if el is None:
            continue
        text = el.strip() if isinstance(el, str) else str(el)
        if text:
            items.append(text)
    return items


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

    An attribute may declare ``source`` when its value lives under a different
    name — either another physical column (``citations`` →
    ``enrichment_citation_count``) or a differently-named JSON key
    (``institution`` → ``affiliation``). The dimension is then resolved from that
    source, so no data has to be duplicated or backfilled.
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
            src = getattr(attr, "source", None) or attr.name
            # Resolve the raw per-row value from the source (physical column or
            # the merged JSON stores under the source key).
            if src in df.columns:
                raw_values = list(df[src])
            else:
                raw_values = [
                    a.get(src) if a.get(src) is not None else n.get(src)
                    for n, a in zip(norm_dicts, attr_dicts)
                ]

            # Multi-valued dimension → materialize a list of items per row so the
            # cube can explode (UNNEST) it into per-item facets.
            if getattr(attr, "multi_valued", False):
                item_key = getattr(attr, "item_key", None)
                sep = getattr(attr, "separator", ", ")
                df[attr.name] = pd.Series(
                    [_explode_items(v, item_key, sep) for v in raw_values],
                    index=df.index, dtype=object,
                )
            else:
                df[attr.name] = raw_values

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
                    if getattr(attr, "multi_valued", False):
                        # Explode the list column so each item is counted.
                        query = (
                            f"SELECT label, COUNT(*) AS value FROM ("
                            f"SELECT UNNEST({col}) AS label FROM df"
                            f") WHERE label IS NOT NULL "
                            f"GROUP BY label ORDER BY value DESC LIMIT 8"
                        )
                    else:
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
            if attr.name not in df.columns or len(df) == 0:
                distinct = 0
            elif getattr(attr, "multi_valued", False):
                # Count distinct *items* across the per-row lists.
                items: set = set()
                for lst in df[attr.name]:
                    if isinstance(lst, (list, tuple)):
                        items.update(lst)
                distinct = len(items)
            else:
                distinct = int(df[attr.name].nunique())
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

        Dimensionality & performance
        ----------------------------
        The cube is capped at **2** group-by dimensions on purpose. The limit is
        driven by result quality, not raw CPU: on this in-memory DuckDB engine a
        GROUP BY over 2-3 columns is trivial. What degrades is:

        * **Sparsity / truncation** — the result grid can reach C1×C2×… cells but
          is cut at ``LIMIT 200``. Crossing high-cardinality dimensions
          (``keywords``, ``institution``, ``journal``, ``authors``) yields a huge,
          mostly count=1 grid whose long tail is silently dropped, making the
          percentages misleading.
        * **Readability** — beyond 2 dimensions a pivot table stops being
          human-interpretable.
        * **Multi-valued explosion** — ``multi_valued`` dims (keywords,
          institution) already multiply rows via UNNEST, so crossing *two* of them
          is rejected outright (ambiguous and costly).

        Guidance: cross **low-cardinality** dims (``year``, ``work_type``,
        ``validation_status``, ``paradigm``); use high-cardinality ones as the
        single primary dimension or as a ``filters`` drill-down. If deeper N-way
        slicing is ever needed, do it in a dedicated analytical/materialized query,
        not this generic cube.

        NB: the real scaling bottleneck is the full ``read_sql_table`` + per-row
        JSON parse on every call (O(rows), independent of dimension count) — that
        is what to optimize (cache/pushdown) before ever raising this cap.
        """
        if not 1 <= len(group_by) <= 2:
            raise ValueError("group_by must specify 1 or 2 dimensions")

        domain = registry.get_domain(domain_id)
        if not domain:
            raise ValueError(f"Domain '{domain_id}' not found")

        attr_by_name = {a.name: a for a in domain.attributes}
        attr_names = set(attr_by_name)
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

        def _is_multi(name: str) -> bool:
            attr = attr_by_name.get(name)
            return bool(attr and getattr(attr, "multi_valued", False))

        # Exploding two multi-valued dimensions at once is ambiguous (it would zip
        # per-row lists, not cross them), so reject it with a clear error.
        if sum(_is_multi(d) for d in group_by) > 1:
            raise ValueError("Cannot group by two multi-valued dimensions at once")

        df = self._load_domain_df(domain)

        # Apply equality filters (field must exist in schema and DataFrame).
        if filters:
            for field, value in (filters or {}).items():
                if not _is_safe_identifier(field):
                    continue
                if field not in df.columns or value is None:
                    continue
                if _is_multi(field):
                    # Drill-down into one item of a multi-valued dimension.
                    target = str(value)
                    df = df[df[field].apply(
                        lambda lst: isinstance(lst, (list, tuple)) and target in [str(x) for x in lst]
                    )]
                else:
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

        # Explode any multi-valued dimension (list column) into one row per item
        # via a sub-select; scalar dimensions pass through unchanged.
        inner_cols = ", ".join(
            f'UNNEST("{d}") AS "{d}"' if _is_multi(d) else f'"{d}"'
            for d in group_by
        )
        select_cols = ", ".join([f'CAST("{d}" AS VARCHAR) AS "{d}"' for d in group_by])
        groupby_clause = ", ".join([f'"{d}"' for d in group_by])
        sql = (
            f"SELECT {select_cols}, COUNT(*) AS count "
            f"FROM (SELECT {inner_cols} FROM df) "
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
