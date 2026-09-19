"""B4 (#320): the provider-reachability signal must be refreshable at runtime.

`evaluate_provider_reachability` treats an assertion as stale after 15 minutes
(`PROVIDER_REACHABILITY_MAX_AGE_MINUTES`), but both call sites read it from
`UKIP_BACKUP_PROVIDER_REACHABLE` / `..._AT`, and a running container's
environment cannot be changed — so nothing could ever keep the signal fresh
without restarting the backend every few minutes.

The fix is a second, refreshable channel: a heartbeat document written by a
probe colocated with production (systemd timer / Dokploy schedule) that lists
the backup prefix with the read-only provider credential and drops a small
JSON file into a directory mounted read-only into the container. The
application still holds no provider credential; the file only carries a
boolean and a timestamp.

Everything else is deliberately unchanged: the same 15-minute staleness rule
applies to the file, so a probe that dies makes the signal fail closed on its
own, and the environment variables keep working when no file is configured.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.backup_assurance import (
    PROVIDER_REACHABILITY_MAX_AGE_MINUTES,
    resolve_provider_reachability,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)


def _iso(delta_minutes: float) -> str:
    return (NOW + timedelta(minutes=delta_minutes)).isoformat().replace("+00:00", "Z")


def _document(tmp_path, body, name="reachability.json"):
    path = tmp_path / name
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    return str(path)


# ── The environment channel still works when no file is configured ───────────

def test_without_a_file_the_environment_variables_are_used():
    result = resolve_provider_reachability(
        now=NOW,
        env={
            "UKIP_BACKUP_PROVIDER_REACHABLE": "1",
            "UKIP_BACKUP_PROVIDER_REACHABLE_AT": _iso(-1),
        },
    )
    assert result == {"reachable": True, "source": "timestamped_environment_assertion"}


def test_without_a_file_and_without_variables_it_fails_closed():
    result = resolve_provider_reachability(now=NOW, env={})
    assert result == {"reachable": False, "source": "unknown_default"}


# ── The file channel ─────────────────────────────────────────────────────────

def test_a_fresh_file_makes_the_provider_reachable(tmp_path):
    path = _document(tmp_path, {"reachable": True, "observed_at": _iso(-2)})
    result = resolve_provider_reachability(
        now=NOW, env={"UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": path}
    )
    assert result == {"reachable": True, "source": "timestamped_file_assertion"}


def test_the_file_wins_over_the_environment_variables(tmp_path):
    # The probe is the live signal; a leftover environment assertion from a
    # deploy must not override it.
    path = _document(tmp_path, {"reachable": False, "observed_at": _iso(-1)})
    result = resolve_provider_reachability(
        now=NOW,
        env={
            "UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": path,
            "UKIP_BACKUP_PROVIDER_REACHABLE": "1",
            "UKIP_BACKUP_PROVIDER_REACHABLE_AT": _iso(-1),
        },
    )
    assert result == {"reachable": False, "source": "explicit_unreachable"}


def test_a_stale_file_fails_closed(tmp_path):
    # A probe that stopped running must not leave a permanently green signal.
    path = _document(
        tmp_path,
        {"reachable": True, "observed_at": _iso(-(PROVIDER_REACHABILITY_MAX_AGE_MINUTES + 1))},
    )
    result = resolve_provider_reachability(
        now=NOW, env={"UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": path}
    )
    assert result == {"reachable": False, "source": "stale_file_assertion"}


def test_a_file_from_the_future_fails_closed(tmp_path):
    path = _document(tmp_path, {"reachable": True, "observed_at": _iso(30)})
    result = resolve_provider_reachability(
        now=NOW, env={"UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": path}
    )
    assert result == {"reachable": False, "source": "future_file_assertion"}


def test_a_file_without_a_timestamp_fails_closed(tmp_path):
    path = _document(tmp_path, {"reachable": True})
    result = resolve_provider_reachability(
        now=NOW, env={"UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": path}
    )
    assert result == {"reachable": False, "source": "file_assertion_missing_timestamp"}


def test_malformed_json_fails_closed(tmp_path):
    path = _document(tmp_path, "{not json", name="broken.json")
    result = resolve_provider_reachability(
        now=NOW, env={"UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": path}
    )
    assert result == {"reachable": False, "source": "invalid_reachability_file"}


def test_a_missing_file_fails_closed_and_does_not_fall_back(tmp_path):
    # Falling back to the environment here would turn a dead probe into a green
    # signal, which is exactly the failure mode this channel exists to avoid.
    result = resolve_provider_reachability(
        now=NOW,
        env={
            "UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": str(tmp_path / "absent.json"),
            "UKIP_BACKUP_PROVIDER_REACHABLE": "1",
            "UKIP_BACKUP_PROVIDER_REACHABLE_AT": _iso(-1),
        },
    )
    assert result == {"reachable": False, "source": "missing_reachability_file"}


def test_an_oversized_file_is_rejected_without_reading_it_all(tmp_path):
    path = _document(tmp_path, {"reachable": True, "observed_at": _iso(-1), "pad": "x" * 8192})
    result = resolve_provider_reachability(
        now=NOW, env={"UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": path}
    )
    assert result == {"reachable": False, "source": "invalid_reachability_file"}


def test_a_non_boolean_reachable_value_is_rejected(tmp_path):
    path = _document(tmp_path, {"reachable": "yes", "observed_at": _iso(-1)})
    result = resolve_provider_reachability(
        now=NOW, env={"UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": path}
    )
    assert result == {"reachable": False, "source": "invalid_reachability_file"}


# ── The endpoint uses the channel, and never echoes the path ─────────────────

def test_backup_status_reports_the_file_assertion(client, auth_headers, tmp_path, monkeypatch):
    path = _document(tmp_path, {"reachable": True, "observed_at": datetime.now(timezone.utc).isoformat()})
    monkeypatch.setenv("UKIP_BACKUP_PROVIDER_REACHABILITY_FILE", path)

    response = client.get("/ops/backups/status?environment=production", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["provider_reachable"] is True
    assert body["provider_reachability_source"] == "timestamped_file_assertion"
    assert "provider_unreachable" not in body["reason_codes"]
    # The path is operator infrastructure detail, not part of the API surface.
    assert path not in response.text


# ── The probe writes what the backend reads ──────────────────────────────────
#
# The two halves of B4 are a shell script on the host and a reader in the app.
# Testing them apart would let the document shape drift; these run the real
# script with a stub `aws` on PATH and feed its output to the real reader.

PROBE = Path(__file__).resolve().parents[2] / "scripts" / "ukip-backup-reachability-probe.sh"


def _run_probe(tmp_path, *, aws_exit_code: int):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "aws"
    stub.write_text(f"#!/usr/bin/env bash\nexit {aws_exit_code}\n", encoding="utf-8")
    stub.chmod(0o755)

    out = tmp_path / "signals" / "backup-provider-reachability.json"
    completed = subprocess.run(
        ["bash", str(PROBE)],
        capture_output=True,
        text=True,
        check=False,  # the assertion below reports the probe's own exit code
        env={
            "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
            "UKIP_REACHABILITY_OUT": str(out),
            "S3_BACKUP_ENDPOINT": "https://s3.example.invalid",
            "S3_BACKUP_BUCKET": "bucket",
            "S3_BACKUP_PREFIX": "prefix/",
        },
    )
    assert completed.returncode == 0, completed.stderr
    return out, completed


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required to run the probe")
def test_probe_output_is_read_as_reachable_when_the_provider_answers(tmp_path):
    out, completed = _run_probe(tmp_path, aws_exit_code=0)

    assert "provider_reachable=true" in completed.stdout
    result = resolve_provider_reachability(
        now=datetime.now(timezone.utc),
        env={"UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": str(out)},
    )
    assert result == {"reachable": True, "source": "timestamped_file_assertion"}


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required to run the probe")
def test_probe_records_an_explicit_false_when_the_provider_fails(tmp_path):
    # A failed listing must be recorded, not left as a missing file: the
    # backend then says explicit_unreachable instead of a dead-probe state.
    out, completed = _run_probe(tmp_path, aws_exit_code=1)

    assert "provider_reachable=false" in completed.stdout
    result = resolve_provider_reachability(
        now=datetime.now(timezone.utc),
        env={"UKIP_BACKUP_PROVIDER_REACHABILITY_FILE": str(out)},
    )
    assert result == {"reachable": False, "source": "explicit_unreachable"}


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is required to run the probe")
def test_probe_leaves_no_temporary_file_behind(tmp_path):
    # The document is renamed into place; a leftover .XXXXXX file would mean a
    # reader could catch a half-written document.
    out, _ = _run_probe(tmp_path, aws_exit_code=0)

    assert sorted(child.name for child in out.parent.iterdir()) == [out.name]
