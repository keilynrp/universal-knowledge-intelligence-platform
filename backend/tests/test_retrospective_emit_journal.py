"""Phase 3.1 — journal-metric normalization emits retrospective events.

Verifies the wiring in ``normalize_impact_factors`` via ``emit_journal_metric_normalized``:
flag gating, computed-vs-recomputed semantics, payload lineage, idempotency, and
the non-fatal contract (an emission failure never breaks normalization).
"""
import json

import pytest

from backend import models
from backend.analyzers.journal_normalization import normalize_impact_factors
from backend.retrospective import emit


def _seed(db, field="Medicine", org_id=None):
    for i, cit in enumerate((5.0, 3.0, 1.0)):
        db.add(
            models.JournalMetric(
                org_id=org_id, issn_l=f"{field[:3]}-{i}", source_id=f"S{i}",
                nif_field=field, two_yr_mean_citedness=cit,
            )
        )
    db.flush()


def _events(db, org_id=None):
    return (
        db.query(models.RetrospectiveEvent)
        .filter(models.RetrospectiveEvent.org_id.is_(org_id) if org_id is None
                else models.RetrospectiveEvent.org_id == org_id)
        .all()
    )


def test_flag_off_emits_nothing(db_session, monkeypatch):
    monkeypatch.delenv("UKIP_RETRO_EVENTS", raising=False)
    _seed(db_session)
    updated = normalize_impact_factors(db_session, None)
    assert updated == 3
    assert _events(db_session) == []


def test_first_normalization_emits_computed(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _seed(db_session)
    normalize_impact_factors(db_session, None)
    evts = _events(db_session)
    assert len(evts) == 3
    assert {e.event_type for e in evts} == {"journal_metric.computed"}
    sample = next(e for e in evts if e.domain_object_id == "issn:Med-0")
    payload = json.loads(sample.payload)
    assert payload["prior_nif"] is None
    assert payload["nif"] > 0
    assert payload["nif_field"] == "Medicine"
    assert sample.source == "journal_normalization"
    assert sample.actor_type == "job"


def test_second_normalization_emits_recomputed(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _seed(db_session)
    normalize_impact_factors(db_session, None)
    db_session.commit()
    # Second deliberate recompute → prior_nif is now populated.
    normalize_impact_factors(db_session, None)
    recomputed = [
        e for e in _events(db_session) if e.event_type == "journal_metric.recomputed"
    ]
    assert len(recomputed) == 3
    payload = json.loads(recomputed[0].payload)
    assert payload["prior_nif"] is not None


def test_emission_is_tenant_scoped(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    _seed(db_session, org_id=7)
    normalize_impact_factors(db_session, 7)
    evts = _events(db_session, org_id=7)
    assert len(evts) == 3
    assert all(e.org_id == 7 for e in evts)


def test_emission_failure_is_non_fatal(db_session, monkeypatch):
    """A writer failure must not break normalization or lose NIF updates."""
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")

    def _boom(*_a, **_k):
        raise RuntimeError("writer down")

    monkeypatch.setattr(emit.writer, "record_event", _boom)
    _seed(db_session)
    updated = normalize_impact_factors(db_session, None)
    assert updated == 3  # operational path unaffected
    rows = db_session.query(models.JournalMetric).all()
    assert all(r.normalized_impact_factor is not None for r in rows)  # NIF persisted
    assert _events(db_session) == []  # nothing emitted


def test_emit_is_idempotent_within_a_run(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_RETRO_EVENTS", "1")
    from datetime import datetime

    now = datetime(2026, 7, 11, 9, 0, 0)
    kwargs = dict(
        org_id=None, issn_l="Med-0", new_nif=1.5, prior_nif=None,
        nif_field="Medicine", field_median=3.0, occurred_at=now, source_id="S0",
    )
    emit.emit_journal_metric_normalized(db_session, **kwargs)
    emit.emit_journal_metric_normalized(db_session, **kwargs)  # replay, same occurred_at
    db_session.flush()
    assert len(_events(db_session)) == 1
