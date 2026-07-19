"""Database DDL constants for append-only backup assurance evidence."""

BACKUP_ASSURANCE_TABLE = "backup_assurance_events"
SQLITE_UPDATE_TRIGGER = "trg_backup_assurance_events_no_update"
SQLITE_DELETE_TRIGGER = "trg_backup_assurance_events_no_delete"
POSTGRES_FUNCTION = "reject_backup_assurance_event_mutation"
POSTGRES_UPDATE_TRIGGER = "trg_backup_assurance_events_no_update"
POSTGRES_DELETE_TRIGGER = "trg_backup_assurance_events_no_delete"

# NOTE: ``IF NOT EXISTS`` makes SQLite trigger creation idempotent without
# weakening the append-only enforcement. It matters for the test harness, where
# every session multiplexes ONE StaticPool in-memory connection (see
# backend/tests/conftest.py::_backup_assurance_test_cleanup): the cleanup context
# drops these triggers, wipes the tables, then recreates them in ``finally``. If a
# recreate runs while the trigger still exists on the shared connection, a plain
# ``CREATE TRIGGER`` raises "trigger ... already exists" (the flaky teardown).
# Postgres (production) uses the POSTGRES_* statements below and is unaffected.
SQLITE_CREATE_UPDATE_TRIGGER = f"""
CREATE TRIGGER IF NOT EXISTS {SQLITE_UPDATE_TRIGGER}
BEFORE UPDATE ON {BACKUP_ASSURANCE_TABLE}
BEGIN
    SELECT RAISE(ABORT, '{BACKUP_ASSURANCE_TABLE} is append-only');
END
"""

SQLITE_CREATE_DELETE_TRIGGER = f"""
CREATE TRIGGER IF NOT EXISTS {SQLITE_DELETE_TRIGGER}
BEFORE DELETE ON {BACKUP_ASSURANCE_TABLE}
BEGIN
    SELECT RAISE(ABORT, '{BACKUP_ASSURANCE_TABLE} is append-only');
END
"""

POSTGRES_CREATE_FUNCTION = f"""
CREATE FUNCTION {POSTGRES_FUNCTION}()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '{BACKUP_ASSURANCE_TABLE} is append-only';
    RETURN OLD;
END;
$$
"""

POSTGRES_CREATE_UPDATE_TRIGGER = f"""
CREATE TRIGGER {POSTGRES_UPDATE_TRIGGER}
BEFORE UPDATE ON {BACKUP_ASSURANCE_TABLE}
FOR EACH ROW EXECUTE FUNCTION {POSTGRES_FUNCTION}()
"""

POSTGRES_CREATE_DELETE_TRIGGER = f"""
CREATE TRIGGER {POSTGRES_DELETE_TRIGGER}
BEFORE DELETE ON {BACKUP_ASSURANCE_TABLE}
FOR EACH ROW EXECUTE FUNCTION {POSTGRES_FUNCTION}()
"""

POSTGRES_DROP_UPDATE_TRIGGER = (
    f"DROP TRIGGER IF EXISTS {POSTGRES_UPDATE_TRIGGER} "
    f"ON {BACKUP_ASSURANCE_TABLE}"
)
POSTGRES_DROP_DELETE_TRIGGER = (
    f"DROP TRIGGER IF EXISTS {POSTGRES_DELETE_TRIGGER} "
    f"ON {BACKUP_ASSURANCE_TABLE}"
)
POSTGRES_DROP_FUNCTION = f"DROP FUNCTION IF EXISTS {POSTGRES_FUNCTION}()"
