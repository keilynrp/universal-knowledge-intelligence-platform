"""Startup resilience regression (production deploy hardening).

A failure in the DB bootstrap or worker/scheduler init must NOT abort the
FastAPI lifespan — the app has to keep serving so the container healthcheck
(`/health`) passes and the real error is visible in logs instead of an opaque
"container unhealthy" deploy failure.
"""
from __future__ import annotations

import asyncio

import backend.main as m


def _noop_create_task(coro=None, *args, **kwargs):
    # Close the coroutine so we don't emit "coroutine was never awaited".
    if coro is not None and hasattr(coro, "close"):
        coro.close()
    return None


def test_lifespan_survives_bootstrap_failure(monkeypatch):
    monkeypatch.setattr(m, "_startup_side_effects_enabled", lambda: True)

    def boom():
        raise RuntimeError("bootstrap boom")

    monkeypatch.setattr(m, "_run_db_bootstrap", boom)
    monkeypatch.setattr(m.asyncio, "create_task", _noop_create_task)
    monkeypatch.setattr(m.scheduled_imports, "start_scheduler", lambda *a, **k: None)
    monkeypatch.setattr(m.scheduled_reports, "start_scheduler", lambda *a, **k: None)

    async def run():
        async with m.lifespan(m.app):
            return "serving"

    # Despite the bootstrap raising, the lifespan must still enter (yield).
    assert asyncio.run(run()) == "serving"


def test_lifespan_survives_worker_init_failure(monkeypatch):
    monkeypatch.setattr(m, "_startup_side_effects_enabled", lambda: True)
    monkeypatch.setattr(m, "_run_db_bootstrap", lambda: None)

    def boom(*a, **k):
        raise RuntimeError("scheduler boom")

    # A scheduler that throws during init must not abort startup.
    monkeypatch.setattr(m.asyncio, "create_task", _noop_create_task)
    monkeypatch.setattr(m.scheduled_imports, "start_scheduler", boom)

    async def run():
        async with m.lifespan(m.app):
            return "serving"

    assert asyncio.run(run()) == "serving"
    # engine_client attribute is always defined for handlers/cleanup.
    assert hasattr(m.app.state, "engine_client")
