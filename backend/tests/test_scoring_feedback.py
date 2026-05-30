"""Tests for feedback-weighted source priors (Phase 3, Task 10).

Confirming candidates from a source repeatedly should nudge that source's
identifier prior upward (bounded ±0.05); rejecting should nudge it down. The
adjustment is logged in the score `evidence` for auditability and never lets a
single source dominate.
"""
from __future__ import annotations

import pytest

from backend.authority import feedback
from backend.authority.feedback import compute_adjustment
from backend.authority.scoring import compute_score


# ── Pure adjustment math ──────────────────────────────────────────────────────

def test_low_sample_yields_no_adjustment():
    assert compute_adjustment(confirmed=1, rejected=0) == 0.0
    assert compute_adjustment(confirmed=0, rejected=0) == 0.0


def test_all_confirms_saturate_positive_and_bounded():
    adj = compute_adjustment(confirmed=50, rejected=0)
    assert 0.0 < adj <= 0.05
    assert adj == pytest.approx(0.05, abs=0.01)


def test_all_rejects_saturate_negative_and_bounded():
    adj = compute_adjustment(confirmed=0, rejected=50)
    assert -0.05 <= adj < 0.0
    assert adj == pytest.approx(-0.05, abs=0.01)


def test_balanced_feedback_is_neutral():
    assert compute_adjustment(confirmed=20, rejected=20) == pytest.approx(0.0, abs=1e-9)


def test_more_confirms_raise_adjustment_monotonically():
    low = compute_adjustment(confirmed=5, rejected=2)
    high = compute_adjustment(confirmed=50, rejected=2)
    assert high > low


# ── Scoring integration ───────────────────────────────────────────────────────

def test_positive_prior_raises_score_and_logs_evidence():
    high, _, ev_high, _ = compute_score(
        value="John Smith", authority_source="openalex", authority_id="A1",
        canonical_label="John Smith", description=None, source_prior=0.05,
    )
    base, _, _, _ = compute_score(
        value="John Smith", authority_source="openalex", authority_id="A1",
        canonical_label="John Smith", description=None, source_prior=0.0,
    )
    assert high > base
    assert any("feedback_prior" in line for line in ev_high)


def test_negative_prior_lowers_score():
    low, *_ = compute_score(
        value="John Smith", authority_source="openalex", authority_id="A1",
        canonical_label="John Smith", description=None, source_prior=-0.05,
    )
    base, *_ = compute_score(
        value="John Smith", authority_source="openalex", authority_id="A1",
        canonical_label="John Smith", description=None, source_prior=0.0,
    )
    assert low < base


# ── DB-backed aggregation ─────────────────────────────────────────────────────

def test_record_outcome_increments_and_prior_reflects_it(db_session):
    feedback.clear_cache()
    for _ in range(10):
        feedback.record_outcome(
            db_session, "author", "openalex", confirmed=True, org_id=None
        )
    db_session.commit()
    prior = feedback.get_source_prior(db_session, "author", "openalex", org_id=None)
    assert prior > 0.0
    assert prior <= 0.05


def test_rejections_drive_prior_negative(db_session):
    feedback.clear_cache()
    for _ in range(10):
        feedback.record_outcome(
            db_session, "author", "viaf", rejected=True, org_id=None
        )
    db_session.commit()
    prior = feedback.get_source_prior(db_session, "author", "viaf", org_id=None)
    assert prior < 0.0
    assert prior >= -0.05


def test_unknown_pair_prior_is_zero(db_session):
    feedback.clear_cache()
    assert feedback.get_source_prior(db_session, "author", "nope", org_id=None) == 0.0


# ── Endpoint wiring ───────────────────────────────────────────────────────────

def _seed_record(db_session, source="openalex"):
    from backend import models
    rec = models.AuthorityRecord(
        field_name="author", original_value="J Smith",
        authority_source=source, authority_id="A1",
        canonical_label="John Smith", confidence=0.7, status="pending",
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)
    return rec


def test_confirm_endpoint_records_feedback(client, editor_headers, db_session):
    from backend import models
    feedback.clear_cache()
    rec = _seed_record(db_session, "openalex")
    res = client.post(
        f"/authority/records/{rec.id}/confirm", json={}, headers=editor_headers
    )
    assert res.status_code == 200
    row = db_session.query(models.AuthorityScoringFeedback).filter_by(
        field_name="author", authority_source="openalex"
    ).first()
    assert row is not None
    assert row.confirmed >= 1


def test_reject_endpoint_records_feedback(client, editor_headers, db_session):
    from backend import models
    feedback.clear_cache()
    rec = _seed_record(db_session, "dbpedia")
    res = client.post(
        f"/authority/records/{rec.id}/reject", headers=editor_headers
    )
    assert res.status_code == 200
    row = db_session.query(models.AuthorityScoringFeedback).filter_by(
        field_name="author", authority_source="dbpedia"
    ).first()
    assert row is not None
    assert row.rejected >= 1
