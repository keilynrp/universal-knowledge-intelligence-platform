from __future__ import annotations

from unittest.mock import patch

from backend import models
from backend.authority.base import AuthorityCandidate


_PATCH = "backend.routers.authority._authority_resolve_all"


def _candidate(
    *,
    authority_source: str = "orcid",
    authority_id: str = "0000-0001-0000-0001",
    canonical_label: str = "Gabriel Garcia Marquez",
    confidence: float = 0.95,
    resolution_status: str = "exact_match",
):
    return AuthorityCandidate(
        authority_source=authority_source,
        authority_id=authority_id,
        canonical_label=canonical_label,
        aliases=["G. Garcia Marquez"],
        description="Author profile",
        confidence=confidence,
        uri="https://example.org/authority",
        score_breakdown={
            "identifiers": 1.0 if authority_source == "orcid" else 0.7,
            "name": confidence,
            "affiliation": 0.2,
            "coauthorship": 0.0,
            "topic": 0.0,
        },
        evidence=["author_test_candidate"],
        resolution_status=resolution_status,
        merged_sources=[],
    )


class TestAuthorResolutionEngine:
    _URL = "/authority/authors/resolve"

    def _payload(self, **overrides):
        payload = {
            "field_name": "author_name",
            "value": "Gabriel Garcia Marquez",
            "context_affiliation": "Universidad Nacional de Colombia",
            "resolve_affiliation": False,
        }
        payload.update(overrides)
        return payload

    def test_fast_path_exact_match_without_review(self, client, editor_headers, db_session):
        with patch(_PATCH, return_value=[_candidate(confidence=0.97, resolution_status="exact_match")]):
            resp = client.post(self._URL, json=self._payload(context_orcid_hint="0000-0001-0000-0001"), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "fast_path"
        assert payload["review_required"] is False
        assert payload["nil_reason"] is None
        assert payload["nil_score"] < 0.5
        assert payload["complexity_score"] < 0.5
        assert payload["winning_record"]["resolution_route"] == "fast_path"
        assert payload["winning_record"]["nil_score"] < 0.5

        record = db_session.query(models.AuthorityRecord).one()
        assert record.resolution_route == "fast_path"
        assert record.review_required is False
        assert record.nil_reason is None
        assert (record.nil_score or 0.0) < 0.5

    def test_hybrid_path_returns_runner_up_for_comparison(self, client, editor_headers, db_session):
        candidates = [
            _candidate(authority_source="openalex", authority_id="A1", confidence=0.84, resolution_status="probable_match"),
            _candidate(authority_source="wikidata", authority_id="Q1", canonical_label="Gabriel G. Marquez", confidence=0.62, resolution_status="ambiguous"),
        ]
        with patch(_PATCH, return_value=candidates):
            resp = client.post(self._URL, json=self._payload(), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "hybrid_path"
        assert payload["review_required"] is False
        assert payload["nil_score"] < 0.8
        assert payload["runner_up_record"] is not None
        assert payload["records_created"] == 2

        rows = db_session.query(models.AuthorityRecord).order_by(models.AuthorityRecord.id.asc()).all()
        assert len(rows) == 2
        assert all(row.resolution_route == "hybrid_path" for row in rows)

    def test_strong_exact_match_without_orcid_can_use_hybrid_path(self, client, editor_headers, db_session):
        candidates = [
            _candidate(authority_source="openalex", authority_id="A8B", confidence=0.88, resolution_status="exact_match"),
            _candidate(authority_source="wikidata", authority_id="Q8B", canonical_label="Gabriel G. Marquez", confidence=0.76, resolution_status="probable_match"),
        ]
        with patch(_PATCH, return_value=candidates):
            resp = client.post(self._URL, json=self._payload(), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "hybrid_path"
        assert payload["review_required"] is False
        assert payload["nil_reason"] is None

        rows = db_session.query(models.AuthorityRecord).order_by(models.AuthorityRecord.id.asc()).all()
        assert len(rows) == 2
        assert all(row.resolution_route == "hybrid_path" for row in rows)
        assert all(row.review_required is False for row in rows)

    def test_close_ambiguous_candidates_route_to_llm_path(self, client, editor_headers, db_session):
        candidates = [
            _candidate(authority_source="openalex", authority_id="A1", confidence=0.68, resolution_status="ambiguous"),
            _candidate(authority_source="wikidata", authority_id="Q1", canonical_label="Gabriel G. Marquez", confidence=0.65, resolution_status="probable_match"),
        ]
        with patch(_PATCH, return_value=candidates):
            resp = client.post(self._URL, json=self._payload(), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "llm_path"
        assert payload["review_required"] is True
        assert payload["nil_reason"] is None
        assert payload["nil_score"] < 0.8

        rows = db_session.query(models.AuthorityRecord).all()
        assert len(rows) == 2
        assert all(row.review_required is True for row in rows)
        assert all((row.nil_score or 0.0) < 0.8 for row in rows)

    def test_no_candidates_persists_nil_record(self, client, editor_headers, db_session):
        with patch(_PATCH, return_value=[]):
            resp = client.post(self._URL, json=self._payload(value="Unknown Author"), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "manual_review"
        assert payload["review_required"] is True
        assert payload["nil_reason"] == "no_candidates"
        assert payload["nil_score"] == 1.0
        assert payload["records_created"] == 1
        assert payload["winning_record"]["authority_source"] == "internal_nil"

        record = db_session.query(models.AuthorityRecord).one()
        assert record.authority_source == "internal_nil"
        assert record.nil_reason == "no_candidates"
        assert record.resolution_route == "manual_review"
        assert record.nil_score == 1.0
