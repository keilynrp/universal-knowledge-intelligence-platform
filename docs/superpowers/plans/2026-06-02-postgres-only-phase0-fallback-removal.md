# Postgres-Only — Phase 0: SQLite Fallback Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PostgreSQL the only *default/production* persistence engine by removing the SQLite default and adding a boot guard, with **zero impact** on the existing SQLite-based test suite.

**Architecture:** UKIP already defaults to Postgres in practice (`db_config.default_database_url()` returns a `postgresql+psycopg2://` URL when `UKIP_DB_MODE` is unset). This phase removes the residual SQLite *default* branch, adds a loud production boot guard if the resolved engine is still SQLite, and cleans up user-facing "FTS5" copy. It deliberately **keeps** the explicit-`DATABASE_URL` passthrough alive so the SQLite test harness and any local dev usage keep working untouched.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Next.js (i18n copy only).

---

## Scope

### In scope (100% test-safe)
1. `backend/db_config.py` — remove the SQLite branch from `default_database_url()`; keep `resolve_database_url()` passthrough of an explicit `DATABASE_URL`.
2. `backend/main.py` lifespan — add a production boot guard that logs a loud warning when the resolved engine is SQLite (side-effects are already gated off in tests, so no test impact).
3. User-facing copy — drop "SQLite FTS5" wording in OpenAPI tag, frontend i18n strings, developer page, and `API.md`.
4. `backend/tests/test_sprint4.py` — retarget the stale `test_database_url_defaults_to_sqlite` to assert the new Postgres production default.

### Explicitly OUT of scope (deferred to the "expensive" test-tier level)
These are **load-bearing for the still-alive SQLite test/dev passthrough** and must NOT be touched here:
- `backend/routers/search.py` — `_IS_SQLITE` / `_fts_query` / FTS5 branch. Collapsing to `tsvector` forces `test_sprint53` + the FTS parts of `test_sprint94` onto Postgres.
- `backend/database.py` — the `is_sqlite` engine-kwargs branch. Removing it breaks module import under the in-memory SQLite test engine (`create_engine("sqlite:///:memory:", pool_size=...)` raises).
- `alembic/versions/0001_baseline.py` conditional FTS5 DDL + `alembic/env.py` `_FTS5_PREFIXES` / `_is_sqlite` — still reachable via an explicit `DATABASE_URL=sqlite://` in dev.
- `backend/tests/conftest.py` SQLite/StaticPool harness.

**Why deferred:** The user chose "solo Fase 0 libre". Collapsing search would regress search-test coverage in the fast SQLite suite until CI runs Postgres. That is a separate, larger piece of work.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `backend/db_config.py` | Resolve the runtime DB URL | Remove SQLite default branch |
| `backend/main.py` | App lifespan / startup guards | Add SQLite-in-production warning |
| `backend/tests/test_sprint4.py` | DB-wiring unit tests | Retarget the default-engine assertion |
| `backend/tests/test_phase0_pg_default.py` | New: lock in the Postgres-default contract | Create |
| `main.py` OpenAPI tag / `frontend/...` / `API.md` | User-facing copy | Drop "FTS5" wording |

---

## Task 1: Make PostgreSQL the only resolved default

**Files:**
- Modify: `backend/db_config.py:4-18`
- Test: `backend/tests/test_phase0_pg_default.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_phase0_pg_default.py
"""Phase 0 — Postgres-only default contract.

These tests assert behaviour of the pure resolution functions in isolation by
manipulating os.environ directly. They do NOT import backend.database (whose
module-level URL is already frozen to the test sqlite URL by conftest).
"""
import importlib
import os


def _reload_db_config():
    import backend.db_config as db_config
    return importlib.reload(db_config)


def test_default_url_is_postgres_when_db_mode_unset(monkeypatch):
    monkeypatch.delenv("UKIP_DB_MODE", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_config = _reload_db_config()
    url = db_config.default_database_url()
    assert url.startswith("postgresql+psycopg2://")


def test_default_url_is_postgres_even_when_db_mode_sqlite(monkeypatch):
    """UKIP_DB_MODE=sqlite no longer forces a sqlite default — the SQLite
    fallback was removed. Tests/dev must pass an explicit DATABASE_URL instead."""
    monkeypatch.setenv("UKIP_DB_MODE", "sqlite")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_config = _reload_db_config()
    url = db_config.default_database_url()
    assert url.startswith("postgresql+psycopg2://")
    assert "sqlite" not in url


def test_explicit_database_url_is_still_honoured(monkeypatch):
    """resolve_database_url() must pass an explicit DATABASE_URL through
    untouched — this is what keeps the SQLite test harness working."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    db_config = _reload_db_config()
    assert db_config.resolve_database_url() == "sqlite:///:memory:"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv\Scripts\python -m pytest backend/tests/test_phase0_pg_default.py -v`
