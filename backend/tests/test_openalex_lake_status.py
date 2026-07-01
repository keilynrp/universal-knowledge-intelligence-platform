"""Tests for the lake status snapshot + read-only store open."""
import pytest

from backend.openalex_lake.status import lake_status
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
