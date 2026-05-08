from __future__ import annotations

from unittest.mock import patch

from backend import models
from backend.authority.base import AuthorityCandidate


_PATCH = "backend.routers.authority._authority_resolve_all"


def _candidate(
    *,
    authority_source: str = "openalex",
    authority_id: str = "A1",
    canonical_label: str = "Candidate Author",
    confidence: float = 0.84,
    resolution_status: str = "probable_match",
    evidence: list[str] | None = None,
    merged_sources: list[str] | None = None,
):
    return AuthorityCandidate(
        authority_source=authority_source,
        authority_id=authority_id,
        canonical_label=canonical_label,
        aliases=[],
        description="Author profile",
        confidence=confidence,
        uri="https://example.org/authority",
        score_breakdown={
            "identifiers": 0.15 if confidence < 0.5 else 0.7,
            "name": confidence,
            "affiliation": 0.05 if confidence < 0.5 else 0.2,
            "coauthorship": 0.0,
            "topic": 0.0,
        },
        evidence=evidence or ["nil_detection_test"],
        resolution_status=resolution_status,
        merged_sources=merged_sources or [],
    )


class TestExplicitNilDetection:
    _URL = "/authority/authors/resolve"

    def _payload(self, value: str = "Unknownish Author"):
        return {
            "field_name": "author_name",
            "value": value,
            "context_affiliation": "Universidad Nacional de Colombia",
            "resolve_affiliation": False,
        }

    def test_insufficient_coverage_is_marked_as_nil(self, client, editor_headers, db_session):
        with patch(_PATCH, return_value=[
            _candidate(confidence=0.39, resolution_status="unresolved"),
        ]):
            resp = client.post(self._URL, json=self._payload(), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "manual_review"
        assert payload["nil_reason"] == "insufficient_coverage"
        assert payload["nil_score"] >= 0.84

        record = db_session.query(models.AuthorityRecord).one()
        assert record.nil_reason == "insufficient_coverage"
        assert (record.nil_score or 0.0) >= 0.84

    def test_conflicting_evidence_is_marked_as_nil(self, client, editor_headers, db_session):
        with patch(_PATCH, return_value=[
            _candidate(
                confidence=0.61,
                resolution_status="ambiguous",
                evidence=["source_conflict"],
                merged_sources=["openalex:A1", "wikidata:Q1"],
            ),
            _candidate(
                authority_source="wikidata",
                authority_id="Q1",
                canonical_label="Conflict Author",
                confidence=0.60,
                resolution_status="ambiguous",
            ),
        ]):
            resp = client.post(self._URL, json=self._payload("Conflict Author"), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "manual_review"
        assert payload["nil_reason"] == "conflicting_evidence"
        assert payload["nil_score"] >= 0.82

        records = db_session.query(models.AuthorityRecord).order_by(models.AuthorityRecord.id.asc()).all()
        assert len(records) == 2
        assert all(row.nil_reason == "conflicting_evidence" for row in records)

    def test_close_but_viable_ambiguous_candidates_are_not_nil(self, client, editor_headers):
        with patch(_PATCH, return_value=[
            _candidate(confidence=0.68, resolution_status="ambiguous"),
            _candidate(
                authority_source="wikidata",
                authority_id="Q2",
                canonical_label="Viable Runner Up",
                confidence=0.65,
                resolution_status="probable_match",
            ),
        ]):
            resp = client.post(self._URL, json=self._payload("Viable Ambiguous Author"), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "llm_path"
        assert payload["nil_reason"] is None
        assert payload["nil_score"] < 0.8
