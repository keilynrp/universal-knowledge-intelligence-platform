"""Backup evidence recorded on the host is ingested without a credential (#370).

The ops monitor reports ``backup_freshness: critical`` every day nobody records
the cycle by hand, while the backups are fine. The host recorder now leaves one
evidence document per backup in the read-only signals directory; these tests
hold what the backend does with them:

- a valid document becomes exactly one ``backup`` event, whoever else recorded
  that backup;
- anything that is not exactly one of our documents is rejected with a reason,
  and never stops ingestion or the monitor;
- once recorded, freshness recovers without a person.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from backend import models, ops_monitor
from backend.backup_assurance import (
    evaluate_backup_freshness,
    latest_completed_backup,
    record_event,
)
from backend.backup_evidence import (
    MAX_DOCUMENT_BYTES,
    RECORDER_OPERATOR,
    EvidenceDocument,
    Rejection,
    ingest_backup_evidence,
    parse_evidence_document,
    same_backup,
)

NOW = datetime(2026, 9, 25, 4, 0, tzinfo=timezone.utc)
ENV = "production"
DIGEST = "a" * 64


def _doc(**overrides) -> dict:
    document = {
        "schema_version": 1,
        "recorder": "ukip-backup-evidence-recorder/1",
        "observed_at": "2026-09-25T03:12:40Z",
        "environment": ENV,
        "scope": "database",
        "backup_id": "pg/2026-09-25T03-00-00-076Z.sql.gz",
        "completed_at": "2026-09-25T03:00:41Z",
        "size_bytes": 5968925,
        "sha256": DIGEST,
        "gzip_ok": True,
        "provider": "s3-compatible",
    }
    document.update(overrides)
    return document


def _raw(**overrides) -> bytes:
    return json.dumps(_doc(**overrides)).encode()


def _write(directory, name: str, **overrides) -> None:
    (directory / name).write_bytes(_raw(**overrides))


def _events(db):
    return db.query(models.BackupAssuranceEvent).filter(
        models.BackupAssuranceEvent.event_type == "backup"
    ).order_by(models.BackupAssuranceEvent.id).all()


# ── The parser ────────────────────────────────────────────────────────────────

def test_a_valid_document_parses():
    parsed = parse_evidence_document(_raw(), environment=ENV, now=NOW)

    assert isinstance(parsed, EvidenceDocument)
    assert parsed.backup_id == "pg/2026-09-25T03-00-00-076Z.sql.gz"
    assert parsed.completed_at == datetime(2026, 9, 25, 3, 0, 41, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (b"{not json", "malformed_json"),
        (b"[]", "not_an_object"),
        (_raw(extra="x"), "unknown_keys"),
        (json.dumps({k: v for k, v in _doc().items() if k != "sha256"}).encode(), "missing_keys"),
        (_raw(schema_version=2), "unsupported_schema_version"),
        (_raw(schema_version=True), "unsupported_schema_version"),
        (_raw(environment="staging"), "other_environment"),
        (_raw(scope="everything"), "unknown_scope"),
        (_raw(backup_id=""), "invalid_backup_id"),
        (_raw(backup_id="/etc/passwd"), "invalid_backup_id"),
        (_raw(backup_id="pg/../x.sql.gz"), "invalid_backup_id"),
        (_raw(size_bytes=0), "invalid_size"),
        (_raw(size_bytes=-5), "invalid_size"),
        (_raw(size_bytes="5968925"), "invalid_size"),
        (_raw(size_bytes=True), "invalid_size"),
        (_raw(sha256="A" * 64), "invalid_sha256"),
        (_raw(sha256="a" * 63), "invalid_sha256"),
        (_raw(sha256="etag-d41d8cd98f00b204e9800998ecf8427e-3"), "invalid_sha256"),
        (_raw(gzip_ok=None), "gzip_result_required_for_database"),
        (_raw(scope="volume", gzip_ok=True), "gzip_result_only_for_database"),
        (_raw(completed_at="yesterday"), "invalid_timestamp"),
        (_raw(completed_at="2026-09-25T03:00:41"), "invalid_timestamp"),
        (_raw(completed_at="2026-09-25T05:00:00Z"), "timestamp_in_future"),
        (_raw(completed_at="2026-09-01T03:00:00Z"), "too_old"),
        (_raw(recorder=""), "invalid_recorder_or_provider"),
    ],
)
def test_anything_that_is_not_exactly_ours_is_rejected_with_a_reason(raw, reason):
    parsed = parse_evidence_document(raw, environment=ENV, now=NOW)

    assert parsed == Rejection(reason)


def test_an_oversized_document_is_rejected_before_parsing():
    assert parse_evidence_document(b" " * (MAX_DOCUMENT_BYTES + 1), environment=ENV, now=NOW) == Rejection("oversized")


def test_a_volume_document_carries_no_gzip_result():
    parsed = parse_evidence_document(
        _raw(scope="volume", backup_id="volume/2026-09-25T03-05-00-000Z.tar.gz", gzip_ok=None),
        environment=ENV, now=NOW,
    )
    assert isinstance(parsed, EvidenceDocument) and parsed.gzip_ok is None


@pytest.mark.parametrize(
    ("recorded", "observed", "same"),
    [
        ("pg/a.sql.gz", "pg/a.sql.gz", True),
        ("ukip-dbukip-eqmmhw/pg/a.sql.gz", "pg/a.sql.gz", True),
        ("pg/a.sql.gz", "ukip-dbukip-eqmmhw/pg/a.sql.gz", True),
        ("xpg/a.sql.gz", "pg/a.sql.gz", False),  # a suffix only counts on a path boundary
        ("pg/b.sql.gz", "pg/a.sql.gz", False),
        (None, "pg/a.sql.gz", False),
    ],
)
def test_backup_ids_match_across_key_forms(recorded, observed, same):
    assert same_backup(recorded, observed) is same


# ── Ingestion ─────────────────────────────────────────────────────────────────

def test_a_new_document_is_recorded_once_across_cycles(db_session, tmp_path):
    _write(tmp_path, "database-2026-09-25T03-00-00-076Z.json")

    first = ingest_backup_evidence(db_session, directory=tmp_path, environment=ENV, now=NOW)
    second = ingest_backup_evidence(db_session, directory=tmp_path, environment=ENV, now=NOW)

    assert first == {"recorded": 1, "already_recorded": 0, "rejected": 0}
    assert second == {"recorded": 0, "already_recorded": 1, "rejected": 0}
    [event] = _events(db_session)
    assert event.status == "completed"
    assert event.operator == RECORDER_OPERATOR
    assert event.integrity_ref == f"sha256:{DIGEST}"
    assert event.size_bytes == 5968925
    assert event.scope == "database"
    evidence = json.loads(event.evidence_json)
    assert evidence["method"] == "sha256-stream+gzip-t"
    assert evidence["source"] == "host-signal"


def test_a_manual_record_with_a_longer_key_suppresses_it(db_session, tmp_path):
    record_event(
        db_session, event_type="backup", status="completed", scope="database",
        environment=ENV, provider="s3-compatible", operator="keilyn",
        backup_id="ukip-dbukip-eqmmhw/pg/2026-09-25T03-00-00-076Z.sql.gz",
        started_at=NOW - timedelta(hours=1), completed_at=NOW - timedelta(hours=1),
        size_bytes=5968925, integrity_ref=f"sha256:{DIGEST}",
    )
    db_session.commit()
    _write(tmp_path, "database-2026-09-25T03-00-00-076Z.json")

    counts = ingest_backup_evidence(db_session, directory=tmp_path, environment=ENV, now=NOW)

    assert counts["already_recorded"] == 1
    assert [e.operator for e in _events(db_session)] == ["keilyn"]


def test_the_same_object_in_another_scope_is_a_different_backup(db_session, tmp_path):
    _write(tmp_path, "database.json")
    _write(tmp_path, "volume.json", scope="volume", backup_id="pg/2026-09-25T03-00-00-076Z.sql.gz", gzip_ok=None)

    counts = ingest_backup_evidence(db_session, directory=tmp_path, environment=ENV, now=NOW)

    assert counts["recorded"] == 2


def test_a_dump_that_fails_its_gzip_test_is_recorded_as_failed(db_session, tmp_path):
    _write(tmp_path, "database.json", gzip_ok=False)

    ingest_backup_evidence(db_session, directory=tmp_path, environment=ENV, now=NOW)

    [event] = _events(db_session)
    assert event.status == "failed"


def test_one_bad_document_does_not_stop_the_others(db_session, tmp_path, caplog):
    (tmp_path / "broken.json").write_bytes(b"{not json")
    _write(tmp_path, "staging.json", environment="staging")
    _write(tmp_path, "good.json")

    counts = ingest_backup_evidence(db_session, directory=tmp_path, environment=ENV, now=NOW)

    assert counts == {"recorded": 1, "already_recorded": 0, "rejected": 2}
    assert "broken.json rejected: malformed_json" in caplog.text
    assert "staging.json rejected: other_environment" in caplog.text


def test_symlinks_subdirectories_and_other_files_are_ignored(db_session, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    _write(outside, "planted.json")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    os.symlink(outside / "planted.json", evidence / "link.json")
    (evidence / "nested").mkdir()
    _write(evidence / "nested", "deeper.json")
    (evidence / "notes.txt").write_text("not evidence")

    counts = ingest_backup_evidence(db_session, directory=evidence, environment=ENV, now=NOW)

    assert counts == {"recorded": 0, "already_recorded": 0, "rejected": 0}
    assert _events(db_session) == []


def test_a_missing_directory_is_simply_nothing_to_ingest(db_session, tmp_path):
    counts = ingest_backup_evidence(db_session, directory=tmp_path / "absent", environment=ENV, now=NOW)

    assert counts == {"recorded": 0, "already_recorded": 0, "rejected": 0}


def test_freshness_recovers_without_a_person(db_session, tmp_path):
    """The point of #370: yesterday's manual record is stale, today's automatic one is not."""
    record_event(
        db_session, event_type="backup", status="completed", scope="database",
        environment=ENV, provider="s3-compatible", operator="keilyn",
        backup_id="pg/2026-09-22T03-00-00-000Z.sql.gz",
        started_at=NOW - timedelta(days=3), completed_at=NOW - timedelta(days=3),
        size_bytes=5954445, integrity_ref=f"sha256:{'b' * 64}",
    )
    db_session.commit()

    def freshness():
        latest = latest_completed_backup(db_session, ENV)
        return evaluate_backup_freshness(
            latest_completed_at=latest.completed_at, now=NOW, size_bytes=latest.size_bytes,
            integrity_ref=latest.integrity_ref, provider_reachable=True,
        )

    assert "backup_stale" in freshness()["reason_codes"]

    _write(tmp_path, "database.json")
    ingest_backup_evidence(db_session, directory=tmp_path, environment=ENV, now=NOW)

    assert freshness()["status"] == "ok"


# ── The monitor ───────────────────────────────────────────────────────────────

def test_the_monitor_ingests_before_judging_and_survives_a_failure(monkeypatch):
    order: list[str] = []

    def ingest(db, now):
        order.append("ingest")
        raise RuntimeError("database gone")

    def checks(db):
        order.append("checks")
        return {"status": "ok", "checked_at": NOW.isoformat(), "summary": {}, "checks": []}

    class _Db:
        def rollback(self):
            order.append("rollback")

    monkeypatch.setitem(ops_monitor._memory, "last", None)
    ops_monitor.run_once(_Db(), now=NOW, run_checks=checks, dispatch=lambda *a, **k: None, ingest_evidence=ingest)

    assert order == ["ingest", "rollback", "checks"]
