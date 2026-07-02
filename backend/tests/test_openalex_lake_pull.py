"""Tests for the OpenAlex works puller (pure logic + paginated ingest)."""
from unittest.mock import MagicMock

import httpx

from backend.openalex_lake.config import LakeScope, LakeSettings
from backend.openalex_lake.pull_works import (
    RateLimitExhausted,
    _default_fetch,
    build_filter,
    chunk_issns,
    iter_works,
    parse_issn_list,
    parse_rate_limit_headers,
    read_issn_file,
    run_pull,
    select_fields,
)
from backend.openalex_lake.status import read_live_status
from backend.openalex_lake.store import LakeStore


def test_parse_issn_list_dedups_and_trims():
    assert parse_issn_list(" 0028-0836, 1476-4687 ,0028-0836,, ") == ["0028-0836", "1476-4687"]
    assert parse_issn_list("") == []


def test_read_issn_file_ignores_blanks_and_comments(tmp_path):
    p = tmp_path / "issns.txt"
    p.write_text("# journals\n0028-0836\n\n1476-4687\n0028-0836\n", encoding="utf-8")
    assert read_issn_file(str(p)) == ["0028-0836", "1476-4687"]


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


def test_select_fields_adds_referenced_works_only_with_citations():
    base = select_fields(LakeScope())
    assert "authorships" in base and "counts_by_year" in base
    assert "referenced_works" not in base
    assert "referenced_works" in select_fields(LakeScope(include_citations=True))


def test_iter_works_passes_select_param():
    seen = {}

    def fetch(url, params):
        seen.update(params)
        return {"results": [], "meta": {"next_cursor": None}}

    list(iter_works(fetch, "filter", "id,doi"))
    assert seen["select"] == "id,doi"


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


def test_run_pull_stops_cleanly_on_rate_limit():
    # First page returns one work, second call hits the daily budget.
    calls = {"n": 0}

    def fetch(url, params):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"results": [{"id": "https://openalex.org/W1", "publication_year": 2018}],
                    "meta": {"next_cursor": "c2"}}
        raise RateLimitExhausted(retry_after=28181)

    scope = LakeScope().with_issns(["0028-0836"])
    with LakeStore(":memory:") as store:
        stats = run_pull(scope, store, fetch)
        assert stats["rate_limited"] is True
        assert stats["retry_after"] == 28181
        assert stats["watermark"] is None          # partial -> no watermark advance
        assert store.count("fact_works") == 1       # partial data was persisted


def test_parse_rate_limit_headers_extracts_known_fields():
    headers = {
        "x-ratelimit-limit": "10000",
        "x-ratelimit-remaining": "9999",
        "x-ratelimit-prepaid-remaining-usd": "2",
        "x-ratelimit-cost-usd": "0.0001",
        "some-other-header": "ignored",
    }
    parsed = parse_rate_limit_headers(headers)
    assert parsed == {
        "limit": 10000,
        "remaining": 9999,
        "prepaid_remaining_usd": 2,
        "last_request_cost_usd": 0.0001,
    }


def test_parse_rate_limit_headers_empty_when_absent():
    assert parse_rate_limit_headers({}) == {}


def test_default_fetch_invokes_rate_limit_callback(monkeypatch):
    def fake_get(self, url, params=None):
        resp = MagicMock(status_code=200)
        resp.headers = {"x-ratelimit-remaining": "9999", "x-ratelimit-limit": "10000"}
        resp.json.return_value = {"results": [], "meta": {"next_cursor": None}}
        return resp

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    captured: list[dict] = []
    fetch = _default_fetch(LakeSettings(), on_response_headers=captured.append)
    fetch("https://api.openalex.org/works", {})
    assert captured and captured[0]["x-ratelimit-remaining"] == "9999"


def test_backfill_writes_a_live_status_sidecar(tmp_path):
    """The whole feature this proves: while a pull holds the DB's write lock,
    progress must still be readable. The sidecar is written via the writer's
    own connection, so it needs a real file (":memory:" has no sidecar).
    Uses two journals where only the first completes (the second hits the
    daily budget) so the run genuinely stops mid-backfill — phase must still
    read "backfill", not "incremental" (which would only be true once every
    journal in the scope is done)."""
    db = str(tmp_path / "lake.duckdb")
    scope = LakeScope().with_issns(["1111-1111", "2222-2222"])

    def fetch(url, params):
        if "1111-1111" in params["filter"]:
            return {"results": [{"id": "https://openalex.org/W1"}], "meta": {"next_cursor": None}}
        raise RateLimitExhausted(retry_after=100)

    with LakeStore(db) as store:
        run_pull(scope, store, fetch)

    sidecar = read_live_status(db)
    assert sidecar is not None
    assert sidecar["phase"] == "backfill"
    assert sidecar["backfill_journals_done"] == 1
    assert sidecar["backfill_total_issns"] == 2
    assert "snapshot_captured_at" in sidecar


def test_backfill_resumes_per_issn_then_switches_to_incremental():
    scope = LakeScope().with_issns(["1111-1111", "2222-2222"])
    with LakeStore(":memory:") as store:
        # Run 1: journal 1 completes, journal 2 hits the daily budget.
        def fetch1(url, params):
            if "1111-1111" in params["filter"]:
                return {"results": [{"id": "https://openalex.org/W1"}], "meta": {"next_cursor": None}}
            raise RateLimitExhausted(retry_after=100)

        s1 = run_pull(scope, store, fetch1)
        assert s1["mode"] == "backfill" and s1["rate_limited"] is True
        assert s1["done_issns"] == 1 and s1["complete"] is False
        assert s1["watermark"] is None and store.get_watermark("works") is None
        assert store.count("fact_works") == 1

        # Run 2: journal 1 is checkpointed (skipped); journal 2 completes the pass.
        seen = []

        def fetch2(url, params):
            seen.append("1111" if "1111-1111" in params["filter"] else "2222")
            return {"results": [{"id": "https://openalex.org/W2"}], "meta": {"next_cursor": None}}

        s2 = run_pull(scope, store, fetch2)
        assert seen == ["2222"]  # journal 1 was NOT re-fetched
        assert s2["complete"] is True and s2["done_issns"] == 2
        assert store.get_watermark("works") is not None
        assert store.count("fact_works") == 2

        # Run 3: watermark set -> incremental mode from here on.
        s3 = run_pull(scope, store, lambda u, p: {"results": [], "meta": {"next_cursor": None}})
        assert s3["mode"] == "incremental"


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
