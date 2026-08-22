"""
Tests for backend/olap.py — SQL injection prevention via identifier
whitelisting and quoted identifiers in DuckDB queries.
"""
import pytest
import pandas as pd
import duckdb

from backend.olap import _is_safe_identifier, DuckDBOLAPEngine

pytestmark = pytest.mark.security


# ── Unit: identifier validation ──────────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "entity_name",
    "brand_capitalized",
    "status",
    "enrichment_status",
    "_private",
    "field123",
    "A",
])
def test_safe_identifiers_pass(name):
    assert _is_safe_identifier(name) is True


@pytest.mark.parametrize("name", [
    "entity_name; DROP TABLE raw_entities--",
    "1_starts_with_number",
    "has space",
    "has-dash",
    "has.dot",
    "'; DROP TABLE--",
    "",
    "field`injection`",
    "field\"injection\"",
])
def test_unsafe_identifiers_rejected(name):
    assert _is_safe_identifier(name) is False


# ── Unit: DuckDB quoted identifier prevents injection ────────────────────────

def test_quoted_identifier_prevents_column_injection():
    """
    Verify that quoting an attribute name in a DuckDB query causes an error
    (column not found) when a malicious name is used, rather than executing SQL.
    """
    df = pd.DataFrame({"safe_column": ["a", "b", "c"], "value": [1, 2, 3]})
    con = duckdb.connect()
    con.register("df", df)

    malicious_name = "safe_column; SELECT * FROM df--"

    # Without quoting, this could cause SQL injection.
    # With quoting, DuckDB treats it as a column name — which doesn't exist.
    quoted = f'"{malicious_name}"'
    with pytest.raises(Exception):
        con.execute(f"SELECT {quoted} FROM df").df()


def test_valid_column_query_succeeds():
    """A legitimate attribute name produces correct results."""
    df = pd.DataFrame({"status": ["active", "inactive", "active"]})
    con = duckdb.connect()
    con.register("df", df)

    col = '"status"'
    result = con.execute(
        f"SELECT CAST({col} AS VARCHAR) AS label, COUNT(*) AS value "
        f"FROM df WHERE {col} IS NOT NULL GROUP BY {col} ORDER BY value DESC"
    ).df()

    assert len(result) == 2
    assert result.iloc[0]["label"] == "active"
    assert result.iloc[0]["value"] == 2


# ── Integration: generate_cube_metrics skips unknown/unsafe columns ──────────

def test_generate_cube_metrics_skips_columns_not_in_df(monkeypatch):
    """
    Columns in the domain schema that don't exist in the DataFrame should be
    silently skipped — no KeyError, no SQL injection.
    """
    from backend.schema_registry import DomainSchema, AttributeSchema

    fake_domain = DomainSchema(
        id="test",
        name="Test",
        description="test",
        primary_entity="Entity",
        attributes=[
            AttributeSchema(name="status", type="string", label="Status", is_core=True),
            AttributeSchema(name="nonexistent_col", type="string", label="Ghost", is_core=True),
            AttributeSchema(
                name="evil'; DROP TABLE df--",
                type="string",
                label="Evil",
                is_core=True,
            ),
        ],
    )

    import backend.olap as olap_mod
    import pandas as pd
    from sqlalchemy import text

    # Patch registry to return our fake domain
    monkeypatch.setattr(olap_mod.registry, "get_domain", lambda _: fake_domain)

    # Patch pd.read_sql_table to return a controlled DataFrame
    controlled_df = pd.DataFrame({
        "status": ["active", "inactive", "active"],
        "normalized_json": [None, None, None],
    })
    monkeypatch.setattr(pd, "read_sql_table", lambda *a, **kw: controlled_df)

    # Should not raise
    metrics = olap_mod.DuckDBOLAPEngine.generate_cube_metrics("test")

    assert metrics["total_records"] == 3
    # "status" is valid and should appear
    assert "Status" in metrics["distributions"]
    # "nonexistent_col" and "evil" must NOT appear
    assert "Ghost" not in metrics["distributions"]
    assert "Evil" not in metrics["distributions"]
