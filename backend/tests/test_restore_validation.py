from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.scripts.validate_restore import (
    build_report,
    install_read_only_guard,
    validate_alembic_revision,
    validate_required_tables,
    validate_target_url,
    validate_tenant_isolation,
)


def test_production_like_url_requires_explicit_override():
    with pytest.raises(ValueError, match="production-like"):
        validate_target_url(
            "postgresql://restore_user:top-secret@prod-db.internal/ukip_production",
            allow_production_target=False,
        )

    validate_target_url(
        "postgresql://restore_user:top-secret@prod-db.internal/ukip_production",
        allow_production_target=True,
    )


def test_missing_required_tables_fails():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        results = validate_required_tables(inspect(connection))

    assert any(result["status"] == "failed" for result in results)
    assert any(
        result["check"] == "required_table:raw_entities"
        and result["status"] == "failed"
        for result in results
    )


def test_alembic_revision_mismatch_fails():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('restored-rev')")
        )
        result = validate_alembic_revision(connection, "manifest-rev")

    assert result["status"] == "failed"
    assert result["actual_revision"] == "restored-rev"
    assert result["expected_revision"] == "manifest-rev"


def test_cross_tenant_visibility_fails(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        owner = models.User(username="restore-owner", password_hash="x")
        session.add(owner)
        session.flush()
        tenant_a = models.Organization(
            name="Restore A", slug="restore-a", owner_id=owner.id
        )
        tenant_b = models.Organization(
            name="Restore B", slug="restore-b", owner_id=owner.id
        )
        session.add_all([tenant_a, tenant_b])
        session.flush()
        session.add_all(
            [
                models.UniversalEntity(
                    org_id=tenant_a.id, primary_label="Tenant A fixture"
                ),
                models.UniversalEntity(
                    org_id=tenant_b.id, primary_label="Tenant B fixture"
                ),
            ]
        )
        session.commit()

        monkeypatch.setattr(
            "backend.scripts.validate_restore.scope_query_to_org",
            lambda query, model, org_id: query,
        )
        result = validate_tenant_isolation(session, tenant_a.id, tenant_b.id)
    finally:
        session.close()

    assert result["status"] == "failed"
    assert result["cross_tenant_rows"] > 0


def test_passing_report_is_structured_json_and_secret_free():
    report = build_report(
        environment="restore-drill",
        backup_id="backup-001",
        operator="ops@example.test",
        validations=[
            {"check": "required_tables", "status": "passed"},
            {"check": "alembic_revision", "status": "passed"},
            {"check": "tenant_isolation", "status": "passed"},
        ],
    )

    serialized = json.dumps(report, sort_keys=True)
    assert report["status"] == "passed"
    assert report["schema_version"] == 1
    assert "password" not in serialized.lower()
    assert "database_url" not in serialized.lower()
    assert "top-secret" not in serialized


def test_report_includes_achieved_rpo_and_rto():
    report = build_report(
        environment="restore-drill",
        backup_id="backup-001",
        operator="ops@example.test",
        validations=[{"check": "required_tables", "status": "passed"}],
        backup_completed_at=datetime(2026, 6, 12, 8, tzinfo=timezone.utc),
        restore_started_at=datetime(2026, 6, 13, 2, tzinfo=timezone.utc),
        restore_completed_at=datetime(2026, 6, 13, 4, tzinfo=timezone.utc),
    )

    assert report["objectives"]["achieved_rpo_hours"] == 18.0
    assert report["objectives"]["achieved_rto_hours"] == 2.0


def test_read_only_guard_rejects_mutating_sql():
    engine = create_engine("sqlite:///:memory:")
    install_read_only_guard(engine)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        with pytest.raises(RuntimeError, match="read-only"):
            connection.execute(text("CREATE TABLE forbidden (id INTEGER)"))
        with pytest.raises(RuntimeError, match="read-only"):
            connection.execute(
                text(
                    "WITH changed AS (DELETE FROM raw_entities RETURNING id) "
                    "SELECT * FROM changed"
                )
            )
        with pytest.raises(RuntimeError, match="read-only"):
            connection.execute(text("PRAGMA user_version = 1"))
