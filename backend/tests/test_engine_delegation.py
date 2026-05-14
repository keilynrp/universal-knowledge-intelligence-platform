"""Tests for EngineClient compute delegation and fallback behavior."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.engine_client import EngineClient


@pytest.fixture
def engine_client():
    """Create an EngineClient pointed at a non-existent server."""
    return EngineClient(grpc_url="localhost:50052", auth_token="test-token")


@pytest.fixture
def offline_client():
    """Create an EngineClient with no URL (always falls back)."""
    return EngineClient(grpc_url="", auth_token="")


# ── Fallback tests (engine unavailable) ──────────────────────────────


class TestFallbackBehavior:
    """Verify all convenience methods return None when engine is unavailable."""

    def test_process_authority_fallback(self, offline_client):
        result = asyncio.get_event_loop().run_until_complete(
            offline_client.process_authority(
                field_name="author",
                values=["John Smith"],
            )
        )
        assert result is None

    def test_process_analytics_fallback(self, offline_client):
        result = asyncio.get_event_loop().run_until_complete(
            offline_client.process_analytics(
                domain_id="science",
                mode="topics",
            )
        )
        assert result is None

    def test_process_disambiguation_fallback(self, offline_client):
        result = asyncio.get_event_loop().run_until_complete(
            offline_client.process_disambiguation(
                field_name="brand",
                values=["Apple", "apple"],
            )
        )
        assert result is None

    def test_process_normalization_fallback(self, offline_client):
        result = asyncio.get_event_loop().run_until_complete(
            offline_client.process_normalization(
                values=["García"],
                mode="unicode",
            )
        )
        assert result is None

    def test_process_connectors_fallback(self, offline_client):
        result = asyncio.get_event_loop().run_until_complete(
            offline_client.process_connectors(
                source="openalex",
                query_type="doi",
                queries=["10.1234/test"],
            )
        )
        assert result is None

    def test_health_fallback(self, offline_client):
        result = asyncio.get_event_loop().run_until_complete(
            offline_client.health()
        )
        assert result is False


# ── Delegation tests (mock engine success) ────────────────────────────


class TestDelegationSuccess:
    """Verify convenience methods send correct proto requests when engine is mocked."""

    @pytest.fixture(autouse=True)
    def setup_mock_channel(self):
        """Provide a pre-connected client with a mocked stub."""
        self.mock_stub = MagicMock()

        self.client = EngineClient(
            grpc_url="localhost:50052", auth_token="test"
        )
        # Bypass channel setup — inject stub directly
        self.client._channel = MagicMock()
        self.client._stub = self.mock_stub
        yield

    def test_process_authority_sends_request(self):
        mock_resp = MagicMock()
        self.mock_stub.ProcessSync = AsyncMock(return_value=mock_resp)

        result = asyncio.get_event_loop().run_until_complete(
            self.client.process_authority(
                field_name="author",
                values=["John Smith", "Alice Jones"],
                entity_type="person",
                context_affiliation="MIT",
            )
        )

        assert result is mock_resp
        call_args = self.mock_stub.ProcessSync.call_args
        req = call_args[0][0]
        assert req.pipeline == "compute_authority"
        assert req.authority_request.field_name == "author"
        assert list(req.authority_request.values) == ["John Smith", "Alice Jones"]
        assert req.authority_request.context_affiliation == "MIT"

    def test_process_analytics_sends_request(self):
        mock_resp = MagicMock()
        self.mock_stub.ProcessSync = AsyncMock(return_value=mock_resp)

        result = asyncio.get_event_loop().run_until_complete(
            self.client.process_analytics(
                domain_id="science",
                mode="topics",
                limit=20,
            )
        )

        assert result is mock_resp
        call_args = self.mock_stub.ProcessSync.call_args
        req = call_args[0][0]
        assert req.pipeline == "compute_analytics"
        assert req.analytics_request.mode == "topics"
        assert req.analytics_request.limit == 20

    def test_process_disambiguation_sends_request(self):
        mock_resp = MagicMock()
        self.mock_stub.ProcessSync = AsyncMock(return_value=mock_resp)

        result = asyncio.get_event_loop().run_until_complete(
            self.client.process_disambiguation(
                field_name="brand",
                values=["Apple", "apple"],
                similarity_threshold=0.90,
            )
        )

        assert result is mock_resp
        call_args = self.mock_stub.ProcessSync.call_args
        req = call_args[0][0]
        assert req.pipeline == "compute_disambiguation"
        assert req.disambiguation_request.similarity_threshold == pytest.approx(0.90)

    def test_process_normalization_sends_request(self):
        mock_resp = MagicMock()
        self.mock_stub.ProcessSync = AsyncMock(return_value=mock_resp)

        result = asyncio.get_event_loop().run_until_complete(
            self.client.process_normalization(
                values=["García", "Müller"],
                mode="unicode",
            )
        )

        assert result is mock_resp
        call_args = self.mock_stub.ProcessSync.call_args
        req = call_args[0][0]
        assert req.pipeline == "compute_normalization"
        assert req.normalization_request.mode == "unicode"

    def test_process_normalization_with_rules(self):
        mock_resp = MagicMock()
        self.mock_stub.ProcessSync = AsyncMock(return_value=mock_resp)

        result = asyncio.get_event_loop().run_until_complete(
            self.client.process_normalization(
                values=["Apple Inc."],
                mode="rules",
                rules=[{"pattern": r"Inc\.?", "replacement": "Incorporated"}],
            )
        )

        assert result is mock_resp
        call_args = self.mock_stub.ProcessSync.call_args
        req = call_args[0][0]
        assert req.normalization_request.mode == "rules"
        assert len(req.normalization_request.rules) == 1

    def test_process_connectors_sends_request(self):
        mock_resp = MagicMock()
        self.mock_stub.ProcessSync = AsyncMock(return_value=mock_resp)

        result = asyncio.get_event_loop().run_until_complete(
            self.client.process_connectors(
                source="openalex",
                query_type="doi",
                queries=["10.1234/test"],
                limit=5,
            )
        )

        assert result is mock_resp
        call_args = self.mock_stub.ProcessSync.call_args
        req = call_args[0][0]
        assert req.pipeline == "compute_connectors"
        assert req.connector_request.source == "openalex"
        assert req.connector_request.query_type == "doi"

    def test_process_authority_handles_exception(self):
        self.mock_stub.ProcessSync = AsyncMock(
            side_effect=Exception("connection refused")
        )

        result = asyncio.get_event_loop().run_until_complete(
            self.client.process_authority(
                field_name="author",
                values=["John Smith"],
            )
        )

        assert result is None
