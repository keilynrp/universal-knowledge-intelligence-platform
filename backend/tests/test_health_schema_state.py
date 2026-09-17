"""/health must not report a healthy service on a broken or stale schema.

The startup path is deliberately fail-open: `docker/backend-entrypoint.sh` keeps
starting when `alembic upgrade head` fails, and the lifespan keeps serving when
`_run_db_bootstrap()` raises, so the container healthcheck (`curl -f /health`)
stays green and the real error lands in the logs. Both are right. What was wrong
is that /health then answered `"database": "ok", "status": "ok"` because its only
probe was `SELECT 1` — a service with no tables at all looked healthy.

/health now also reports:

- ``bootstrap``: ``ok`` | ``failed`` | ``skipped`` | ``not_run``, recorded by the
  lifespan.
- ``schema``: ``current`` | ``stale`` | ``unversioned`` | ``unknown``, from the
  same `backend.db_revision` check the entrypoint and /ops/checks use.

A failed bootstrap or a stale/unknown schema degrades ``status``. The HTTP code
stays 200 on purpose: the healthcheck must keep passing so the container stays
up and its logs stay readable. /health is public, so it carries only these
enums — never exception text.
"""
from __future__ import annotations

import asyncio

from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

import backend.main as m
from backend import db_revision
from backend.db_revision import classify_drift, schema_state


def _head() -> str:
    return ScriptDirectory.from_config(db_revision._alembic_config()).get_heads()[0]


def _engine_at(revision: str | None):
    engine = create_engine("sqlite:///:memory:")
    if revision is not None:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)"))
            conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:v)"), {"v": revision})
    return engine


def _noop_create_task(coro=None, *args, **kwargs):
    if coro is not None and hasattr(coro, "close"):
        coro.close()


# ── Pure classification ──────────────────────────────────────────────────────

def test_classify_current():
    assert classify_drift({"current": "a", "heads": ["a"], "is_stale": False, "error": None}) == "current"


def test_classify_stale():
    assert classify_drift({"current": "old", "heads": ["a"], "is_stale": True, "error": None}) == "stale"


def test_classify_missing_version_table_is_unversioned():
    assert classify_drift({"current": None, "heads": ["a"], "is_stale": True, "error": None}) == "unversioned"


def test_classify_inspection_error_is_unknown_even_without_a_revision():
    drift = {"current": None, "heads": [], "is_stale": True, "error": "boom"}
    assert classify_drift(drift) == "unknown"


# ── Live inspection against real databases ───────────────────────────────────

def test_schema_state_fresh_database_is_unversioned():
    assert schema_state(_engine_at(None)) == "unversioned"


def test_schema_state_at_head_is_current():
    assert schema_state(_engine_at(_head())) == "current"


def test_schema_state_behind_head_is_stale():
    assert schema_state(_engine_at("0000000000ff")) == "stale"


# ── /health body ─────────────────────────────────────────────────────────────

def test_health_reports_bootstrap_and_schema_in_the_test_environment(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    # Tests run with UKIP_SKIP_STARTUP_SIDE_EFFECTS=1 and build tables with
    # create_all, so there is no alembic_version table: informative, not degraded.
    assert body["bootstrap"] == "skipped"
    assert body["schema"] == "unversioned"
    assert body["database"] == "ok"
    assert body["status"] == "ok"


def test_failed_bootstrap_degrades_health_but_keeps_http_200(client, monkeypatch):
    monkeypatch.setattr(m.app.state, "db_bootstrap", "failed")
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["bootstrap"] == "failed"
    assert body["database"] == "ok"
    assert body["status"] == "degraded"


def test_stale_schema_degrades_health_but_keeps_http_200(client, monkeypatch):
    monkeypatch.setattr(db_revision, "schema_state", lambda engine: "stale")
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["schema"] == "stale"
    assert resp.json()["status"] == "degraded"


def test_unknown_schema_degrades_health(client, monkeypatch):
    monkeypatch.setattr(db_revision, "schema_state", lambda engine: "unknown")
    body = client.get("/health").json()
    assert body["schema"] == "unknown"
    assert body["status"] == "degraded"


def test_health_never_exposes_inspection_error_text(client, monkeypatch):
    secret = "relation secret_tenant_table does not exist"
    monkeypatch.setattr(
        db_revision,
        "migration_drift",
        lambda engine: {"current": None, "heads": [], "is_stale": True, "error": secret},
    )
    resp = client.get("/health")
    assert resp.json()["schema"] == "unknown"
    assert secret not in resp.text
    assert "secret_tenant_table" not in resp.text


# ── Lifespan records the bootstrap outcome ───────────────────────────────────

def _enter_lifespan() -> str:
    async def run():
        async with m.lifespan(m.app):
            return "serving"

    return asyncio.run(run())


def _stub_side_effects(monkeypatch):
    monkeypatch.setattr(m, "_startup_side_effects_enabled", lambda: True)
    monkeypatch.setattr(m.asyncio, "create_task", _noop_create_task)
    monkeypatch.setattr(m.scheduled_imports, "start_scheduler", lambda *a, **k: None)
    monkeypatch.setattr(m.scheduled_reports, "start_scheduler", lambda *a, **k: None)


def test_lifespan_records_skipped_when_side_effects_are_disabled(monkeypatch):
    monkeypatch.setattr(m.app.state, "db_bootstrap", "not_run", raising=False)
    monkeypatch.setattr(m, "_startup_side_effects_enabled", lambda: False)
    assert _enter_lifespan() == "serving"
    assert m.app.state.db_bootstrap == "skipped"


def test_lifespan_records_ok_when_bootstrap_succeeds(monkeypatch):
    monkeypatch.setattr(m.app.state, "db_bootstrap", "not_run", raising=False)
    _stub_side_effects(monkeypatch)
    monkeypatch.setattr(m, "_run_db_bootstrap", lambda: None)
    assert _enter_lifespan() == "serving"
    assert m.app.state.db_bootstrap == "ok"


def test_lifespan_records_failed_and_still_serves_when_bootstrap_raises(monkeypatch):
    monkeypatch.setattr(m.app.state, "db_bootstrap", "not_run", raising=False)
    _stub_side_effects(monkeypatch)

    def boom():
        raise RuntimeError("no such table: raw_entities")

    monkeypatch.setattr(m, "_run_db_bootstrap", boom)
    assert _enter_lifespan() == "serving"
    assert m.app.state.db_bootstrap == "failed"
