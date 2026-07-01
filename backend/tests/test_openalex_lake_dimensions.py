"""Tests for the OpenAlex dimension loader (gz JSONL -> DuckDB dim_*)."""
import gzip
import json
import os

from backend.openalex_lake.store import LakeStore
from backend.openalex_lake.sync_dimensions import (
    download_entity,
    load_entity_dir,
    run_sync,
)
from backend.openalex_lake.transform import (
    transform_institution,
    transform_source,
    transform_topic,
)


def _write_gz(path: str, records: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")
        fh.write("\n")  # trailing blank line must be tolerated


def test_dimension_transforms():
    assert transform_source({"id": "https://openalex.org/S1", "issn_l": "0028-0836",
                             "display_name": "Nature"})["issn_l"] == "0028-0836"
    assert transform_institution({"id": "https://openalex.org/I1",
                                 "ror": "https://ror.org/05gq02987"})["ror"] == "05gq02987"
    topic = transform_topic({"id": "https://openalex.org/T1", "display_name": "Astro",
                             "field": {"id": "https://openalex.org/fields/31", "display_name": "Physics and Astronomy"}})
    assert topic["field_id"] == 31 and topic["field"] == "Physics and Astronomy"
    assert transform_source({"issn_l": "x"}) is None  # no id -> skipped


def test_load_entity_dir_streams_gz(tmp_path):
    snap = str(tmp_path)
    _write_gz(os.path.join(snap, "sources", "updated_date=2025-06-01", "part_000.gz"), [
        {"id": "https://openalex.org/S1", "issn_l": "0028-0836", "display_name": "Nature", "is_in_doaj": False},
        {"id": "https://openalex.org/S2", "issn_l": "1476-4687", "display_name": "Science"},
    ])
    with LakeStore(":memory:") as store:
        n = load_entity_dir(store, "sources", snapshot_dir=snap)
        assert n == 2
        assert store.count("dim_source") == 2
        # idempotent re-load
        assert load_entity_dir(store, "sources", snapshot_dir=snap) == 2
        assert store.count("dim_source") == 2
        issn = store.con.execute(
            "SELECT issn_l FROM dim_source WHERE source_id = 'S1'"
        ).fetchone()[0]
        assert issn == "0028-0836"


def test_load_entity_dir_missing_dir_is_noop(tmp_path):
    with LakeStore(":memory:") as store:
        assert load_entity_dir(store, "topics", snapshot_dir=str(tmp_path)) == 0


def test_run_sync_all_dimensions(tmp_path):
    snap = str(tmp_path)
    _write_gz(os.path.join(snap, "sources", "d=1", "p.gz"), [{"id": "https://openalex.org/S1"}])
    _write_gz(os.path.join(snap, "institutions", "d=1", "p.gz"), [{"id": "https://openalex.org/I1", "ror": "https://ror.org/x"}])
    _write_gz(os.path.join(snap, "topics", "d=1", "p.gz"), [{"id": "https://openalex.org/T1", "display_name": "T"}])
    with LakeStore(":memory:") as store:
        stats = run_sync(store, snapshot_dir=snap)
        assert stats == {"sources": 1, "institutions": 1, "topics": 1}


def test_download_entity_builds_no_sign_request_command(tmp_path):
    captured = {}
    download_entity("sources", snapshot_dir=str(tmp_path), runner=lambda cmd: captured.setdefault("cmd", cmd))
    assert captured["cmd"][:3] == ["aws", "s3", "sync"]
    assert captured["cmd"][3].endswith("/data/sources")
    assert "--no-sign-request" in captured["cmd"]
