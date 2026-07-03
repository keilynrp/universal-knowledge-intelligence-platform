"""
Regression tests for backend/olap.py — the OLAP cube must project domain
attributes from ``attributes_json`` (the authoritative store written by the
API/BibTeX importers and the enrichment worker), not only from
``normalized_json`` (which is populated solely by the generic CSV wizard for
unmapped columns).

Before the fix, entities imported via OpenAlex/PubMed (data in
``attributes_json``, ``normalized_json`` NULL) produced dimensions with
``distinct_count == 0`` and empty cube queries — the explorer looked empty even
though the data was fully ingested and enriched. Two bugs combined:

  1. projection read ``normalized_json`` instead of ``attributes_json``;
  2. projection skipped ``is_core`` attributes, but several domains (science)
     store "core" fields like journal/year inside ``attributes_json`` rather
     than as physical RawEntity columns.
"""
import pandas as pd
import pytest

import backend.olap as olap_mod
from backend.olap import DuckDBOLAPEngine
from backend.schema_registry import DomainSchema, AttributeSchema


def _fake_domain() -> DomainSchema:
    return DomainSchema(
        id="science",
        name="Science",
        description="test",
        primary_entity="Publication",
        attributes=[
            # is_core=True on purpose: proves the is_core gate no longer hides
            # attributes that actually live in attributes_json.
            AttributeSchema(name="journal", type="string", label="Journal", is_core=True),
            AttributeSchema(name="year", type="integer", label="Year", is_core=True),
            AttributeSchema(name="keywords", type="string", label="Keywords", is_core=False),
        ],
    )


def _patch(monkeypatch, df: pd.DataFrame):
    monkeypatch.setattr(olap_mod.registry, "get_domain", lambda _: _fake_domain())
    monkeypatch.setattr(pd, "read_sql_table", lambda *a, **kw: df.copy())


def test_dimensions_projected_from_attributes_json(monkeypatch):
    """Attributes stored in attributes_json (normalized_json NULL) must yield
    non-zero distinct counts — even when marked is_core."""
    df = pd.DataFrame({
        "attributes_json": [
            '{"journal": "Nature", "year": 2020, "keywords": "astronomy"}',
            '{"journal": "Cell", "year": 2021, "keywords": "biology"}',
            '{"journal": "Nature", "year": 2020, "keywords": "astronomy"}',
        ],
        "normalized_json": [None, None, None],
    })
    _patch(monkeypatch, df)

    dims = {d["name"]: d["distinct_count"] for d in DuckDBOLAPEngine().get_dimensions("science")}

    assert dims["journal"] == 2   # Nature, Cell  (was 0 before the fix)
    assert dims["year"] == 2      # 2020, 2021    (is_core, was 0 before the fix)
    assert dims["keywords"] == 2


def test_query_cube_groups_by_attributes_json_dimension(monkeypatch):
    """A GROUP BY over an attributes_json-backed dimension returns real rows."""
    df = pd.DataFrame({
        "attributes_json": [
            '{"journal": "Nature"}',
            '{"journal": "Cell"}',
            '{"journal": "Nature"}',
        ],
        "normalized_json": [None, None, None],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["journal"])

    assert result["total"] == 3
    counts = {r["values"]["journal"]: r["count"] for r in result["rows"]}
    assert counts == {"Nature": 2, "Cell": 1}


def test_normalized_json_still_used_as_fallback(monkeypatch):
    """Legacy CSV-imported data (only normalized_json populated) still works."""
    df = pd.DataFrame({
        "attributes_json": ["{}", "{}"],
        "normalized_json": [
            '{"keywords": "legacy-a"}',
            '{"keywords": "legacy-b"}',
        ],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["keywords"])

    assert result["total"] == 2
    counts = {r["values"]["keywords"]: r["count"] for r in result["rows"]}
    assert counts == {"legacy-a": 1, "legacy-b": 1}


def test_attributes_json_wins_over_normalized_json(monkeypatch):
    """When both stores hold the same key, attributes_json is authoritative."""
    df = pd.DataFrame({
        "attributes_json": ['{"journal": "Nature"}'],
        "normalized_json": ['{"journal": "STALE"}'],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["journal"])

    assert result["rows"][0]["values"]["journal"] == "Nature"