Expected: `test_default_url_is_postgres_even_when_db_mode_sqlite` FAILS (current code returns a sqlite URL when `UKIP_DB_MODE=sqlite`).

- [ ] **Step 3: Remove the SQLite default branch**

Replace the body of `default_database_url()` in `backend/db_config.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv\Scripts\python -m pytest backend/tests/test_phase0_pg_default.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db_config.py backend/tests/test_phase0_pg_default.py
git commit -m "refactor: remove SQLite default from db_config (Postgres-only Phase 0)"
```

---

## Task 2: Production boot guard for SQLite

**Files:**
- Modify: `backend/main.py` (lifespan startup block, after the env-var guards ~line 244, before the `_startup_side_effects_enabled()` early return)
- Test: `backend/tests/test_phase0_pg_default.py` (append)

> **Why this placement:** The guard must run only on real startup. Tests set
> `UKIP_SKIP_STARTUP_SIDE_EFFECTS=1`, but place the guard BEFORE that early
> return so it still logs in production while staying a pure log call (no DB
> work) that is harmless if it ever runs. We assert it via caplog using a small
> extracted helper so we never trigger real startup side-effects in tests.

- [ ] **Step 1: Write the failing test (append to test_phase0_pg_default.py)**

```python
import logging


def test_sqlite_engine_emits_production_warning(caplog):
    from backend.main import warn_if_sqlite_engine
    with caplog.at_level(logging.WARNING):
        warn_if_sqlite_engine("sqlite:///./sql_app.db")
    assert any("SQLite" in r.message and "production" in r.message.lower()
               for r in caplog.records)


def test_postgres_engine_emits_no_warning(caplog):
    from backend.main import warn_if_sqlite_engine
    with caplog.at_level(logging.WARNING):
        warn_if_sqlite_engine("postgresql+psycopg2://u:p@h:5432/db")
    assert not any("SQLite" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python -m pytest backend/tests/test_phase0_pg_default.py -k sqlite_engine -v`
Expected: FAIL with `ImportError: cannot import name 'warn_if_sqlite_engine'`.

- [ ] **Step 3: Add the helper and call it in lifespan**

In `backend/main.py`, add the helper near the other module-level startup helpers (after `_startup_side_effects_enabled`):

```python
def warn_if_sqlite_engine(database_url: str) -> None:
    """Loudly warn when the runtime resolved to SQLite.

    SQLite is no longer a supported production engine. It remains usable for
    local dev/tests only via an explicit DATABASE_URL. This is a pure log call
    with no side effects, safe to invoke on every boot.
    """
    if database_url.startswith("sqlite"):
        logger.warning(
            "⚠ Resolved DB engine is SQLite (%s). SQLite is NOT supported in "
            "production — set DATABASE_URL / POSTGRES_* to a PostgreSQL instance.",
            database_url,
        )
```

Then inside `lifespan`, immediately after the existing `ALLOWED_ORIGINS=*` warning block and BEFORE the `if not _startup_side_effects_enabled():` early return, add:

```python
    warn_if_sqlite_engine(database.SQLALCHEMY_DATABASE_URL)
```

