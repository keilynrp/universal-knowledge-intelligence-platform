"""Phase 4 — flag-gated incremental migration (shadow/queue), safe-by-default."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend import models
from backend.jobs import migration, runtime, service
from backend.jobs.states import JobStatus


def _fake_schedule(sid=1, org_id=None):
    return SimpleNamespace(id=sid, org_id=org_id,
                           next_run_at=datetime(2026, 7, 12, 9, 0, 0, tzinfo=timezone.utc))


# ── modes & flags (default off) ─────────────────────────────────────────────

def test_default_mode_is_off(monkeypatch):
    monkeypatch.delenv("UKIP_JOBS_REPORTS", raising=False)
    assert migration.job_mode("reports") == migration.JobMode.OFF


def test_mode_parsing(monkeypatch):
    monkeypatch.setenv("UKIP_JOBS_REPORTS", "shadow")
    assert migration.job_mode("reports") == "shadow"
    monkeypatch.setenv("UKIP_JOBS_REPORTS", "bogus")
    assert migration.job_mode("reports") == migration.JobMode.OFF  # invalid → off


def test_mode_predicates():
    assert migration.should_run_inprocess("off") and not migration.should_enqueue("off")
    assert migration.should_run_inprocess("shadow") and migration.should_enqueue("shadow")
    assert not migration.should_run_inprocess("queue") and migration.should_enqueue("queue")


def test_inprocess_schedulers_default_on(monkeypatch):
    monkeypatch.delenv("UKIP_INPROCESS_SCHEDULERS", raising=False)
    assert migration.inprocess_schedulers_enabled() is True
    monkeypatch.setenv("UKIP_INPROCESS_SCHEDULERS", "0")
    assert migration.inprocess_schedulers_enabled() is False


# ── enqueue_occurrence ──────────────────────────────────────────────────────

def test_enqueue_occurrence_off_is_noop(db_session):
    job = migration.enqueue_occurrence(
        db_session, domain="reports", job_type="report.execute", schedule_id=1,
        org_id=None, occurrence_at=_fake_schedule().next_run_at, mode="off")
    assert job is None


def test_enqueue_occurrence_is_idempotent_per_occurrence(db_session):
    sch = _fake_schedule()
    a = migration.enqueue_occurrence(db_session, domain="reports", job_type="report.execute",
                                     schedule_id=sch.id, org_id=None,
                                     occurrence_at=sch.next_run_at, mode="queue")
    db_session.commit()
    b = migration.enqueue_occurrence(db_session, domain="reports", job_type="report.execute",
                                     schedule_id=sch.id, org_id=None,
                                     occurrence_at=sch.next_run_at, mode="queue")
    assert a.id == b.id  # same occurrence → one job
    assert json.loads(a.payload)["mode"] == "queue"


# ── dispatch_due ────────────────────────────────────────────────────────────

def test_dispatch_off_runs_inprocess_only(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_JOBS_REPORTS", "off")
    calls = []
    migration.dispatch_due(db_session, domain="reports", job_type="report.execute",
                           schedule=_fake_schedule(), execute=lambda s, db: calls.append(s.id))
    assert calls == [1]
    assert db_session.query(models.BackgroundJob).count() == 0


def test_dispatch_shadow_runs_inprocess_and_enqueues(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_JOBS_REPORTS", "shadow")
    calls = []
    migration.dispatch_due(db_session, domain="reports", job_type="report.execute",
                           schedule=_fake_schedule(), execute=lambda s, db: calls.append(s.id))
    assert calls == [1]  # in-process still authoritative
    jobs = db_session.query(models.BackgroundJob).all()
    assert len(jobs) == 1 and json.loads(jobs[0].payload)["mode"] == "shadow"


def test_dispatch_queue_enqueues_and_skips_inprocess(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_JOBS_REPORTS", "queue")
    calls = []
    migration.dispatch_due(db_session, domain="reports", job_type="report.execute",
                           schedule=_fake_schedule(), execute=lambda s, db: calls.append(s.id))
    assert calls == []  # in-process skipped
    assert db_session.query(models.BackgroundJob).count() == 1


# ── mode-aware handlers ─────────────────────────────────────────────────────

def test_shadow_handler_has_no_side_effect(db_session, monkeypatch):
    import backend.jobs.handlers  # noqa: F401 — registers handlers
    from backend.routers import scheduled_reports

    executed = []
    monkeypatch.setattr(scheduled_reports, "_execute_report",
                        lambda schedule, db: executed.append(schedule.id))

    # Enqueue a shadow report job, then run it through the worker.
    service.enqueue(db_session, job_type="report.execute", org_id=None,
                    idempotency_key="reports:1:shadow", payload={"schedule_id": 1, "mode": "shadow"})
    db_session.commit()
    done = runtime.run_once(db_session, lease_owner="w1")
    assert done.status == JobStatus.SUCCEEDED
    assert executed == []  # shadow → NO side effect


def test_queue_handler_executes_real_report(db_session, monkeypatch):
    import backend.jobs.handlers  # noqa: F401
    from backend.routers import scheduled_reports

    executed = []
    monkeypatch.setattr(scheduled_reports, "_execute_report",
                        lambda schedule, db: executed.append(schedule.id))
    sch = models.ScheduledReport(name="r", org_id=None)
    db_session.add(sch); db_session.commit()

    service.enqueue(db_session, job_type="report.execute", org_id=None,
                    idempotency_key="reports:queued", payload={"schedule_id": sch.id, "mode": "queue"})
    db_session.commit()
    done = runtime.run_once(db_session, lease_owner="w1")
    assert done.status == JobStatus.SUCCEEDED
    assert executed == [sch.id]  # queue → real execution
