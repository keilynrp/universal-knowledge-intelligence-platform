import os


def default_database_url() -> str:
    """Build the default PostgreSQL URL from POSTGRES_* env vars.

    SQLite is no longer a supported default engine (Phase 0, 2026-06-02).
    To run against SQLite for local dev/tests, set DATABASE_URL explicitly;
    resolve_database_url() passes it through untouched.
    """
    pg_user = os.environ.get("POSTGRES_USER", "ukip")
    pg_password = os.environ.get("POSTGRES_PASSWORD", "ukip_secret")
    pg_host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    pg_port = os.environ.get("POSTGRES_PORT", "5432")
    pg_db = os.environ.get("POSTGRES_DB", "ukip")
    return f"postgresql+psycopg2://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"


def resolve_database_url() -> str:
    return os.environ.get("DATABASE_URL") or default_database_url()
