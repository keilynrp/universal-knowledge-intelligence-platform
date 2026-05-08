from __future__ import annotations

from unittest.mock import patch

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
        evidence=["author_compare_test"],
        resolution_status=resolution_status,
        merged_sources=[],
    )


class TestAuthorReviewCompare:
    _RESOLVE_URL = "/authority/authors/resolve"

    def _payload(self, value: str = "Gabriel Garcia Marquez"):
        return {
            "field_name": "author_name",
            "value": value,
            "context_affiliation": "Universidad Nacional de Colombia",
            "resolve_affiliation": False,
        }

    def test_compare_returns_subject_and_peer_candidates(self, client, editor_headers):
        with patch(_RESOLVE_PATCH, return_value=[
            _candidate(confidence=0.84, resolution_status="probable_match"),
            _candidate(authority_source="wikidata", authority_id="Q1", canonical_label="Gabriel G. Marquez", confidence=0.62, resolution_status="ambiguous"),
            _candidate(authority_source="viaf", authority_id="V1", canonical_label="G. Garcia Marquez", confidence=0.51, resolution_status="ambiguous"),
        ]):
            create = client.post(self._RESOLVE_URL, json=self._payload(), headers=editor_headers)

        assert create.status_code == 201
        record_id = create.json()["records"][0]["id"]

        resp = client.get(f"/authority/authors/review-queue/{record_id}/compare", headers=editor_headers)
        assert resp.status_code == 200
        payload = resp.json()

        assert payload["subject"]["id"] == record_id
        assert payload["peer_count"] == 2
        assert len(payload["peers"]) == 2
        assert payload["peers"][0]["id"] != record_id
        assert payload["peers"][0]["original_value"] == payload["subject"]["original_value"]

    def test_compare_rejects_non_author_records(self, client, editor_headers):
        resp = client.get("/authority/authors/review-queue/999999/compare", headers=editor_headers)
        assert resp.status_code == 404
