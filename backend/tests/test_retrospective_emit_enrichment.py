"""Phase 3.2 — enrichment lifecycle emits retrospective events.

Unit coverage of ``emit_enrichment_lifecycle`` plus one end-to-end path through
``enrich_single_record`` (the no-title → failed transition, which needs no
provider mocks) to confirm the post-commit wiring fires.
"""
import json

from backend import models
from backend.retrospective import emit


def _events(db):
    return db.query(models.RetrospectiveEvent).all()


def _emit_completed(db, **over):
    from datetime import datetime
    kwargs = dict(
        org_id=None, entity_id=1, status="completed",
        occurred_at=datetime(2026, 7, 11, 10, 0, 0),
        source="openalex", citation_count=42, work_type="article",
    )
    kwargs.update(over)
    emit.emit_enrichment_lifecycle(db, **kwargs)
    db.flush()


def test_flag_off_emits_nothing(db_session, monkeypatch):
    monkeypatch.delenv("UKIP_RETRO_EVENTS", raising=False)
    _emit_completed(db_session)
    assert _events(db_session) == []


def test_completed_event(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _emit_completed(db_session)
    evts = _events(db_session)
    assert len(evts) == 1
    e = evts[0]
    assert e.event_type == "enrichment.completed"
    assert e.domain_object_type == "entity"
    assert e.source == "enrichment_worker"
    payload = json.loads(e.payload)
    assert payload["citation_count"] == 42
    assert payload["work_type"] == "article"


def test_failed_event_carries_reason(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    from datetime import datetime
    emit.emit_enrichment_lifecycle(
        db_session, org_id=5, entity_id=9, status="failed",
        occurred_at=datetime(2026, 7, 11, 10, 0, 0),
        failure_reason="API_ERROR",
    )
    db_session.flush()
    e = _events(db_session)[0]
    assert e.event_type == "enrichment.failed"
    assert e.org_id == 5
    assert json.loads(e.payload)["failure_reason"] == "API_ERROR"


def test_unmapped_status_is_ignored(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _emit_completed(db_session, status="processing")
    assert _events(db_session) == []


def test_non_fatal_on_writer_error(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")

    def _boom(*_a, **_k):
        raise RuntimeError("down")

    monkeypatch.setattr(emit.writer, "record_event", _boom)
    _emit_completed(db_session)  # must not raise
    assert _events(db_session) == []


def test_idempotent_within_run(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _emit_completed(db_session)
    _emit_completed(db_session)  # replay, same occurred_at
    assert len(_events(db_session)) == 1


def test_enrich_single_record_failed_path_emits(db_session, monkeypatch):
    """End-to-end: a record with no title fails and emits enrichment.failed."""
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    from backend import enrichment_worker

    entity = models.RawEntity(primary_label="", domain="science",
                              enrichment_status="pending")
    db_session.add(entity)
    db_session.commit()

    enrichment_worker.enrich_single_record(db_session, entity)

    failed = [e for e in _events(db_session) if e.event_type == "enrichment.failed"]
    assert len(failed) == 1
    assert failed[0].domain_object_id == str(entity.id)
