"""The host recorder writes what the backend accepts (#370).

The two halves of automatic backup evidence are a shell script on the host and
a parser in the app. Testing them apart would let the document drift, so these
run the real script with a stub `aws` on PATH and feed every document it writes
to the real ``parse_evidence_document``.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.backup_evidence import EvidenceDocument, parse_evidence_document

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required to run the recorder")

RECORDER = Path(__file__).resolve().parents[2] / "scripts" / "ukip-backup-evidence-recorder.sh"
PREFIX = "ukip-dbukip-eqmmhw/"
DB_KEY = f"{PREFIX}pg/2026-09-25T03-00-00-076Z.sql.gz"
VOL_KEY = f"{PREFIX}volumes/ukip_static_data-2026-09-25T03-05-00-066Z.tar"
SECRET = "not-a-real-secret-value-for-the-test-only"

_STUB = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG"
if [ "$1" = "s3api" ]; then
  case "$*" in
    *".sql.gz"*) [ -n "${STUB_DB_LISTING:-}" ] && printf '%b\n' "$STUB_DB_LISTING" || echo None ;;
    *".tar"*)    [ -n "${STUB_VOL_LISTING:-}" ] && printf '%b\n' "$STUB_VOL_LISTING" || echo None ;;
  esac
  exit "${STUB_LIST_EXIT:-0}"
fi
if [ "$1" = "s3" ] && [ "$2" = "cp" ]; then
  for arg in "$@"; do case "$arg" in s3://*) key=${arg#s3://*/} ;; esac; done
  cat "$STUB_OBJECTS/$(basename "$key")"
  exit "${STUB_CP_EXIT:-0}"
fi
exit 9
"""


def _stamp(minutes_ago: int) -> str:
    """A listing timestamp relative to the real clock: the recorder stamps
    observed_at with the real time, and a fixed date would age out of the
    backend's 14-day window."""
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _setup(tmp_path, *, db_bytes: bytes | None, vol_bytes: bytes | None = None, db_size: int | None = None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "aws").write_text(_STUB, encoding="utf-8")
    (bin_dir / "aws").chmod(0o755)
    objects = tmp_path / "objects"
    objects.mkdir()
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "STUB_LOG": str(tmp_path / "argv.log"),
        "STUB_OBJECTS": str(objects),
        "UKIP_EVIDENCE_OUT_DIR": str(tmp_path / "signals" / "backup-evidence"),
        "S3_BACKUP_ENDPOINT": "https://s3.example.invalid",
        "S3_BACKUP_BUCKET": "bucket",
        "S3_BACKUP_PREFIX": PREFIX,
        "AWS_ACCESS_KEY_ID": "AKIAEXAMPLEONLYNOTREAL",
        "AWS_SECRET_ACCESS_KEY": SECRET,
        "AWS_DEFAULT_REGION": "us-east-2",
        "UKIP_AWS_RUNNER": "aws",
    }
    if db_bytes is not None:
        (objects / Path(DB_KEY).name).write_bytes(db_bytes)
        size = len(db_bytes) if db_size is None else db_size
        env["STUB_DB_LISTING"] = f"{DB_KEY}\\t{size}\\t{_stamp(60)}"
    if vol_bytes is not None:
        (objects / Path(VOL_KEY).name).write_bytes(vol_bytes)
        env["STUB_VOL_LISTING"] = f"{VOL_KEY}\\t{len(vol_bytes)}\\t{_stamp(55)}"
    return env


def _run(env, **extra):
    return subprocess.run(["bash", str(RECORDER)], capture_output=True, text=True, check=False, env={**env, **extra})


def _documents(env) -> dict[str, dict]:
    out = Path(env["UKIP_EVIDENCE_OUT_DIR"])
    return {p.name: json.loads(p.read_text()) for p in sorted(out.glob("*.json"))}


def _parse(document: dict):
    return parse_evidence_document(
        json.dumps(document).encode(), environment="production",
        now=datetime.now(timezone.utc),
    )


