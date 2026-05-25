"""Tests for authority_readiness.py — Task 3.6."""
import pytest

from backend.services.authority_candidate_extraction import CandidateFamily
from backend.services.authority_readiness import (
    AuthorityReadiness,
    AuthorityReadinessTracker,
    FamilyCounts,
    ReadinessState,
)


class TestFamilyCounts:
    def test_total(self):
        fc = FamilyCounts(extracted=5, resolved=2, review_required=1)
        assert fc.total == 8

    def test_resolution_rate(self):
        fc = FamilyCounts(extracted=5, resolved=5)
        assert fc.resolution_rate == 0.5

    def test_resolution_rate_zero(self):
        fc = FamilyCounts()
        assert fc.resolution_rate == 0.0

    def test_to_dict(self):
        fc = FamilyCounts(extracted=10, resolved=5)
        d = fc.to_dict()
        assert d["total"] == 15
        assert d["resolution_rate"] == round(5 / 15, 3)


class TestGetOrCreate:
    def test_creates_new(self):
        tracker = AuthorityReadinessTracker()
        r = tracker.get_or_create("domain-1")
        assert r.scope_id == "domain-1"
        assert r.state == ReadinessState.NOT_STARTED
        assert len(r.families) == len(CandidateFamily)

    def test_reuses_existing(self):
        tracker = AuthorityReadinessTracker()
        r1 = tracker.get_or_create("domain-1")
        r2 = tracker.get_or_create("domain-1")
        assert r1 is r2


class TestRecordExtraction:
    def test_updates_counts(self):
        tracker = AuthorityReadinessTracker()
        r = tracker.record_extraction("d1", CandidateFamily.PERSON, 10, "2026-01-01T00:00:00Z")
        assert r.families["person"].extracted == 10
        assert r.last_extraction_at == "2026-01-01T00:00:00Z"

    def test_state_becomes_source_ready(self):
        tracker = AuthorityReadinessTracker()
        r = tracker.record_extraction("d1", CandidateFamily.PERSON, 5, "2026-01-01")
        assert r.state == ReadinessState.SOURCE_CANDIDATES_READY

    def test_accumulates(self):
        tracker = AuthorityReadinessTracker()
        tracker.record_extraction("d1", CandidateFamily.PERSON, 5, "t1")
        r = tracker.record_extraction("d1", CandidateFamily.PERSON, 3, "t2")
        assert r.families["person"].extracted == 8


class TestRecordResolution:
    def test_partially_resolved(self):
        tracker = AuthorityReadinessTracker()
        tracker.record_extraction("d1", CandidateFamily.PERSON, 10, "t1")
        r = tracker.record_resolution("d1", CandidateFamily.PERSON, resolved=5)
        assert r.state == ReadinessState.PARTIALLY_RESOLVED

    def test_fully_resolved(self):
        tracker = AuthorityReadinessTracker()
        # extracted=5, resolved=5 → total=10, resolved < total → PARTIALLY_RESOLVED
        # For RESOLVED, resolved must equal total across all families
        tracker.record_resolution("d1", CandidateFamily.PERSON, resolved=5)
        r = tracker.get_or_create("d1")
        # Total = sum of all family counts. With 6 families all at 0 except person(resolved=5),
        # total=5, resolved=5 → RESOLVED
        assert r.state == ReadinessState.RESOLVED

    def test_review_required(self):
        tracker = AuthorityReadinessTracker()
        tracker.record_extraction("d1", CandidateFamily.PERSON, 10, "t1")
        r = tracker.record_resolution("d1", CandidateFamily.PERSON, review_required=3)
        assert r.state == ReadinessState.REVIEW_REQUIRED

    def test_failed_only(self):
        tracker = AuthorityReadinessTracker()
        r = tracker.record_resolution("d1", CandidateFamily.PERSON, failed=5)
        assert r.state == ReadinessState.FAILED


class TestMarkStale:
    def test_stale(self):
        tracker = AuthorityReadinessTracker()
        tracker.record_extraction("d1", CandidateFamily.PERSON, 10, "t1")
        r = tracker.mark_stale("d1", CandidateFamily.PERSON, 2, "t2")
        assert r.state == ReadinessState.STALE
        assert r.last_evidence_change_at == "t2"

    def test_stale_overrides_resolved(self):
        tracker = AuthorityReadinessTracker()
        tracker.record_extraction("d1", CandidateFamily.PERSON, 5, "t1")
        tracker.record_resolution("d1", CandidateFamily.PERSON, resolved=5)
        r = tracker.mark_stale("d1", CandidateFamily.PERSON, 1, "t3")
        assert r.state == ReadinessState.STALE


class TestToDict:
    def test_serialization(self):
        tracker = AuthorityReadinessTracker()
        tracker.record_extraction("d1", CandidateFamily.PERSON, 10, "t1")
        d = tracker.get_or_create("d1").to_dict()
        assert d["state"] == "source_candidates_ready"
        assert "person" in d["families"]
        assert d["families"]["person"]["extracted"] == 10
