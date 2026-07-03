"""Multi-valued OLAP dimensions — per-item faceting (issue #104).

`keywords` (a comma-joined concepts string) and `institution` (structured
``canonical_affiliations`` list, or a delimited affiliation string) hold several
items per work. Grouping on the raw value makes each row almost unique. A
``multi_valued`` dimension is exploded so a work with N items counts once in each
of its N item buckets — turning the dimension into a usable facet.
"""
import pytest
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
            # keywords: delimited-string source, split on ", "
            AttributeSchema(name="keywords", type="string", label="Keywords",
                            source="enrichment_concepts", multi_valued=True, separator=", "),
            # institution: list-of-dicts source, pull "name" from each item
            AttributeSchema(name="institution", type="string", label="Institution",
                            source="canonical_affiliations", multi_valued=True, item_key="name"),
            AttributeSchema(name="year", type="integer", label="Year", is_core=True),
        ],
    )


def _patch(monkeypatch, df: pd.DataFrame):
    monkeypatch.setattr(olap_mod.registry, "get_domain", lambda _: _domain())
    monkeypatch.setattr(pd, "read_sql_table", lambda *a, **kw: df.copy())


def test_keywords_string_source_explodes(monkeypatch):
    """A work with 'A, B' contributes one count to A and one to B."""
    df = pd.DataFrame({
        "enrichment_concepts": ["Machine Learning, Physics", "Machine Learning", None],
        "attributes_json": ["{}", "{}", "{}"],
        "normalized_json": [None, None, None],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["keywords"])

    counts = {r["values"]["keywords"]: r["count"] for r in result["rows"]}
    assert counts == {"Machine Learning": 2, "Physics": 1}


def test_institution_list_of_dicts_explodes(monkeypatch):
    """institution pulls `name` from each canonical_affiliations item."""
    df = pd.DataFrame({
        "enrichment_concepts": [None, None],
        "attributes_json": [
            '{"canonical_affiliations": [{"name": "MIT", "ror": "r1"}, {"name": "Stanford"}]}',
            '{"canonical_affiliations": [{"name": "MIT", "ror": "r1"}]}',
        ],
        "normalized_json": [None, None],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["institution"])

    counts = {r["values"]["institution"]: r["count"] for r in result["rows"]}
    assert counts == {"MIT": 2, "Stanford": 1}


def test_multivalued_distinct_count_is_per_item(monkeypatch):
    """get_dimensions counts distinct *items*, not distinct raw strings."""
    df = pd.DataFrame({
        "enrichment_concepts": ["A, B", "B, C", "A"],
        "attributes_json": ["{}", "{}", "{}"],
        "normalized_json": [None, None, None],
    })
    _patch(monkeypatch, df)

    dims = {d["name"]: d["distinct_count"] for d in DuckDBOLAPEngine().get_dimensions("science")}

    assert dims["keywords"] == 3  # A, B, C — not 3 distinct raw strings by luck


def test_crosstab_multivalued_with_normal_dim(monkeypatch):
    """keyword × year cross-tab explodes the keyword and keeps year."""
    df = pd.DataFrame({
        "enrichment_concepts": ["A, B", "A"],
        "year": [2020, 2020],
        "attributes_json": ["{}", "{}"],
        "normalized_json": [None, None],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["keywords", "year"])

    counts = {(r["values"]["keywords"], r["values"]["year"]): r["count"] for r in result["rows"]}
    assert counts == {("A", "2020"): 2, ("B", "2020"): 1}


def test_two_multivalued_dims_rejected(monkeypatch):
    """Crossing two exploded dimensions is ambiguous — reject clearly."""
    df = pd.DataFrame({
        "enrichment_concepts": ["A, B"],
        "attributes_json": ['{"canonical_affiliations": [{"name": "MIT"}]}'],
        "normalized_json": [None],
    })
    _patch(monkeypatch, df)

    with pytest.raises(ValueError):
        DuckDBOLAPEngine().query_cube("science", ["keywords", "institution"])


def test_multivalued_ignores_empty_and_whitespace(monkeypatch):
    """Empty items, whitespace and missing sources contribute nothing."""
    df = pd.DataFrame({
        "enrichment_concepts": ["A, , B ", "", None],
        "attributes_json": ["{}", "{}", "{}"],
        "normalized_json": [None, None, None],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["keywords"])

    counts = {r["values"]["keywords"]: r["count"] for r in result["rows"]}
    assert counts == {"A": 1, "B": 1}


def test_drilldown_filter_into_multivalued_item(monkeypatch):
    """Filtering by one keyword item keeps works that contain it (drill-down)."""
    df = pd.DataFrame({
        "enrichment_concepts": ["A, B", "A", "B"],
        "year": [2020, 2021, 2022],
        "attributes_json": ["{}", "{}", "{}"],
        "normalized_json": [None, None, None],
    })
    _patch(monkeypatch, df)

    result = DuckDBOLAPEngine().query_cube("science", ["year"], filters={"keywords": "A"})

    years = {r["values"]["year"]: r["count"] for r in result["rows"]}
    assert years == {"2020": 1, "2021": 1}  # the "B"-only row (2022) excluded


# ── Real science.yaml wiring (config lock) ───────────────────────────────────


def test_real_science_domain_marks_multivalued_dims():
    """Guard the science.yaml wiring so the faceting config can't silently break."""
    from backend.schema_registry import registry

    attrs = {a.name: a for a in registry.get_domain("science").attributes}
    assert attrs["keywords"].multi_valued is True
    assert attrs["keywords"].source == "enrichment_concepts"
    assert attrs["institution"].multi_valued is True
    assert attrs["institution"].source == "canonical_affiliations"
    assert attrs["institution"].item_key == "name"