DUMP = gzip.compress(b"-- PostgreSQL database dump\nSELECT 1;\n" * 200)
ARCHIVE = b"ustar archive bytes " * 300


def test_it_records_both_scopes_in_the_form_the_backend_accepts(tmp_path):
    env = _setup(tmp_path, db_bytes=DUMP, vol_bytes=ARCHIVE)

    completed = _run(env)

    assert completed.returncode == 0, completed.stderr
    docs = _documents(env)
    assert set(docs) == {
        "database-pg_2026-09-25T03-00-00-076Z.sql.gz.json",
        "volume-volumes_ukip_static_data-2026-09-25T03-05-00-066Z.tar.json",
    }
    db = _parse(docs["database-pg_2026-09-25T03-00-00-076Z.sql.gz.json"])
    vol = _parse(docs["volume-volumes_ukip_static_data-2026-09-25T03-05-00-066Z.tar.json"])
    assert isinstance(db, EvidenceDocument) and isinstance(vol, EvidenceDocument)
    assert db.backup_id == "pg/2026-09-25T03-00-00-076Z.sql.gz", "relative to the prefix, no bucket or prefix"
    assert db.sha256 == hashlib.sha256(DUMP).hexdigest(), "digest over the stored bytes"
    assert db.size_bytes == len(DUMP) and db.gzip_ok is True
    assert vol.gzip_ok is None and vol.sha256 == hashlib.sha256(ARCHIVE).hexdigest()


def test_a_corrupt_dump_is_recorded_with_gzip_ok_false(tmp_path):
    env = _setup(tmp_path, db_bytes=b"this is not gzip at all")

    assert _run(env).returncode == 0
    [doc] = _documents(env).values()
    assert doc["gzip_ok"] is False


def test_an_interrupted_download_writes_nothing(tmp_path):
    env = _setup(tmp_path, db_bytes=DUMP[:100], db_size=len(DUMP))

    completed = _run(env, STUB_CP_EXIT="1")

    assert completed.returncode != 0
    assert _documents(env) == {}
    assert "download_failed" in completed.stderr


def test_a_truncated_download_writes_nothing(tmp_path):
    """The copy exits 0 but hands over fewer bytes than the listing reports."""
    env = _setup(tmp_path, db_bytes=DUMP[:100], db_size=len(DUMP))

    completed = _run(env)

    assert completed.returncode != 0
    assert _documents(env) == {}
    assert "truncated" in completed.stderr


def test_an_existing_document_is_not_downloaded_again(tmp_path):
    env = _setup(tmp_path, db_bytes=DUMP)
    assert _run(env).returncode == 0
    first = _documents(env)
    log = Path(env["STUB_LOG"])
    log.write_text("")

    assert _run(env).returncode == 0

    assert _documents(env) == first
    assert "s3 cp" not in log.read_text(), "an already-recorded backup must not be fetched again"


def test_no_object_is_not_a_failure(tmp_path):
    env = _setup(tmp_path, db_bytes=None)

    completed = _run(env)

    assert completed.returncode == 0
    assert "scope=database no_object" in completed.stdout
    assert _documents(env) == {}


def test_documents_older_than_the_backend_window_are_pruned(tmp_path):
    env = _setup(tmp_path, db_bytes=None)
    out = Path(env["UKIP_EVIDENCE_OUT_DIR"])
    out.mkdir(parents=True)
    stale = out / "database-pg_old.sql.gz.json"
    stale.write_text("{}")
    old = time.time() - 20 * 86400
    os.utime(stale, (old, old))

    assert _run(env).returncode == 0
    assert not stale.exists()


def test_no_credential_or_key_path_reaches_the_output(tmp_path):
    env = _setup(tmp_path, db_bytes=DUMP, vol_bytes=ARCHIVE)

    completed = _run(env)

    everything = completed.stdout + completed.stderr + json.dumps(_documents(env))
    assert SECRET not in everything
    assert "AKIAEXAMPLE" not in everything
    assert "bucket" not in json.dumps(_documents(env)), "documents carry no bucket name"
    assert PREFIX not in json.dumps(_documents(env)), "documents carry no prefix"
