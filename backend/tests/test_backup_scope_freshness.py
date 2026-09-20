"""Backup freshness must be judged per scope, not by whichever job ran last.

Found on 2026-09-20 (#320 Phase C): recording the `ukip_static_data` volume
archive alongside the PostgreSQL dump moved `latest_backup` to the volume,
because `latest_completed_backup()` took the newest completed event of any
kind and the volume job runs five minutes after the database job.

The failure that hides: a failing database dump plus a succeeding volume job
keeps `GET /ops/backups/status` at `ok` with a small `age_hours`, while a
10 KB tar of an empty directory holds the freshness signal green and the
database goes unbacked. Scope used to live only inside free-text `evidence`,
which the evaluator never reads.

So scope is now a first-class field, the database scope governs the overall
verdict, and the volume evidence is still reported — just not as the thing
that decides freshness.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.backup_assurance import (
    classify_legacy_scope,
    latest_completed_backup,
    record_event,
)

ENV = "scope-tests"


def _event(db, *, scope, hours_ago, backup_id, provider="dokploy", **extra):
    completed = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    event = record_event(
        db,
        event_type="backup",
        status=extra.pop("status", "completed"),
        environment=ENV,
        provider=provider,
        backup_id=backup_id,
        started_at=completed - timedelta(minutes=1),
        completed_at=completed,
        operator="tester",
        size_bytes=extra.pop("size_bytes", 1024),
        integrity_ref="sha256:" + "0" * 64,
        scope=scope,
        **extra,
    )
    db.commit()
    return event


# ── The field itself ─────────────────────────────────────────────────────────

def test_scope_defaults_to_database(db_session):
    event = _event(db_session, scope=None, hours_ago=1, backup_id="pg/a.sql.gz")
    assert event.scope == "database"


def test_scope_is_persisted_when_given(db_session):
    event = record_event(
        db_session,
        event_type="backup",
        status="completed",
        environment=ENV,
        provider="dokploy volume backup",
        backup_id="static/a.tar",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        operator="tester",
        scope="volume",
    )
    db_session.commit()
    assert event.scope == "volume"


def test_an_unknown_scope_is_refused(db_session):
    with pytest.raises(ValueError, match="scope"):
        record_event(
            db_session,
            event_type="backup",
            status="completed",
            environment=ENV,
            provider="dokploy",
            backup_id="pg/a.sql.gz",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            operator="tester",
            scope="everything",
        )


# ── The query the evaluator depends on ───────────────────────────────────────

def test_latest_completed_backup_ignores_a_newer_volume_archive(db_session):
    # The regression itself: the volume job finishes after the database job.
    _event(db_session, scope="database", hours_ago=2, backup_id="pg/older.sql.gz")
    _event(db_session, scope="volume", hours_ago=1, backup_id="static/newer.tar")

    latest = latest_completed_backup(db_session, ENV)

    assert latest.backup_id == "pg/older.sql.gz"
    assert latest.scope == "database"


def test_latest_completed_backup_can_be_asked_for_the_volume_scope(db_session):
    _event(db_session, scope="database", hours_ago=2, backup_id="pg/older.sql.gz")
    _event(db_session, scope="volume", hours_ago=1, backup_id="static/newer.tar")

    latest = latest_completed_backup(db_session, ENV, scope="volume")

    assert latest.backup_id == "static/newer.tar"


# ── The endpoint verdict ─────────────────────────────────────────────────────

def test_a_fresh_volume_archive_cannot_mask_a_stale_database_dump(
    client, auth_headers, db_session, monkeypatch
):
    monkeypatch.setenv("UKIP_BACKUP_ENVIRONMENT", ENV)
    _event(db_session, scope="database", hours_ago=30, backup_id="pg/stale.sql.gz")
    _event(db_session, scope="volume", hours_ago=0.2, backup_id="static/fresh.tar")

    body = client.get(f"/ops/backups/status?environment={ENV}", headers=auth_headers).json()

    assert body["status"] == "critical"
    assert "backup_stale" in body["reason_codes"]
    assert body["latest_backup"]["backup_id"] == "pg/stale.sql.gz"


def test_the_volume_archive_is_still_reported_as_its_own_evidence(
    client, auth_headers, db_session
):
    _event(db_session, scope="database", hours_ago=2, backup_id="pg/fresh.sql.gz")
    _event(db_session, scope="volume", hours_ago=1, backup_id="static/fresh.tar")

    body = client.get(f"/ops/backups/status?environment={ENV}", headers=auth_headers).json()

    assert body["latest_backup"]["backup_id"] == "pg/fresh.sql.gz"
    assert body["latest_volume_backup"]["backup_id"] == "static/fresh.tar"
    assert body["latest_backup"]["scope"] == "database"


def test_a_missing_volume_backup_does_not_affect_the_verdict(
    client, auth_headers, db_session
):
    # Volume coverage is reported, not required: an environment without one is
    # not thereby unhealthy.
    _event(db_session, scope="database", hours_ago=2, backup_id="pg/fresh.sql.gz")

    body = client.get(f"/ops/backups/status?environment={ENV}", headers=auth_headers).json()

    assert body["latest_volume_backup"] is None
    assert "backup_stale" not in body["reason_codes"]


def test_posting_an_event_accepts_and_echoes_the_scope(client, auth_headers):
    now = datetime.now(timezone.utc)
    payload = {
        "event_type": "backup",
        "status": "completed",
        "environment": ENV,
        "provider": "dokploy volume backup",
        "backup_id": "static/posted.tar",
        "scope": "volume",
        "started_at": (now - timedelta(minutes=1)).isoformat(),
        "completed_at": now.isoformat(),
    }

    response = client.post("/ops/backups/events", json=payload, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["scope"] == "volume"


def test_posting_an_unknown_scope_is_rejected(client, auth_headers):
    now = datetime.now(timezone.utc)
    payload = {
        "event_type": "backup",
        "status": "completed",
        "environment": ENV,
        "provider": "dokploy",
        "backup_id": "pg/posted.sql.gz",
        "scope": "everything",
        "started_at": (now - timedelta(minutes=1)).isoformat(),
        "completed_at": now.isoformat(),
    }

    assert client.post("/ops/backups/events", json=payload, headers=auth_headers).status_code == 422


# ── Backfilling the rows written before the column existed ───────────────────

@pytest.mark.parametrize(
    ("provider", "backup_id", "expected"),
    [
        ("aws-s3 via dokploy postgres backup", "ukip-db/pg/2026-09-20.sql.gz", "database"),
        ("aws-s3 via dokploy volume backup", "app/static/vol-2026-09-20.tar", "volume"),
        ("dokploy", "app/static/ukip_static_data-2026-09-20.tar", "volume"),
        ("dokploy", None, "database"),
    ],
)
def test_legacy_rows_are_classified_from_what_they_recorded(provider, backup_id, expected):
    # Production already holds three rows written before this column existed:
    # two dumps and one volume archive. The migration backfills them with this
    # rule rather than defaulting everything to "database", which would have
    # mislabelled the archive as the thing that governs freshness.
    assert classify_legacy_scope(provider=provider, backup_id=backup_id) == expected


# ── The migration's SQL must agree with the Python classifier ────────────────

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "b8c9d0e1f2a3_backup_event_scope.py"
)

LEGACY_ROWS = [
    # The three rows production already holds, plus two shapes the rule must
    # not get wrong.
    ("aws-s3 via dokploy postgres backup", "ukip-db/pg/2026-09-19T03-00-00-134Z.sql.gz"),
    ("aws-s3 via dokploy postgres backup", "ukip-db/pg/2026-09-20T03-00-00-076Z.sql.gz"),
    ("aws-s3 via dokploy volume backup", "app_ukip-backend/static/vol-2026-09-20T03-05-00-066Z.tar"),
    ("dokploy", None),
    ("dokploy", "pg/plain.sql.gz"),
]


def _backfill_sql() -> str:
    source = MIGRATION.read_text(encoding="utf-8")
    start = source.index("UPDATE backup_assurance_events")
    end = source.index('"""', start)
    return source[start:end].strip()


def test_the_backfill_sql_classifies_exactly_like_the_python_rule(tmp_path):
    connection = sqlite3.connect(tmp_path / "legacy.db")
    connection.execute(
        "CREATE TABLE backup_assurance_events "
        "(id INTEGER PRIMARY KEY, provider TEXT, backup_id TEXT, scope TEXT NOT NULL DEFAULT 'database')"
    )
    connection.executemany(
        "INSERT INTO backup_assurance_events (provider, backup_id) VALUES (?, ?)",
        LEGACY_ROWS,
    )

    connection.execute(_backfill_sql())

    rows = connection.execute(
        "SELECT provider, backup_id, scope FROM backup_assurance_events ORDER BY id"
    ).fetchall()
    connection.close()

    assert [row[2] for row in rows] == [
        classify_legacy_scope(provider=provider, backup_id=backup_id)
        for provider, backup_id in LEGACY_ROWS
    ]
    # And concretely: the volume archive production already stored is the one
    # row that must move off the default.
    assert [row[2] for row in rows] == ["database", "database", "volume", "database", "database"]
