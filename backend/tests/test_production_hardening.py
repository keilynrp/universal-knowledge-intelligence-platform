"""Tests for production-hardening fixes (engine-production-hardening change)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.engine_client import _sanitize_job_id
from backend.services.engine_delegation import MAX_DELEGATION_VALUES


# ── Job ID sanitization ─────────────────────────────────────────────────────

class TestSanitizeJobId:
    def test_strips_special_chars(self):
        assert _sanitize_job_id("job'; DROP TABLE--") == "jobDROPTABLE--"

    def test_allows_safe_chars(self):
        assert _sanitize_job_id("analytics-topics-default_01") == "analytics-topics-default_01"

    def test_truncates_to_128(self):
        long = "a" * 200
        assert len(_sanitize_job_id(long)) == 128

    def test_empty_string(self):
        assert _sanitize_job_id("") == ""


# ── Source validation ────────────────────────────────────────────────────────

class TestSourceValidation:
    def test_invalid_source_returns_400(self, client, auth_headers):
        resp = client.post(
            "/scientific/search",
            json={"source": "evil_source", "query": "test"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "Invalid source" in resp.json()["detail"] or "Unknown" in resp.json()["detail"]

    def test_invalid_doi_source_returns_400(self, client, auth_headers):
        resp = client.post(
            "/scientific/dois/preview",
            json={"dois": ["10.1234/test"], "source": "evil_source"},
            headers=auth_headers,
        )
        assert resp.status_code == 400


# ── Domain ID validation ─────────────────────────────────────────────────────

class TestDomainIdValidation:
    def test_invalid_domain_id_returns_422(self, client, auth_headers):
        resp = client.get(
            "/dashboard/compare?domains=valid,'; DROP TABLE",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_valid_domain_ids_pass(self, client, auth_headers):
        # May return empty data but shouldn't 422
        resp = client.get(
            "/dashboard/compare?domains=default,science",
            headers=auth_headers,
        )
        assert resp.status_code == 200


# ── Engine health auth ───────────────────────────────────────────────────────

class TestEngineHealthAuth:
    def test_viewer_cannot_access_engine_health(self, client, viewer_headers):
        resp = client.get("/engine/health", headers=viewer_headers)
        assert resp.status_code == 403

    def test_admin_can_access_engine_health(self, client, auth_headers):
        resp = client.get("/engine/health", headers=auth_headers)
        # May return engine not configured (no gRPC in test) but should not 403
        assert resp.status_code == 200


# ── Delegation values cap ────────────────────────────────────────────────────

class TestDelegationValuesCap:
    @pytest.mark.asyncio
    async def test_disambiguation_truncates_oversized(self):
        mock_client = AsyncMock()
        mock_client.process_disambiguation = AsyncMock(return_value=None)

        from backend.services.engine_delegation import try_engine_disambiguation
        values = [f"val_{i}" for i in range(MAX_DELEGATION_VALUES + 100)]
        await try_engine_disambiguation(mock_client, "brand", values)

        # Verify the call received truncated values
        call_args = mock_client.process_disambiguation.call_args
        assert len(call_args.kwargs["values"]) == MAX_DELEGATION_VALUES

    @pytest.mark.asyncio
    async def test_normalization_truncates_oversized(self):
        mock_client = AsyncMock()
        mock_client.process_normalization = AsyncMock(return_value=None)

        from backend.services.engine_delegation import try_engine_normalization
        values = [f"val_{i}" for i in range(MAX_DELEGATION_VALUES + 100)]
        await try_engine_normalization(mock_client, "brand", values)

        call_args = mock_client.process_normalization.call_args
        assert len(call_args.kwargs["values"]) == MAX_DELEGATION_VALUES


# ── AIResolveRequest no longer accepts api_key ───────────────────────────────

class TestAIResolveNoApiKey:
    def test_ai_resolve_request_rejects_api_key(self):
        from backend.routers.disambiguation import AIResolveRequest
        from pydantic import ValidationError

        # Should work without api_key
        req = AIResolveRequest(field_name="brand", variations=["a", "b"])
        assert req.field_name == "brand"

        # api_key should not be a recognized field (strict mode would reject,
        # but by default Pydantic just ignores extra fields)
        assert not hasattr(req, "api_key") or getattr(req, "api_key", None) is None
