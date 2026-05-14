"""Tests for EngineClient compute delegation and fallback behavior."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.engine_client import EngineClient
from backend.services.engine_delegation import (
    ENGINE_DELEGATION_THRESHOLD,
    try_engine_analytics,
    try_engine_connectors,
    try_engine_disambiguation,
    try_engine_normalization,
)


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


# ── Delegation helper tests (engine_delegation.py) ───────────────────


class TestAnalyticsDelegationHelpers:
    """Tests for try_engine_analytics and response converters."""

    def _make_response(self, mode):
        topic = SimpleNamespace(concept="AI", count=10, frequency=0.5)
        cooc = SimpleNamespace(concept_a="AI", concept_b="ML", co_count=5, pmi=2.3)
        cluster = SimpleNamespace(seed_concept="AI", members=["AI", "ML"], total_count=15)
        corr = SimpleNamespace(field_a="year", field_b="journal", cramers_v=0.42, strength="moderate")
        ar = SimpleNamespace(
            topics=[topic] if mode == "topics" else [],
            cooccurrences=[cooc] if mode == "cooccurrence" else [],
            clusters=[cluster] if mode == "clusters" else [],
            correlations=[corr] if mode == "correlation" else [],
        )
        return SimpleNamespace(analytics_result=ar)

    def test_topics_conversion(self):
        client = AsyncMock()
        client.process_analytics = AsyncMock(return_value=self._make_response("topics"))
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_analytics(client, "default", "topics", 30)
        )
        assert result is not None
        assert result[0]["concept"] == "AI"
        assert result[0]["count"] == 10

    def test_cooccurrence_conversion(self):
        client = AsyncMock()
        client.process_analytics = AsyncMock(return_value=self._make_response("cooccurrence"))
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_analytics(client, "default", "cooccurrence", 20)
        )
        assert result is not None
        assert result[0]["concept_a"] == "AI"
        assert result[0]["pmi"] == 2.3

    def test_clusters_conversion(self):
        client = AsyncMock()
        client.process_analytics = AsyncMock(return_value=self._make_response("clusters"))
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_analytics(client, "default", "clusters", 6)
        )
        assert result is not None
        assert result[0]["seed"] == "AI"
        assert "AI" in result[0]["members"]
        assert result[0]["cluster_id"] == 0

    def test_correlation_conversion(self):
        client = AsyncMock()
        client.process_analytics = AsyncMock(return_value=self._make_response("correlation"))
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_analytics(client, "default", "correlation", 20)
        )
        assert result is not None
        assert result[0]["field_a"] == "year"
        assert result[0]["cramers_v"] == 0.42
        assert result[0]["strength"] == "moderate"

    def test_engine_unavailable_returns_none(self):
        client = AsyncMock()
        client.process_analytics = AsyncMock(return_value=None)
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_analytics(client, "default", "topics", 30)
        )
        assert result is None

    def test_none_client_returns_none(self):
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_analytics(None, "default", "topics", 30)
        )
        assert result is None

    def test_exception_returns_none(self):
        client = AsyncMock()
        client.process_analytics = AsyncMock(side_effect=Exception("rpc error"))
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_analytics(client, "default", "topics", 30)
        )
        assert result is None


class TestDisambiguationDelegationHelpers:
    """Tests for try_engine_disambiguation."""

    def test_successful_delegation(self):
        cluster = SimpleNamespace(
            canonical_value="University of Tokyo",
            variants=["Univ Tokyo", "U. Tokyo"],
            scores=[0.92, 0.88],
            frequency=3,
        )
        resp = SimpleNamespace(disambiguation_result=SimpleNamespace(clusters=[cluster]))
        client = AsyncMock()
        client.process_disambiguation = AsyncMock(return_value=resp)
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_disambiguation(client, "institution", ["a"] * 200, 80, 0.85)
        )
        assert result is not None
        assert result[0]["canonical"] == "University of Tokyo"
        assert result[0]["count"] == 3
        assert "Univ Tokyo" in result[0]["variations"]

    def test_engine_unavailable_returns_none(self):
        client = AsyncMock()
        client.process_disambiguation = AsyncMock(return_value=None)
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_disambiguation(client, "author", ["a", "b"], 80, 0.85)
        )
        assert result is None

    def test_threshold_default(self):
        assert ENGINE_DELEGATION_THRESHOLD == 100


class TestNormalizationDelegationHelpers:
    """Tests for try_engine_normalization."""

    def test_bulk_exact_match(self):
        nr = SimpleNamespace(normalized_values=["Apple Inc.", "Google LLC", "Microsoft Corp."])
        resp = SimpleNamespace(normalization_result=nr)
        client = AsyncMock()
        client.process_normalization = AsyncMock(return_value=resp)
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_normalization(
                client, "company",
                ["apple inc.", "google llc", "Microsoft Corp."],
                mode="rules",
                rules=[{"pattern": "apple inc.", "replacement": "Apple Inc."}],
            )
        )
        assert result is not None
        assert result["apple inc."] == "Apple Inc."
        assert result["google llc"] == "Google LLC"
        # Unchanged value not in mapping
        assert "Microsoft Corp." not in result

    def test_engine_unavailable_returns_none(self):
        client = AsyncMock()
        client.process_normalization = AsyncMock(return_value=None)
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_normalization(client, "field", ["a"], "rules")
        )
        assert result is None


class TestConnectorDelegationHelpers:
    """Tests for try_engine_connectors."""

    def _make_pub(self):
        author = SimpleNamespace(display_name="John Doe")
        return SimpleNamespace(
            title="A Study",
            doi="10.1234/test",
            year=2024,
            abstract_text="Abstract here",
            source_title="Nature",
            enrichment_source="openalex",
            citation_count=42,
            authors=[author],
        )

    def test_publication_conversion(self):
        pub = self._make_pub()
        cr = SimpleNamespace(publications=[pub], total_results=1)
        resp = SimpleNamespace(connector_result=cr)
        client = AsyncMock()
        client.process_connectors = AsyncMock(return_value=resp)
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_connectors(client, "openalex", "search", ["machine learning"], 10)
        )
        assert result is not None
        assert len(result) == 1
        assert result[0]["title"] == "A Study"
        assert result[0]["doi"] == "10.1234/test"
        assert result[0]["authors"] == ["John Doe"]
        assert result[0]["citations"] == 42
        assert result[0]["journal"] == "Nature"

    def test_engine_unavailable_returns_none(self):
        client = AsyncMock()
        client.process_connectors = AsyncMock(return_value=None)
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_connectors(client, "openalex", "search", ["test"], 10)
        )
        assert result is None

    def test_none_client_returns_none(self):
        result = asyncio.get_event_loop().run_until_complete(
            try_engine_connectors(None, "openalex", "search", ["test"], 10)
        )
        assert result is None


# ── E2E tests (behind UKIP_ENGINE_E2E=1 flag) ────────────────────────

import os

_ENGINE_E2E = os.environ.get("UKIP_ENGINE_E2E", "0") == "1"


@pytest.mark.skipif(not _ENGINE_E2E, reason="UKIP_ENGINE_E2E not set")
class TestAnalyticsDelegationE2E:
    """E2E: requires a running engine at ENGINE_GRPC_URL."""

    def test_analytics_topics_via_engine(self, client, auth_headers):
        resp = client.get("/analyzers/topics/default?top_n=5", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            assert "concept" in data[0]
            assert "count" in data[0]


@pytest.mark.skipif(not _ENGINE_E2E, reason="UKIP_ENGINE_E2E not set")
class TestDisambiguationDelegationE2E:
    """E2E: disambiguation with engine delegation."""

    def test_disambiguation_with_large_dataset(self, client, auth_headers):
        resp = client.get("/disambiguate/primary_label?threshold=80", headers=auth_headers)
        assert resp.status_code in (200, 400)
        if resp.status_code == 200:
            data = resp.json()
            assert "groups" in data
            assert "total_groups" in data
