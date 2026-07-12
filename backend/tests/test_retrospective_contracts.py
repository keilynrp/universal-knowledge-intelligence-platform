"""Phase 2 contract tests for the Retrospective Intelligence Layer (ADR-006).

Covers task 2.5: tenant scoping, append-only writes, schema-version validation,
plus idempotency and payload bounds enforced by the writer.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from backend import models
from backend.retrospective import (
    MAX_PAYLOAD_BYTES,
    PayloadTooLargeError,
    SchemaVersionError,
    UnknownFamily,
    record_event,
    record_snapshot,
)
from backend.retrospective.registry import event_family, snapshot_family

_NOW = datetime(2026, 7, 11, 12, 0, 0)


def _event(db, **overrides):
    kwargs = dict(
        event_type="journal_metric.recomputed",
        org_id=12,
        domain_object_type="journal",
        domain_object_id="issn:1234-5678",
        occurred_at=_NOW,
        source="journal_metric_normalizer",
        idempotency_key="job-1:issn:1234-5678",
        payload={"nif": 1.42, "prev_nif": 1.30},
    )
    kwargs.update(overrides)
    rec = record_event(db, **kwargs)
    db.flush()
    return rec


def _snapshot(db, **overrides):
    kwargs = dict(
        snapshot_type="journal_metric",
        org_id=12,
        subject_type="journal",
        subject_id="issn:1234-5678",
        valid_at=_NOW,
        idempotency_key="2026-07-11:issn:1234-5678",
        payload={"nif": 1.42},
    )
    kwargs.update(overrides)
    rec = record_snapshot(db, **kwargs)
    db.flush()
    return rec


# ── Envelope + tenant scope ─────────────────────────────────────────────────

def test_event_records_tenant_scope_and_envelope(db_session):
    rec = _event(db_session)
    assert rec.org_id == 12
    assert rec.event_type == "journal_metric.recomputed"
    assert rec.schema_version == event_family("journal_metric.recomputed").current_version
    assert rec.event_id  # stable UUID assigned
    assert rec.recorded_at is not None


def test_snapshot_records_tenant_scope_and_envelope(db_session):
    rec = _snapshot(db_session)
    assert rec.org_id == 12
    assert rec.snapshot_type == "journal_metric"
    assert rec.valid_at == _NOW
    assert rec.snapshot_id


def test_same_idempotency_key_across_orgs_creates_distinct_rows(db_session):
    a = _event(db_session, org_id=12)
    b = _event(db_session, org_id=99)
    assert a.id != b.id
    assert a.org_id == 12 and b.org_id == 99


def test_platform_scope_none_is_allowed(db_session):
    rec = _event(db_session, org_id=None, idempotency_key="platform-1")
    assert rec.org_id is None


# ── Idempotency ─────────────────────────────────────────────────────────────

def test_event_idempotent_replay_returns_existing(db_session):
    first = _event(db_session)
    second = _event(db_session, payload={"nif": 9.99})  # same key, same org
    assert first.id == second.id
    # payload of the original is preserved (no silent overwrite)
    assert '"nif":1.42' in first.payload
    count = (
        db_session.query(models.RetrospectiveEvent)
        .filter_by(idempotency_key="job-1:issn:1234-5678", org_id=12)
        .count()
    )
    assert count == 1


def test_snapshot_idempotent_replay_returns_existing(db_session):
    first = _snapshot(db_session)
    second = _snapshot(db_session)
    assert first.id == second.id


# ── Schema-version validation ───────────────────────────────────────────────

def test_unregistered_event_type_is_rejected(db_session):
    with pytest.raises(UnknownFamily):
        record_event(
            db_session,
            event_type="totally.unknown",
            org_id=12,
            domain_object_type="journal",
            domain_object_id="x",
            occurred_at=_NOW,
            source="test",
            idempotency_key="k",
            payload={"a": 1},
        )


def test_mismatched_schema_version_is_rejected(db_session):
    with pytest.raises(SchemaVersionError):
        _event(db_session, schema_version=999)


def test_explicit_current_version_is_accepted(db_session):
    current = snapshot_family("journal_metric").current_version
    rec = _snapshot(db_session, schema_version=current)
    assert rec.schema_version == current


# ── Payload bounds ──────────────────────────────────────────────────────────

def test_oversized_payload_is_rejected(db_session):
    big = {"blob": "x" * (MAX_PAYLOAD_BYTES + 1)}
    with pytest.raises(PayloadTooLargeError):
        _event(db_session, payload=big)


# ── Append-only enforcement ─────────────────────────────────────────────────

def test_event_update_is_rejected(db_session):
    rec = _event(db_session)
    db_session.commit()
    rec.payload = '{"tampered":true}'
    with pytest.raises(RuntimeError, match="append-only"):
        db_session.flush()
    db_session.rollback()


def test_event_delete_is_rejected(db_session):
    rec = _event(db_session)
    db_session.commit()
    db_session.delete(rec)
    with pytest.raises(RuntimeError, match="append-only"):
        db_session.flush()
    db_session.rollback()


def test_bulk_update_is_rejected(db_session):
    _event(db_session)
    db_session.commit()
    with pytest.raises(RuntimeError, match="append-only"):
        db_session.execute(
            update(models.RetrospectiveEvent).values(source="hacked")
        )
    db_session.rollback()


def test_snapshot_update_is_rejected(db_session):
    rec = _snapshot(db_session)
    db_session.commit()
    rec.payload = '{"tampered":true}'
    with pytest.raises(RuntimeError, match="append-only"):
        db_session.flush()
    db_session.rollback()
