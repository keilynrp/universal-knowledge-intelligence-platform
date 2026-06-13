from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.scripts.validate_restore import (
    _parser,
    build_report,
    configure_read_only_connection,
    install_read_only_guard,
    main,
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


@pytest.mark.parametrize(
    "database_url",
    (
        "postgresql://restore_user:secret@db.internal/ukip",
        "postgresql://restore_user:secret@10.0.0.8/ukip",
    ),
)
def test_unmarked_remote_target_requires_explicit_override(database_url):
    with pytest.raises(ValueError, match="isolated drill"):
        validate_target_url(database_url, allow_production_target=False)


def test_isolated_drill_target_is_accepted():
    validate_target_url(
        "postgresql://restore_user:secret@drill-db.internal/restore_ukip",
        allow_production_target=False,
        expected_host="drill-db.internal",
        expected_database="restore_ukip",
    )


def test_remote_target_must_match_exact_allowlist():
    with pytest.raises(ValueError, match="exact isolated drill allowlist"):
        validate_target_url(
            "postgresql://user:secret@drill-db.internal/restore_ukip",
            allow_production_target=False,
            expected_host="approved-drill-db.internal",
            expected_database="restore_ukip",
        )


@pytest.mark.parametrize(
    "database_url",
    (
        "postgresql://user:secret@contest-db.internal/restore_ukip",
        "postgresql://user:secret@customer-test-db.internal/restore_ukip",
        "postgresql://user:secret@drill-db.internal/customer_test",
    ),
)
def test_incidental_isolation_words_do_not_bypass_target_protection(database_url):
    with pytest.raises(ValueError, match="isolated drill"):
        validate_target_url(database_url, allow_production_target=False)


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


def test_report_fails_when_rpo_or_rto_objective_is_missed():
    report = build_report(
        environment="restore-drill",
        backup_id="backup-001",
        operator="ops@example.test",
        validations=[{"check": "required_tables", "status": "passed"}],
        backup_completed_at=datetime(2026, 6, 11, 12, tzinfo=timezone.utc),
        restore_started_at=datetime(2026, 6, 13, 2, tzinfo=timezone.utc),
        restore_completed_at=datetime(2026, 6, 13, 7, tzinfo=timezone.utc),
    )

    assert report["status"] == "failed"
    objectives = {
        item["check"]: item["status"] for item in report["validations"]
    }
    assert objectives["rpo_objective"] == "failed"
    assert objectives["rto_objective"] == "failed"


def test_report_fails_for_negative_recovery_duration():
    report = build_report(
        environment="restore-drill",
        backup_id="backup-001",
        operator="ops@example.test",
        validations=[{"check": "required_tables", "status": "passed"}],
        backup_completed_at=datetime(2026, 6, 13, 3, tzinfo=timezone.utc),
        restore_started_at=datetime(2026, 6, 13, 2, tzinfo=timezone.utc),
        restore_completed_at=datetime(2026, 6, 13, 1, tzinfo=timezone.utc),
    )

    assert report["status"] == "failed"


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


def test_database_connection_is_put_in_database_enforced_read_only_mode():
    engine = create_engine("sqlite:///:memory:")
    install_read_only_guard(engine)

    with engine.connect() as connection:
        configure_read_only_connection(connection)
        assert connection.exec_driver_sql("PRAGMA query_only").scalar_one() == 1


def test_cli_requires_tenant_fixture_ids_and_uses_environment_url():
    parser = _parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--database-url-env",
                "DRILL_DATABASE_URL",
                "--environment",
                "isolated-drill",
                "--backup-id",
                "backup-001",
                "--operator",
                "operator",
                "--expected-revision",
                "head",
                "--backup-completed-at",
                "2026-06-12T08:00:00Z",
                "--restore-started-at",
                "2026-06-13T02:00:00Z",
                "--output",
                "report.json",
            ]
        )


def test_report_redacts_credentials_embedded_in_string_values():
    report = build_report(
        environment="restore-drill",
        backup_id="backup-001",
        operator="ops@example.test",
        validations=[
            {
                "check": "connection",
                "status": "failed",
                "reason": "postgresql://user:top-secret@drill-db/ukip_restore",
            }
        ],
    )

    serialized = json.dumps(report)
    assert "top-secret" not in serialized
    assert "***:***@" in serialized


@pytest.mark.parametrize(
    "secret_text",
    (
        "postgresql://user:p@ssword@drill-db/restore_ukip",
        "password=top-secret",
        "request failed ?password=top-secret",
        "token: top-secret",
        "access_token=abc123",
        "api_key=abc123",
        "authorization: Bearer abc123",
        "pwd=hunter2",
        "passwd=hunter2",
    ),
)
def test_report_redacts_adversarial_secret_values(secret_text):
    report = build_report(
        environment="restore-drill",
        backup_id="backup-001",
        operator="ops@example.test",
        validations=[
            {
                "check": "connection",
                "status": "failed",
                "reason": secret_text,
            }
        ],
    )

    serialized = json.dumps(report)
    assert "top-secret" not in serialized
    assert "p@ssword" not in serialized
    assert "abc123" not in serialized
    assert "hunter2" not in serialized


def test_runtime_failure_writes_structured_failed_report(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("MISSING_DRILL_URL", raising=False)
    output = tmp_path / "restore-report.json"

    exit_code = main(
        [
            "--database-url-env",
            "MISSING_DRILL_URL",
            "--environment",
            "isolated-drill",
            "--backup-id",
            "backup-001",
            "--operator",
            "operator",
            "--expected-revision",
            "head",
            "--backup-completed-at",
            "2026-06-12T08:00:00Z",
            "--restore-started-at",
            "2026-06-13T02:00:00Z",
            "--tenant-a",
            "1",
            "--tenant-b",
            "2",
            "--expected-target-host",
            "drill-db.internal",
            "--expected-target-database",
            "restore_ukip",
            "--output",
            str(output),
        ]
    )

    report = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert report["status"] == "failed"
    assert report["validations"][0]["check"] == "validator_execution"
