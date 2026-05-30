"""Tests for adaptive per-field/domain resolution thresholds (Phase 3, Task 11).

The scoring engine maps a numeric score to a resolution_status using cut points
(exact / probable / ambiguous). Those cut points are tunable per (org, domain,
field); absence falls back to the global defaults.
"""
from __future__ import annotations

from backend.authority import thresholds as th
from backend.authority.scoring import (
    ResolutionThresholds,
    _DEFAULT_THRESHOLDS,
    compute_score,
)


# ── Pure classification ───────────────────────────────────────────────────────

def test_default_thresholds_match_module_constants():
    assert _DEFAULT_THRESHOLDS.classify(0.90) == "exact_match"
    assert _DEFAULT_THRESHOLDS.classify(0.70) == "probable_match"
    assert _DEFAULT_THRESHOLDS.classify(0.50) == "ambiguous"
    assert _DEFAULT_THRESHOLDS.classify(0.10) == "unresolved"


def test_custom_thresholds_shift_boundaries():
    strict = ResolutionThresholds(exact=0.95, probable=0.80, ambiguous=0.60)
    # A 0.90 score is exact under defaults but only probable under stricter cuts.
    assert _DEFAULT_THRESHOLDS.classify(0.90) == "exact_match"
    assert strict.classify(0.90) == "probable_match"


def test_compute_score_uses_override_thresholds():
    common = dict(
        value="John Smith", authority_source="orcid", authority_id="0000",
        canonical_label="John Smith", description=None,
    )
    _, _, _, default_status = compute_score(**common)
    strict = ResolutionThresholds(exact=0.999, probable=0.99, ambiguous=0.95)
    _, _, _, strict_status = compute_score(**common, thresholds=strict)
    assert default_status == "exact_match"
    assert strict_status != "exact_match"  # same score, stricter cut → downgraded


# ── DB-backed lookup ──────────────────────────────────────────────────────────

def test_lookup_returns_none_when_no_override(db_session):
    th.clear_cache()
    assert th.get_thresholds(db_session, "author", domain_id="science", org_id=None) is None


def test_lookup_returns_override_for_field_domain(db_session):
    from backend import models
    th.clear_cache()
    db_session.add(models.ResolutionThreshold(
        org_id=None, domain_id="science", field_name="author",
        exact=0.92, probable=0.70, ambiguous=0.50,
    ))
    db_session.commit()
    out = th.get_thresholds(db_session, "author", domain_id="science", org_id=None)
    assert out is not None
    assert out.exact == 0.92
    assert out.probable == 0.70


def test_field_only_override_falls_back_when_domain_differs(db_session):
    from backend import models
    th.clear_cache()
    db_session.add(models.ResolutionThreshold(
        org_id=None, domain_id=None, field_name="author",
        exact=0.88, probable=0.66, ambiguous=0.44,
    ))
    db_session.commit()
    # Domain-specific lookup misses, but the field-level (domain=None) override applies.
    out = th.get_thresholds(db_session, "author", domain_id="healthcare", org_id=None)
    assert out is not None
    assert out.exact == 0.88


# ── CRUD endpoint ─────────────────────────────────────────────────────────────

def test_create_and_list_threshold_endpoint(client, editor_headers):
    res = client.post(
        "/authority/thresholds",
        json={"field_name": "author", "domain_id": "science",
              "exact": 0.9, "probable": 0.68, "ambiguous": 0.48},
        headers=editor_headers,
    )
    assert res.status_code == 201
    listed = client.get("/authority/thresholds", headers=editor_headers)
    assert listed.status_code == 200
    rows = listed.json()
    assert any(r["field_name"] == "author" and r["domain_id"] == "science" for r in rows)


def test_threshold_validation_rejects_disordered_cuts(client, editor_headers):
    res = client.post(
        "/authority/thresholds",
        json={"field_name": "author", "exact": 0.4, "probable": 0.6, "ambiguous": 0.8},
        headers=editor_headers,
    )
    assert res.status_code == 422
