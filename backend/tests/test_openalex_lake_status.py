"""Tests for the lake status snapshot + read-only store open."""
import pytest

from backend.openalex_lake.status import _total_scoped_issns, lake_status, resolve_status
from backend.openalex_lake.store import LakeStore
from backend.openalex_lake.transform import transform_work


def _work(work_id, year, issn="0028-0836"):
    return {
        "id": f"https://openalex.org/{work_id}",
        "publication_year": year,
        "primary_location": {"source": {"id": "https://openalex.org/S1", "issn_l": issn}},
    }


def test_lake_status_reports_watermark_coverage_and_span():
    with LakeStore(":memory:") as store:
        store.ingest_work_rows(transform_work(_work("W1", 2012)))
        store.ingest_work_rows(transform_work(_work("W2", 2020)))
        store.set_watermark("works", "2026-06-30")

        status = lake_status(store)
        assert status["works_watermark"] == "2026-06-30"
        assert status["journals"] == 1
        assert status["year_min"] == 2012 and status["year_max"] == 2020
        assert status["tables"]["fact_works"] == 2


def test_rate_limit_snapshot_roundtrip_and_status_inclusion():
    with LakeStore(":memory:") as store:
        assert store.get_rate_limit_snapshot() is None
        store.set_rate_limit_snapshot({"limit": 10000, "remaining": 9412, "prepaid_remaining_usd": 1.87})
        snap = store.get_rate_limit_snapshot()
        assert snap["limit"] == 10000 and snap["remaining"] == 9412
        assert "captured_at" in snap  # timestamped for "last seen X min ago"

        status = lake_status(store)
        assert status["rate_limit"]["remaining"] == 9412


def test_set_rate_limit_snapshot_ignores_empty_headers():
    with LakeStore(":memory:") as store:
        store.set_rate_limit_snapshot({})
        assert store.get_rate_limit_snapshot() is None


def test_total_scoped_issns_counts_distinct_journal_metrics(db_session):
    from backend.models import JournalMetric

    db_session.add_all([
        JournalMetric(issn_l="0028-0836", normalized_impact_factor=1.0),
        JournalMetric(issn_l="1476-4687", normalized_impact_factor=1.0),
    ])
    db_session.commit()
    assert _total_scoped_issns() == 2


def test_resolve_status_reports_locked_on_real_write_lock(tmp_path):
    """A concurrent read-only open while a writer holds the file must return
    the friendly {"lake": "locked"} marker, not raise. DuckDB's actual lock
    conflict is _duckdb.ConnectionException (NOT IOException, despite the
    error text mentioning I/O) — this reproduces the real conflict rather
    than mocking an exception type, so it would have caught the mismatch."""
    db = str(tmp_path / "lake.duckdb")
    writer = LakeStore(db)  # holds the write lock; deliberately not closed yet
    try:
        out = resolve_status(db)
        assert out == {
            "lake": "locked",
            "db_path": db,
            "hint": "a pull is currently running; re-check once it finishes",
        }
    finally:
        writer.close()


def test_resolve_status_not_initialized(tmp_path):
    missing = str(tmp_path / "nope.duckdb")
    out = resolve_status(missing)
    assert out["lake"] == "not_initialized" and "pull_works" in out["hint"]


def test_resolve_status_reads_existing_lake(tmp_path):
    db = str(tmp_path / "lake.duckdb")
    with LakeStore(db) as store:
        store.ingest_work_rows(transform_work(_work("W1", 2015)))
    out = resolve_status(db)
    assert out["tables"]["fact_works"] == 1


def test_read_only_store_can_query_persisted_lake(tmp_path):
    db = str(tmp_path / "lake.duckdb")
    with LakeStore(db) as store:
        store.ingest_work_rows(transform_work(_work("W1", 2015)))
        store.set_watermark("works", "2026-06-30")

    with LakeStore(db, read_only=True) as ro:
        assert lake_status(ro)["tables"]["fact_works"] == 1
        # read-only really is read-only
        with pytest.raises(Exception):
            ro.insert_rows("fact_works", [{"work_id": "W2"}])
