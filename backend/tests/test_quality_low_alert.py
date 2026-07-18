"""
wire-notification-events — Phase 3: quality.low alert.

`quality.low` fires when a domain's average quality score drops from at/above
the configured threshold to below it (a downward crossing), so a full rescore
that degrades a domain notifies once — not on every recompute while already low.

Scores are 0..1; the threshold is expressed as a percent (0..100), default 60,
overridable via UKIP_QUALITY_LOW_THRESHOLD.
"""
from __future__ import annotations

import pytest

from backend import models
from backend.quality_scorer import (
    quality_low_threshold,
    quality_low_crossings,
    domain_quality_averages,
)


# ── Threshold config ────────────────────────────────────────────────────────

class TestThreshold:
    def test_default_is_60(self, monkeypatch):
        monkeypatch.delenv("UKIP_QUALITY_LOW_THRESHOLD", raising=False)
        assert quality_low_threshold() == 60.0

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("UKIP_QUALITY_LOW_THRESHOLD", "75")
        assert quality_low_threshold() == 75.0

    def test_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("UKIP_QUALITY_LOW_THRESHOLD", "not-a-number")
        assert quality_low_threshold() == 60.0


# ── Downward-crossing logic (pure) ──────────────────────────────────────────

class TestCrossings:
    def test_fires_on_downward_cross(self):
        before = {"books": 0.70, "music": 0.50}
        after = {"books": 0.50, "music": 0.50}
        crossings = quality_low_crossings(before, after, 60.0)
        assert [c["domain"] for c in crossings] == ["books"]
        c = crossings[0]
        assert c["avg_quality_pct"] == 50.0
        assert c["previous_pct"] == 70.0
        assert c["threshold_pct"] == 60.0

    def test_no_fire_when_staying_above(self):
        assert quality_low_crossings({"a": 0.90}, {"a": 0.80}, 60.0) == []

    def test_no_fire_when_already_below(self):
        # Already below the threshold before the pass → not a NEW crossing.
        assert quality_low_crossings({"a": 0.40}, {"a": 0.30}, 60.0) == []

    def test_no_fire_for_domain_without_baseline(self):
        # A domain with no previous average has no crossing to detect.
        assert quality_low_crossings({}, {"a": 0.30}, 60.0) == []

    def test_boundary_exactly_at_threshold_is_not_below(self):
        # after == threshold is NOT "below"; no fire.
        assert quality_low_crossings({"a": 0.90}, {"a": 0.60}, 60.0) == []


# ── domain_quality_averages (db) ────────────────────────────────────────────

class TestDomainAverages:
    def test_groups_and_averages_by_domain(self, db_session):
        db_session.add_all([
            models.UniversalEntity(primary_label="a1", domain="books", quality_score=0.8),
            models.UniversalEntity(primary_label="a2", domain="books", quality_score=0.6),
            models.UniversalEntity(primary_label="b1", domain="music", quality_score=0.4),
            models.UniversalEntity(primary_label="n1", domain="books", quality_score=None),
        ])
        db_session.commit()

        avgs = domain_quality_averages(db_session)

        assert avgs["books"] == pytest.approx(0.7)   # 0.8, 0.6 (None ignored)
        assert avgs["music"] == pytest.approx(0.4)