(`database` is already imported at the top of `main.py`.)

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\python -m pytest backend/tests/test_phase0_pg_default.py -k engine -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_phase0_pg_default.py
git commit -m "feat: warn loudly when production resolves to SQLite engine"
```

---

## Task 3: Retarget the stale default-engine test

**Files:**
- Modify: `backend/tests/test_sprint4.py:51-54`

- [ ] **Step 1: Update the stale test**

Replace `test_database_url_defaults_to_sqlite` with a name + body that reflects reality. The test-env value stays SQLite (conftest), but the *production default* is now Postgres:

```python
def test_test_env_uses_sqlite_but_production_default_is_postgres():
    """In the test env the module URL is SQLite (conftest sets DATABASE_URL),
    but the production default (no DATABASE_URL) is now PostgreSQL."""
    from backend import database
    from backend.db_config import default_database_url
    assert "sqlite" in database.SQLALCHEMY_DATABASE_URL  # test env
    assert default_database_url().startswith("postgresql")  # production default
```

- [ ] **Step 2: Run the updated test**

Run: `.venv\Scripts\python -m pytest backend/tests/test_sprint4.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_sprint4.py
git commit -m "test: retarget stale sqlite-default assertion to Postgres default"
```

---

## Task 4: Drop "SQLite FTS5" user-facing copy

> Cosmetic only — no behavioural change. The search engine is dialect-aware at
> runtime; the copy should not advertise a specific engine.

**Files:**
- Modify: `backend/main.py:363` (OpenAPI tag)
- Modify: `frontend/app/i18n/translations.ts:2509` (EN) and `:5909` (ES)
- Modify: `frontend/app/developer/page.tsx:45`
- Modify: `API.md:622`

- [ ] **Step 1: Update the OpenAPI tag** (`backend/main.py:363`)

From:
```python
    {"name": "search",         "description": "Full-text search index (FTS5) across entities and annotations."},
```
To:
```python
    {"name": "search",         "description": "Full-text search index across entities and annotations."},
```

- [ ] **Step 2: Update i18n strings** (`frontend/app/i18n/translations.ts`)

Line 2509 (EN): `'Powered by SQLite FTS5 full-text search'` → `'Powered by PostgreSQL full-text search'`
Line 5909 (ES): `'Impulsado por búsqueda de texto completo SQLite FTS5'` → `'Impulsado por búsqueda de texto completo PostgreSQL'`

- [ ] **Step 3: Update developer page** (`frontend/app/developer/page.tsx:45`)

`{ name: "search", description: "Full-text search (FTS5)" }` → `{ name: "search", description: "Full-text search" }`

- [ ] **Step 4: Update API.md** (`API.md:622`)

`Full-text search (FTS5) across entities and annotations` → `Full-text search across entities and annotations`

- [ ] **Step 5: Sanity-check no stray "SQLite FTS5" user copy remains**

Run: `git grep -n "SQLite FTS5"` (expect no matches in `frontend/` or docs surfaced to users; backend code comments in `search.py`/`conftest.py`/alembic are out of scope and may remain).

- [ ] **Step 6: Commit**

```bash
git add backend/main.py frontend/app/i18n/translations.ts frontend/app/developer/page.tsx API.md
git commit -m "docs: drop SQLite-specific FTS5 wording from user-facing copy"
```

---

## Task 5: Full-suite verification

- [ ] **Step 1: Run the backend suite (SQLite test harness, unchanged)**

Run: `.venv\Scripts\python -m pytest backend/tests -q`
Expected: All previously-passing tests still pass. No new failures. The SQLite test harness is untouched by Phase 0.

- [ ] **Step 2: Confirm the boot guard fires in a simulated production run**

Run:
```bash
set DATABASE_URL=sqlite:///./sql_app.db
.venv\Scripts\python -c "from backend.main import warn_if_sqlite_engine; warn_if_sqlite_engine('sqlite:///./x.db')"
```
Expected: a WARNING line mentioning SQLite + production on stderr.

- [ ] **Step 3: Final commit / no-op**

If everything is green, the per-task commits already capture the work. Nothing further to commit.

---

## Definition of Done

- [ ] `default_database_url()` returns a PostgreSQL URL regardless of `UKIP_DB_MODE`.
- [ ] An explicit `DATABASE_URL` (including `sqlite://`) is still honoured by `resolve_database_url()`.
- [ ] Production boot logs a clear SQLite warning; tests do not (side-effects gated).
- [ ] No user-facing copy advertises "SQLite FTS5".
- [ ] Full backend suite passes unchanged (no test-tier migration performed).
- [ ] `search.py`, `database.py` engine branch, Alembic baseline, and conftest are untouched (deferred to the test-tier level).
