from __future__ import annotations

from unittest.mock import patch

from backend import models
from backend.authority.base import AuthorityCandidate
from backend.llm_agent import QueryReformulationResult


_RESOLVE_PATCH = "backend.routers.authority._authority_resolve_all"
_REFORM_PATCH = "backend.authority.query_reformulation.generate_query_reformulations"


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
        evidence=["author_reformulation_test"],
        resolution_status=resolution_status,
        merged_sources=[],
    )


class TestAuthorQueryReformulation:
    _URL = "/authority/authors/resolve"

    def _payload(self, value: str = "Unknownish Author"):
        return {
            "field_name": "author_name",
            "value": value,
            "context_affiliation": "Universidad Nacional de Colombia",
            "resolve_affiliation": False,
        }

    def test_feature_flag_off_keeps_deterministic_path(self, client, editor_headers, db_session, monkeypatch):
        monkeypatch.delenv("UKIP_ENABLE_LLM_QUERY_REFORMULATION", raising=False)
        with patch(_RESOLVE_PATCH, return_value=[]):
            resp = client.post(self._URL, json=self._payload(), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "manual_review"
        assert payload["reformulation"] is None

        record = db_session.query(models.AuthorityRecord).one()
        assert record.reformulation_trace is None
        assert bool(record.reformulation_applied) is False

    def test_feature_flag_on_applies_better_reformulated_query(self, client, editor_headers, db_session, monkeypatch):
        monkeypatch.setenv("UKIP_ENABLE_LLM_QUERY_REFORMULATION", "1")

        def resolve_side_effect(value, entity_type, context):
            if value == "Unknownish Author":
                return []
            if value == "Gabriel Garcia Marquez":
                return [_candidate(authority_source="orcid", authority_id="0000-0001-0000-0001", confidence=0.97, resolution_status="exact_match")]
            return []

        with patch(_RESOLVE_PATCH, side_effect=resolve_side_effect):
            with patch(_REFORM_PATCH, return_value=QueryReformulationResult(
                variants=["Gabriel Garcia Marquez"],
                provider="openai",
                model="gpt-4o-mini",
                prompt_tokens=90,
                completion_tokens=24,
            )):
                resp = client.post(self._URL, json=self._payload(), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "fast_path"
        assert payload["reformulation"]["attempted"] is True
        assert payload["reformulation"]["applied"] is True
        assert payload["reformulation"]["selected_query"] == "Gabriel Garcia Marquez"
        assert payload["winning_record"]["reformulation_applied"] is True
        assert payload["winning_record"]["reformulation_gain"] == 1

        record = db_session.query(models.AuthorityRecord).one()
        assert record.reformulation_applied is True
        assert record.reformulation_gain == 1
        assert record.reformulation_trace is not None

    def test_feature_flag_on_does_not_break_when_provider_returns_no_variants(self, client, editor_headers, db_session, monkeypatch):
        monkeypatch.setenv("UKIP_ENABLE_LLM_QUERY_REFORMULATION", "1")
        with patch(_RESOLVE_PATCH, return_value=[]):
            with patch(_REFORM_PATCH, return_value=QueryReformulationResult()):
                resp = client.post(self._URL, json=self._payload("Still Unknown"), headers=editor_headers)

        assert resp.status_code == 201
        payload = resp.json()
        assert payload["resolution_route"] == "manual_review"
        assert payload["nil_reason"] == "no_candidates"
        assert payload["reformulation"]["attempted"] is True
        assert payload["reformulation"]["applied"] is False

        record = db_session.query(models.AuthorityRecord).one()
        assert bool(record.reformulation_applied) is False
        assert record.reformulation_trace is not None
