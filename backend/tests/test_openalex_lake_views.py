"""Tests for the OpenAlex lake analysis views (the 4 axes)."""
from backend.openalex_lake.store import LakeStore
from backend.openalex_lake.transform import transform_work
from backend.openalex_lake.views import ANALYSIS_VIEWS, VIEWS_BY_AXIS


def _work(work_id, year, cited, authors, *, issn="0028-0836"):
    """Build a minimal OpenAlex work. `authors` = list of (author_id, inst_id)."""
    return {
        "id": f"https://openalex.org/{work_id}",
        "doi": f"https://doi.org/10.1/{work_id}",
        "publication_year": year,
        "cited_by_count": cited,
        "primary_location": {"source": {"id": "https://openalex.org/S1", "issn_l": issn, "display_name": "Nature"}},
        "primary_topic": {
            "id": "https://openalex.org/T1", "display_name": "Astro",
            "field": {"id": "https://openalex.org/fields/31", "display_name": "Physics and Astronomy"},
        },
        "topics": [{
            "id": "https://openalex.org/T1", "display_name": "Astro", "score": 0.9,
            "field": {"id": "https://openalex.org/fields/31", "display_name": "Physics and Astronomy"},
        }],
        "counts_by_year": [{"year": year + 1, "cited_by_count": cited}],
        "authorships": [
            {"author_position": "first" if i == 0 else "middle",
             "author": {"id": f"https://openalex.org/{aid}", "display_name": aid},
             "institutions": [{"id": f"https://openalex.org/{iid}", "display_name": iid}]}
            for i, (aid, iid) in enumerate(authors)
        ],
    }


def _seeded_store() -> LakeStore:
    store = LakeStore(":memory:")
    store.ingest_work_rows(transform_work(_work("W1", 2018, 42, [("A1", "I1"), ("A2", "I2")])))
    store.ingest_work_rows(transform_work(_work("W2", 2019, 10, [("A1", "I1")])))
    return store


def test_views_are_registered_on_store():
    with LakeStore(":memory:") as store:
        names = {r[0] for r in store.con.execute(
            "SELECT view_name FROM duckdb_views() WHERE NOT internal"
        ).fetchall()}
        assert set(ANALYSIS_VIEWS.keys()).issubset(names)


def test_journal_yearly_scientometrics():
    with _seeded_store() as store:
        rows = store.con.execute(
            "SELECT publication_year, works, citations FROM v_journal_yearly "
            "WHERE issn_l = '0028-0836' ORDER BY publication_year"
        ).fetchall()
        assert rows == [(2018, 1, 42), (2019, 1, 10)]


def test_journal_citation_trend():
    with _seeded_store() as store:
        total = store.con.execute(
            "SELECT sum(citations) FROM v_journal_citation_trend WHERE issn_l = '0028-0836'"
        ).fetchone()[0]
        assert total == 52  # 42 (2019) + 10 (2020)


def test_coauthor_pairs_network():
    with _seeded_store() as store:
        rows = store.con.execute(
            "SELECT author_a, author_b, collaborations FROM v_coauthor_pairs"
        ).fetchall()
        assert rows == [("A1", "A2", 1)]  # only W1 has two authors


def test_topic_and_field_trends():
    with _seeded_store() as store:
        topic_works = store.con.execute(
            "SELECT sum(works) FROM v_topic_yearly WHERE topic_id = 'T1'"
        ).fetchone()[0]
        assert topic_works == 2
        field = store.con.execute(
            "SELECT field, sum(works) FROM v_field_yearly GROUP BY field"
        ).fetchone()
        assert field == ("Physics and Astronomy", 2)


def test_source_coverage_and_keys():
    with _seeded_store() as store:
        cov = store.con.execute(
            "SELECT works, first_year, last_year, works_with_doi FROM v_source_coverage "
            "WHERE issn_l = '0028-0836'"
        ).fetchone()
        assert cov == (2, 2018, 2019, 2)
        assert store.con.execute("SELECT count(*) FROM v_work_keys").fetchone()[0] == 2


def test_views_by_axis_covers_all_views():
    listed = {v for views in VIEWS_BY_AXIS.values() for v in views}
    assert listed == set(ANALYSIS_VIEWS.keys())
