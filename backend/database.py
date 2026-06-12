import os
import re

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql.dml import Delete, Update
from sqlalchemy.sql.elements import TextClause

from backend.db_config import resolve_database_url


_BACKUP_ASSURANCE_TABLE = "backup_assurance_events"
_BACKUP_ASSURANCE_MAINTENANCE_OPTION = (
    "_ukip_backup_assurance_test_cleanup"
)
_BACKUP_ASSURANCE_MAINTENANCE_SENTINEL = object()
_BACKUP_ASSURANCE_TEXT_MUTATION = re.compile(
    r"\b(?:update\s+(?:[a-z0-9_]+\.)?|delete\s+from\s+(?:[a-z0-9_]+\.)?)"
    r"backup_assurance_events\b",
    re.IGNORECASE,
)


def _is_backup_assurance_mutation(statement) -> bool:
    if isinstance(statement, (Update, Delete)):
        return statement.table.name == _BACKUP_ASSURANCE_TABLE
    if isinstance(statement, TextClause):
        normalized = re.sub(r'["`\[\]]', "", statement.text)
        return bool(_BACKUP_ASSURANCE_TEXT_MUTATION.search(normalized))
    return False


def _guard_backup_assurance_sql(
    _connection,
    clauseelement,
    _multiparams,
    _params,
    execution_options,
):
    maintenance_value = execution_options.get(
        _BACKUP_ASSURANCE_MAINTENANCE_OPTION
    )
    if maintenance_value is _BACKUP_ASSURANCE_MAINTENANCE_SENTINEL:
        return
    if _is_backup_assurance_mutation(clauseelement):
        raise RuntimeError("BackupAssuranceEvent records are append-only")


def install_backup_assurance_sql_guard(target_engine) -> None:
    """Protect one application/test engine from Core and textual mutations."""
    marker = "_ukip_backup_assurance_guard_installed"
    if getattr(target_engine, marker, False):
        return
    event.listen(target_engine, "before_execute", _guard_backup_assurance_sql)
    setattr(target_engine, marker, True)


def backup_assurance_test_cleanup_statement():
    """Return the sole test-maintenance DELETE allowed for assurance evidence.

    This bypass is intentionally limited to the exact full-table cleanup used
    by pytest isolation. Application code must not use it.
    """
    return text(f"DELETE FROM {_BACKUP_ASSURANCE_TABLE}").execution_options(
        **{
            _BACKUP_ASSURANCE_MAINTENANCE_OPTION:
                _BACKUP_ASSURANCE_MAINTENANCE_SENTINEL
        }
    )


SQLALCHEMY_DATABASE_URL = resolve_database_url()

is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

engine_kwargs = {}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = int(os.environ.get("DB_POOL_SIZE", 20))
    engine_kwargs["max_overflow"] = int(os.environ.get("DB_MAX_OVERFLOW", 10))
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs)
install_backup_assurance_sql_guard(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
