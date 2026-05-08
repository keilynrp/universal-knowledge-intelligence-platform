from __future__ import annotations

from unittest.mock import patch

from backend import models
from backend.authority.base import AuthorityCandidate


_RESOLVE_PATCH = "backend.routers.authority._authority_resolve_all"


def _candidate(
    *,
    authority_source: str = "openalex",
    authority_id: str = "A1",
    canonical_label: str = "Gabriel Garcia Marquez",
    confidence: float = 0.84,
    resolution_status: str = "probable_match",
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
            "identifiers": 0.7,
            "name": confidence,
            "affiliation": 0.2,
            "coauthorship": 0.0,
            "topic": 0.0,
        },
        evidence=["author_metrics_test"],
        resolution_status=resolution_status,
        merged_sources=[],
    )


class TestAuthorResolutionMetrics:
    _RESOLVE_URL = "/authority/authors/resolve"
    _METRICS_URL = "/authority/authors/metrics"

    def _payload(self, value: str):
        return {
            "field_name": "author_name",
            "value": value,
            "context_affiliation": "Universidad Nacional de Colombia",
            "resolve_affiliation": False,
        }

    def test_unauthenticated_returns_401(self, client):
        assert client.get(self._METRICS_URL).status_code == 401

    def test_metrics_only_include_author_engine_records(self, client, editor_headers, db_session):
        legacy = models.AuthorityRecord(
            field_name="brand_capitalized",
            original_value="Microsoft",
            authority_source="wikidata",
            authority_id="Q2283",
            canonical_label="Microsoft",
            aliases="[]",
            description="Technology company",
            confidence=0.91,
            status="pending",
            resolution_status="exact_match",
            score_breakdown="{}",
            evidence="[]",
            merged_sources="[]",
        )
        db_session.add(legacy)
        db_session.commit()

        with patch(_RESOLVE_PATCH, return_value=[
            _candidate(authority_source="orcid", authority_id="0000-0001-0000-0001", confidence=0.97, resolution_status="exact_match")
        ]):
            assert client.post(self._RESOLVE_URL, json=self._payload("Fast Author"), headers=editor_headers).status_code == 201

        with patch(_RESOLVE_PATCH, return_value=[
            _candidate(confidence=0.84, resolution_status="probable_match"),
            _candidate(authority_source="wikidata", authority_id="Q1", canonical_label="Gabriel G. Marquez", confidence=0.62, resolution_status="ambiguous"),
        ]):
            assert client.post(self._RESOLVE_URL, json=self._payload("Hybrid Author"), headers=editor_headers).status_code == 201

        with patch(_RESOLVE_PATCH, return_value=[
            _candidate(confidence=0.68, resolution_status="ambiguous"),
            _candidate(authority_source="wikidata", authority_id="Q2", canonical_label="Gabriel G. Marquez", confidence=0.65, resolution_status="probable_match"),
        ]):
            assert client.post(self._RESOLVE_URL, json=self._payload("LLM Author"), headers=editor_headers).status_code == 201

        with patch(_RESOLVE_PATCH, return_value=[]):
            assert client.post(self._RESOLVE_URL, json=self._payload("Unknown Author"), headers=editor_headers).status_code == 201

        records = db_session.query(models.AuthorityRecord).filter(
            models.AuthorityRecord.resolution_route.is_not(None)
        ).order_by(models.AuthorityRecord.id.asc()).all()
        assert len(records) == 6

        assert client.post(
            f"/authority/records/{records[0].id}/confirm",
            json={"also_create_rule": True},
            headers=editor_headers,
        ).status_code == 200
        assert client.post(
            f"/authority/records/{records[3].id}/reject",
            headers=editor_headers,
        ).status_code == 200

        resp = client.get(self._METRICS_URL, headers=editor_headers)
        assert resp.status_code == 200
        payload = resp.json()

        assert payload["total_records"] == 6
        assert payload["pending_review"] == 2
        assert payload["nil_cases"] == 1
        assert payload["by_nil_reason"]["no_candidates"] == 1
        assert payload["by_route"]["fast_path"] == 1
        assert payload["by_route"]["hybrid_path"] == 2
        assert payload["by_route"]["llm_path"] == 2
        assert payload["by_route"]["manual_review"] == 1
        assert payload["by_status"]["confirmed"] == 1
        assert payload["by_status"]["rejected"] == 1
        assert payload["by_status"]["pending"] == 4
        assert payload["avg_confidence"] > 0
        assert payload["avg_complexity"] > 0
        assert payload["avg_nil_score"] > 0
        assert payload["review_rate"] == 0.333
        assert payload["nil_rate"] == 0.167
        assert payload["confirm_rate"] == 0.167
        assert payload["reject_rate"] == 0.167
