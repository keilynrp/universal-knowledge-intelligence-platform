"""Phase 6 — ML feature readiness: envelopes, leakage, governed labels, lineage."""
from datetime import datetime

from backend import models
from backend.retrospective import features, writer

_MAY = datetime(2026, 5, 15, 12, 0, 0)
_JUN = datetime(2026, 6, 15, 12, 0, 0)
_JUL = datetime(2026, 7, 15, 12, 0, 0)


def _snap(db, subj, valid_at, payload, org_id=None):
    writer.record_snapshot(
        db, snapshot_type="journal_metric", org_id=org_id, subject_type="journal",
        subject_id=subj, valid_at=valid_at,
        idempotency_key=f"{subj}:{valid_at.isoformat()}:{org_id}", payload=payload)
    db.flush()


# ── 6.3 leakage check ───────────────────────────────────────────────────────

def test_leakage_flags_feature_after_label():
    assert features.leakage_violations(_JUN, _MAY, [_JUN])  # feature_ts after label_ts


def test_leakage_flags_source_after_feature_ts():
    problems = features.leakage_violations(_MAY, _JUL, [_JUN])  # source JUN > feature MAY
    assert any("after feature_timestamp" in p for p in problems)


def test_leakage_clean():
    assert features.leakage_violations(_MAY, _JUL, [_MAY]) == []


# ── 6.2 governed labels ─────────────────────────────────────────────────────

def test_governed_label_from_authority_accept(db_session):
    ev = writer.record_event(
        db_session, event_type="authority.accepted", org_id=None,
        domain_object_type="authority_record", domain_object_id="42", occurred_at=_JUN,
        source="authority_review", actor_type="user", actor_id="7",
        idempotency_key="42:accepted", payload={"decision": "accepted"})
    db_session.flush()
    label = features.governed_label_from_decision(ev)
    assert label["value"] == 1 and label["label_kind"] == "governed_decision"
    assert label["lineage"]["event_id"] == ev.event_id
    assert label["label_timestamp"] == _JUN


def test_governed_label_ignores_non_decision(db_session):
    ev = writer.record_event(
        db_session, event_type="journal_metric.computed", org_id=None,
        domain_object_type="journal", domain_object_id="issn:A", occurred_at=_JUN,
        source="test", idempotency_key="A", payload={"nif": 1.0})
    db_session.flush()
    assert features.governed_label_from_decision(ev) is None


# ── 6.1 / 6.4 / 6.5 offline dataset ─────────────────────────────────────────

def test_dataset_envelope_and_no_leakage(db_session):
    _snap(db_session, "issn:A", _MAY, {"nif": 1.0, "nif_bayes": 0.9})
    _snap(db_session, "issn:A", _JUL, {"nif": 1.6})
    ds = features.build_journal_nif_dataset(db_session, org_scope=None)
    assert ds.leakage_ok is True
    assert len(ds.rows) == 1
    row = ds.rows[0]
    assert row.feature_timestamp == _MAY and row.label_timestamp == _JUL
    assert row.feature_timestamp <= row.label_timestamp
    assert row.features["nif"] == 1.0
    assert row.labels["nif_increased"] == 1  # 1.6 > 1.0
    assert row.labels["label_kind"] == "proxy_outcome"
    assert row.lineage["feature_snapshot_id"] and row.lineage["label_snapshot_id"]
    assert row.schema_version == features.SCHEMA_VERSION


def test_features_come_from_earliest_snapshot_only(db_session):
    # 3 snapshots: features from MAY (earliest), label from JUL (latest).
    _snap(db_session, "issn:A", _MAY, {"nif": 1.0})
    _snap(db_session, "issn:A", _JUN, {"nif": 5.0})  # middle — not the feature source
    _snap(db_session, "issn:A", _JUL, {"nif": 0.5})
    ds = features.build_journal_nif_dataset(db_session, org_scope=None)
    row = ds.rows[0]
    assert row.features["nif"] == 1.0            # earliest, not the middle 5.0
    assert row.labels["nif_increased"] == 0      # 0.5 < 1.0


def test_single_snapshot_subject_is_excluded(db_session):
    _snap(db_session, "issn:solo", _MAY, {"nif": 1.0})
    ds = features.build_journal_nif_dataset(db_session, org_scope=None)
    assert ds.rows == []
    assert ds.quality["subjects_considered"] == 1
    assert ds.quality["row_counts"] == 0


def test_dataset_quality_metrics(db_session):
    _snap(db_session, "issn:A", _MAY, {"nif": 1.0})
    _snap(db_session, "issn:A", _JUL, {"nif": 2.0})
    ds = features.build_journal_nif_dataset(db_session, org_scope=None)
    assert ds.quality["row_counts"] == 1
    assert ds.quality["lineage_completeness"] == 1.0
    assert ds.quality["positive_labels"] == 1
    assert ds.quality["leakage_ok"] is True


def test_dataset_is_tenant_scoped(db_session):
    _snap(db_session, "issn:A", _MAY, {"nif": 1.0}, org_id=7)
    _snap(db_session, "issn:A", _JUL, {"nif": 2.0}, org_id=7)
    assert features.build_journal_nif_dataset(db_session, org_scope=1).rows == []
    assert len(features.build_journal_nif_dataset(db_session, org_scope=7).rows) == 1
