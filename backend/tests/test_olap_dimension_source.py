"""
Tests for OLAP dimension `source` aliasing (issue #102).

Several science-domain dimensions don't live under their own name: the value is
stored in a differently-named physical column or attributes_json key. Examples
(confirmed against production):

  - citations   → physical column ``enrichment_citation_count``
  - keywords    → physical column ``enrichment_concepts``
  - issn        → physical column ``enrichment_issn_l``
  - institution → attributes_json key ``affiliation``

An ``AttributeSchema.source`` declares where the value really is, and the OLAP
projection resolves the dimension from it — physical column OR JSON key — with no
data duplication and no backfill.
"""
import pandas as pd

import backend.olap as olap_mod
from backend.olap import DuckDBOLAPEngine
from backend.schema_registry import DomainSchema, AttributeSchema


def _domain() -> DomainSchema:
    return DomainSchema(
        id="science",
        name="Science",
        description="test",
        primary_entity="Publication",
        attributes=[
            AttributeSchema(name="citations", type="integer", label="Citations",
                            is_core=True, source="enrichment_citation_count"),
            AttributeSchema(name="institution", type="string", label="Institution",
                            is_core=False, source="affiliation"),
            AttributeSchema(name="journal", type="string", label="Journal", is_core=True),
        ],
    )


def _patch(monkeypatch, df: pd.DataFrame):
    monkeypatch.setattr(olap_mod.registry, "get_domain", lambda _: _domain())
    monkeypatch.setattr(pd, "read_sql_table", lambda *a, **kw: df.copy())


def test_source_resolves_from_physical_column(monkeypatch):
    """A dimension whose source is a physical column (citations →
    enrichment_citation_count) must group by that column's values."""
    df = pd.DataFrame({
        "enrichment_citation_count": [10, 10, 42],
        "attributes_json": ["{}", "{}", "{}"],
        "normalized_json": [None, None, None],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["citations"])

    counts = {r["values"]["citations"]: r["count"] for r in result["rows"]}
    assert counts == {"10": 2, "42": 1}


def test_source_resolves_from_json_key(monkeypatch):
    """A dimension whose source is a differently-named attributes_json key
    (institution → affiliation) must group by that key's values."""
    df = pd.DataFrame({
        "enrichment_citation_count": [1, 2],
        "attributes_json": [
            '{"affiliation": "MIT, US"}',
            '{"affiliation": "MIT, US"}',
        ],
        "normalized_json": [None, None],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["institution"])

    assert result["rows"][0]["values"]["institution"] == "MIT, US"
    assert result["rows"][0]["count"] == 2


def test_source_dimension_reports_distinct_count(monkeypatch):
    """get_dimensions must count distinct values via the source too."""
    df = pd.DataFrame({
        "enrichment_citation_count": [10, 10, 42],
        "attributes_json": ["{}", "{}", "{}"],
        "normalized_json": [None, None, None],
    })
    _patch(monkeypatch, df)

    dims = {d["name"]: d["distinct_count"] for d in DuckDBOLAPEngine().get_dimensions("science")}

    assert dims["citations"] == 2  # 10, 42


def test_native_key_still_wins_when_present(monkeypatch):
    """A dimension without a source resolves from its own name as before."""
    df = pd.DataFrame({
        "enrichment_citation_count": [1],
        "attributes_json": ['{"journal": "Nature"}'],
        "normalized_json": [None],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["journal"])

    assert result["rows"][0]["values"]["journal"] == "Nature"
