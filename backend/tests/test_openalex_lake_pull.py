"""Tests for the OpenAlex works puller (pure logic + paginated ingest)."""
from backend.openalex_lake.config import LakeScope
from backend.openalex_lake.pull_works import build_filter, chunk_issns, iter_works, run_pull
from backend.openalex_lake.store import LakeStore


def test_chunk_issns_bounds_url():
    issns = [f"{i:04d}-000X" for i in range(120)]
    chunks = chunk_issns(issns, size=50)
    assert [len(c) for c in chunks] == [50, 50, 20]
    # empty input still yields one (empty) chunk so callers can iterate.
    assert chunk_issns([]) == [[]]


def test_build_filter_composes_clauses():
    scope = LakeScope(year_from=2010, year_to=2025, field_ids=(31,), country_codes=("US",))
    f = build_filter(scope, issn_chunk=["0028-0836", "1476-4687"], from_updated_date="2025-06-30")
    assert "primary_location.source.issn:0028-0836|1476-4687" in f
    assert "primary_topic.field.id:fields/31" in f
    assert "authorships.institutions.country_code:us" in f
    assert "from_publication_date:2010-01-01" in f
    assert "to_publication_date:2025-12-31" in f
    assert "from_updated_date:2025-06-30" in f
    # AND-joined
    assert f.count(",") >= 5


def test_build_filter_omits_absent_clauses():
    f = build_filter(LakeScope(year_from=None, year_to=None), issn_chunk=None)
    assert f == ""


def _fake_fetch(pages):
    """Return a fetch that replays `pages` (list of bodies) by cursor."""
    calls = {"n": 0}

    def fetch(url, params):
        body = pages[calls["n"]]
        calls["n"] += 1
        return body

    return fetch


def test_iter_works_follows_cursor():
    pages = [
        {"results": [{"id": "https://openalex.org/W1"}], "meta": {"next_cursor": "c2"}},
        {"results": [{"id": "https://openalex.org/W2"}], "meta": {"next_cursor": None}},
    ]
    works = list(iter_works(_fake_fetch(pages), "filter"))
    assert [w["id"] for w in works] == ["https://openalex.org/W1", "https://openalex.org/W2"]


def test_run_pull_ingests_and_watermarks():
    pages = [
        {
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "publication_year": 2018,
                    "primary_location": {"source": {"id": "https://openalex.org/S1", "issn_l": "0028-0836"}},
                }
            ],
            "meta": {"next_cursor": None},
        }
    ]
    scope = LakeScope().with_issns(["0028-0836"])
    with LakeStore(":memory:") as store:
        stats = run_pull(scope, store, _fake_fetch(pages))
        assert stats["works"] == 1
        assert stats["limited"] is False
        assert store.count("fact_works") == 1
        assert store.get_watermark("works") is not None
        assert stats["tables"]["fact_works"] == 1


def test_run_pull_limit_is_partial_and_no_watermark():
    pages = [
        {
            "results": [
                {"id": "https://openalex.org/W1", "publication_year": 2018},
                {"id": "https://openalex.org/W2", "publication_year": 2019},
                {"id": "https://openalex.org/W3", "publication_year": 2020},
            ],
            "meta": {"next_cursor": None},
        }
    ]
    scope = LakeScope().with_issns(["0028-0836"])
    with LakeStore(":memory:") as store:
        stats = run_pull(scope, store, _fake_fetch(pages), limit=2)
        assert stats["works"] == 2 and stats["limited"] is True
        assert store.count("fact_works") == 2  # stopped early
        assert stats["watermark"] is None
        # a smoke run must NOT advance the watermark
        assert store.get_watermark("works") is None
