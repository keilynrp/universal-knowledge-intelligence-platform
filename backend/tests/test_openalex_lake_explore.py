"""Tests for the Lake Explorer query layer (whitelisted views, bounded reads)."""
import pytest

from backend.openalex_lake.explore import (
    BadOrderByError,
    UnknownViewError,
    list_views,
    query_view,
    resolve_query,
)
from backend.openalex_lake.store import LakeStore
from backend.openalex_lake.transform import transform_work
from backend.openalex_lake.views import ANALYSIS_VIEWS


def _work(work_id, year, cited, *, issn="0028-0836", field="Physics and Astronomy", authors=()):
    return {
        "id": f"https://openalex.org/{work_id}",
        "publication_year": year,
        "cited_by_count": cited,
        "primary_location": {"source": {"id": "https://openalex.org/S1", "issn_l": issn}},
        "primary_topic": {
            "id": "https://openalex.org/T1", "display_name": "Topic",
            "field": {"id": "https://openalex.org/fields/31", "display_name": field},
        },
        "topics": [{
            "id": "https://openalex.org/T1", "display_name": "Topic", "score": 0.9,
            "field": {"id": "https://openalex.org/fields/31", "display_name": field},
        }],
        "counts_by_year": [{"year": year + 1, "cited_by_count": cited}],
        "authorships": [
            {"author": {"id": f"https://openalex.org/{a}", "display_name": a},
             "institutions": [{"id": "https://openalex.org/I1"}]}
            for a in authors
        ],
    }


@pytest.fixture()
def seeded_db(tmp_path):
    db = str(tmp_path / "lake.duckdb")
    with LakeStore(db) as store:
        store.ingest_work_rows(transform_work(_work("W1", 2015, 100, authors=("A1", "A2"))))
        store.ingest_work_rows(transform_work(_work("W2", 2020, 50)))
        store.ingest_work_rows(transform_work(_work("W3", 2020, 10, issn="1111-1111", field="Medicine")))
    return db


def test_list_views_covers_every_whitelisted_view():
    catalog = list_views()
    listed = {v for entry in catalog for v in entry["views"]}
    assert listed == set(ANALYSIS_VIEWS.keys())
    assert {e["axis"] for e in catalog} == {
        "journal_scientometrics", "collaboration_networks",
        "topic_trends", "coverage_cross_source",
    }


def test_query_view_rejects_unknown_view(seeded_db):
    with pytest.raises(UnknownViewError):
        query_view(seeded_db, "fact_works")  # a real table, but NOT a whitelisted view
    with pytest.raises(UnknownViewError):
        query_view(seeded_db, "v_journal_yearly; DROP TABLE fact_works")


def test_query_view_rejects_bad_order_by(seeded_db):
    with pytest.raises(BadOrderByError):
        query_view(seeded_db, "v_journal_yearly", order_by="nonexistent")


def test_query_view_orders_filters_and_paginates(seeded_db):
    out = query_view(seeded_db, "v_journal_yearly", order_by="citations", descending=True)
    assert out["columns"][0] == "issn_l"
    citations_idx = out["columns"].index("citations")
    values = [r[citations_idx] for r in out["rows"]]
    assert values == sorted(values, reverse=True)

    only_nature = query_view(seeded_db, "v_journal_yearly", issn_l="0028-0836")
    assert only_nature["total"] == 2  # 2015 and 2020 rows
    year_bound = query_view(seeded_db, "v_journal_yearly", issn_l="0028-0836", year_min=2016)
    assert year_bound["total"] == 1

    paged = query_view(seeded_db, "v_journal_yearly", limit=1, offset=1, order_by="publication_year")
    assert len(paged["rows"]) == 1 and paged["total"] == 3


def test_query_view_ignores_filters_the_view_lacks(seeded_db):
    # v_coauthor_pairs has no issn_l/year column: filters must no-op, not error.
    out = query_view(seeded_db, "v_coauthor_pairs", issn_l="0028-0836", year_min=2016)
    assert out["total"] == 1  # the single A1-A2 pair


def test_query_view_caps_limit(seeded_db):
    out = query_view(seeded_db, "v_journal_yearly", limit=99999)
    assert out["limit"] == 500


def test_resolve_query_not_initialized(tmp_path):
    out = resolve_query(str(tmp_path / "nope.duckdb"), "v_journal_yearly")
    assert out["lake"] == "not_initialized"


def test_resolve_query_locked_while_writer_holds_lock(seeded_db):
    writer = LakeStore(seeded_db)
    try:
        out = resolve_query(seeded_db, "v_journal_yearly")
        assert out["lake"] == "locked"
    finally:
        writer.close()
