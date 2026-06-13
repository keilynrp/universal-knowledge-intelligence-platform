"""Read-only validation for an isolated UKIP database restore."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend import models
from backend.tenant_access import scope_query_to_org


REQUIRED_TABLES = (
    "alembic_version",
    "users",
    "organizations",
    "organization_members",
    "raw_entities",
    "audit_logs",
    "data_lifecycle_events",
    "backup_assurance_events",
)
_PRODUCTION_MARKERS = ("prod", "production", "primary", "live")
_ISOLATED_TARGET_MARKERS = ("drill", "restore", "recovery", "test", "staging")
_SECRET_KEY_MARKERS = (
    "secret",
    "password",
    "token",
    "credential",
    "database_url",
    "connection_string",
)
_READ_ONLY_PREFIXES = ("SELECT", "SHOW", "EXPLAIN")
_URL_CREDENTIALS = re.compile(
    r"([a-z][a-z0-9+.-]*://[^:/@\s]+):([^@\s]+)@",
    re.IGNORECASE,
)


def validate_target_url(
    database_url: str, allow_production_target: bool
) -> None:
    """Reject URLs whose host or database name looks production-like."""
    parsed = urlsplit(database_url)
    target_identity = " ".join(
        part for part in (parsed.hostname, unquote(parsed.path.lstrip("/"))) if part
    ).lower()
    if not target_identity:
        raise ValueError("Database URL must identify a host or database")
    production_like = any(
        marker in target_identity for marker in _PRODUCTION_MARKERS
    )
    isolated_like = any(
        marker in target_identity for marker in _ISOLATED_TARGET_MARKERS
    )
    local_target = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not allow_production_target and (production_like or not (isolated_like or local_target)):
        raise ValueError(
            "Refusing production-like or unmarked target that is not clearly "
            "an isolated drill database; "
            "use --allow-production-target only with separate incident approval"
        )


def install_read_only_guard(engine: Engine) -> None:
    """Block DDL and DML at the SQLAlchemy execution boundary."""

    @event.listens_for(engine, "before_cursor_execute")
    def _reject_mutation(
        connection,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        normalized = statement.lstrip().upper()
        is_read_only = normalized.startswith(_READ_ONLY_PREFIXES)
        if normalized in {"PRAGMA QUERY_ONLY", "PRAGMA QUERY_ONLY = ON"}:
            is_read_only = True
        if normalized == "SET TRANSACTION READ ONLY":
            is_read_only = True
        if not is_read_only or ";" in normalized.rstrip(";"):
            raise RuntimeError("Restore validation connection is strictly read-only")


def configure_read_only_connection(connection) -> None:
    """Ask the database itself to enforce a read-only validation session."""
    dialect = connection.dialect.name
    if dialect == "postgresql":
        connection.exec_driver_sql("SET TRANSACTION READ ONLY")
    elif dialect == "sqlite":
        connection.exec_driver_sql("PRAGMA query_only = ON")
    else:
        raise RuntimeError(f"Unsupported restore-validation dialect: {dialect}")


def validate_required_tables(inspector) -> list[dict[str, Any]]:
    available = set(inspector.get_table_names())
    return [
        {
            "check": f"required_table:{table}",
            "status": "passed" if table in available else "failed",
        }
        for table in REQUIRED_TABLES
    ]


def validate_alembic_revision(
    connection, expected_revision: str | None
) -> dict[str, Any]:
    try:
        actual_revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
    except Exception as exc:
        return {
            "check": "alembic_revision",
            "status": "failed",
            "expected_revision": expected_revision,
            "actual_revision": None,
            "reason": f"revision_unavailable:{type(exc).__name__}",
        }

    matches = expected_revision is None or actual_revision == expected_revision
    return {
        "check": "alembic_revision",
        "status": "passed" if matches and actual_revision else "failed",
        "expected_revision": expected_revision,
        "actual_revision": actual_revision,
    }


def validate_tenant_isolation(
    session: Session, tenant_a: int, tenant_b: int
) -> dict[str, Any]:
    """Verify restored fixture tenants remain separated by UKIP query scoping."""
    if tenant_a == tenant_b:
        return {
            "check": "tenant_isolation",
            "status": "failed",
            "cross_tenant_rows": 0,
            "reason": "tenant_ids_must_differ",
        }

    existing_tenants = {
        row[0]
        for row in (
            session.query(models.Organization.id)
            .filter(models.Organization.id.in_((tenant_a, tenant_b)))
            .all()
        )
    }
    scoped_a = scope_query_to_org(
        session.query(models.UniversalEntity), models.UniversalEntity, tenant_a
    ).all()
    scoped_b = scope_query_to_org(
        session.query(models.UniversalEntity), models.UniversalEntity, tenant_b
    ).all()
    cross_tenant_rows = sum(row.org_id != tenant_a for row in scoped_a) + sum(
        row.org_id != tenant_b for row in scoped_b
    )
    fixtures_present = (
        existing_tenants == {tenant_a, tenant_b} and bool(scoped_a) and bool(scoped_b)
    )

    return {
        "check": "tenant_isolation",
        "status": (
            "passed" if fixtures_present and cross_tenant_rows == 0 else "failed"
        ),
        "tenant_fixture_count": len(existing_tenants),
        "tenant_a_entity_count": len(scoped_a),
        "tenant_b_entity_count": len(scoped_b),
        "cross_tenant_rows": cross_tenant_rows,
    }


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hours_between(start: datetime, end: datetime) -> float:
    return round((_as_utc(end) - _as_utc(start)).total_seconds() / 3600, 3)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _redact(item)
            for key, item in value.items()
            if not any(marker in str(key).lower() for marker in _SECRET_KEY_MARKERS)
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _URL_CREDENTIALS.sub(r"\1:***@", value)
    return value


def build_report(
    *,
    environment: str,
    backup_id: str,
    operator: str,
    validations: list[dict[str, Any]],
    backup_completed_at: datetime | None = None,
    restore_started_at: datetime | None = None,
    restore_completed_at: datetime | None = None,
) -> dict[str, Any]:
    objective_validations: list[dict[str, Any]] = []
    objectives: dict[str, float] = {}
    if backup_completed_at and restore_started_at:
        achieved_rpo = _hours_between(backup_completed_at, restore_started_at)
        objectives["achieved_rpo_hours"] = achieved_rpo
        objective_validations.append(
            {
                "check": "rpo_objective",
                "status": "passed" if 0 <= achieved_rpo <= 24 else "failed",
                "target_hours": 24,
                "achieved_hours": achieved_rpo,
            }
        )
    if restore_started_at and restore_completed_at:
        achieved_rto = _hours_between(restore_started_at, restore_completed_at)
        objectives["achieved_rto_hours"] = achieved_rto
        objective_validations.append(
            {
                "check": "rto_objective",
                "status": "passed" if 0 <= achieved_rto <= 4 else "failed",
                "target_hours": 4,
                "achieved_hours": achieved_rto,
            }
        )

    sanitized_validations = _redact(validations + objective_validations)
    passed = bool(sanitized_validations) and all(
        result.get("status") == "passed" for result in sanitized_validations
    )

    return {
        "schema_version": 1,
        "status": "passed" if passed else "failed",
        "environment": environment,
        "backup_id": backup_id,
        "operator": operator,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "objectives": objectives,
        "validations": sanitized_validations,
    }


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url-env",
        required=True,
        help="Environment variable containing the database URL",
    )
    parser.add_argument("--environment", required=True)
    parser.add_argument("--backup-id", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--backup-completed-at", required=True, type=_parse_datetime)
    parser.add_argument("--restore-started-at", required=True, type=_parse_datetime)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tenant-a", type=int, required=True)
    parser.add_argument("--tenant-b", type=int, required=True)
    parser.add_argument("--allow-production-target", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    validations: list[dict[str, Any]] = []
    database_url = os.environ.get(args.database_url_env)
    engine = None
    try:
        if not database_url:
            raise ValueError(
                f"Database URL environment variable {args.database_url_env!r} is unset"
            )
        validate_target_url(database_url, args.allow_production_target)
        engine = create_engine(database_url, pool_pre_ping=True)
        install_read_only_guard(engine)
        with engine.connect() as connection:
            configure_read_only_connection(connection)
            validations.extend(validate_required_tables(inspect(connection)))
            validations.append(
                validate_alembic_revision(connection, args.expected_revision)
            )
            session_factory = sessionmaker(
                bind=connection, autoflush=False, expire_on_commit=False
            )
            with session_factory() as session:
                validations.append(
                    validate_tenant_isolation(
                        session, args.tenant_a, args.tenant_b
                    )
                )
    except Exception as exc:
        validations.append(
            {
                "check": "validator_execution",
                "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}",
            }
        )
    finally:
        if engine is not None:
            engine.dispose()

    report = build_report(
        environment=args.environment,
        backup_id=args.backup_id,
        operator=args.operator,
        validations=validations,
        backup_completed_at=args.backup_completed_at,
        restore_started_at=args.restore_started_at,
        restore_completed_at=datetime.now(timezone.utc),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
