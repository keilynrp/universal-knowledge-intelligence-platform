"""
End-to-end integration tests for engine delegation.

These tests require a running ukip-engine instance.
Set UKIP_ENGINE_E2E=1 to enable.
"""
from __future__ import annotations

import asyncio
import os
import time

import pytest

# Skip entire module if engine e2e not enabled
pytestmark = pytest.mark.skipif(
    os.environ.get("UKIP_ENGINE_E2E") != "1",
    reason="Set UKIP_ENGINE_E2E=1 to run engine e2e tests",
)


@pytest.fixture
def engine_client():
    from backend.services.engine_client import EngineClient

    url = os.environ.get("UKIP_ENGINE_URL", "localhost:50051")
    client = EngineClient(grpc_url=url)
    yield client
    asyncio.get_event_loop().run_until_complete(client.close())


class TestE2EAuthorityDelegation:
    """10.1: Python backend delegates authority resolution to running engine."""

    def test_authority_resolution_returns_valid_format(self, engine_client):
        resp = asyncio.get_event_loop().run_until_complete(
            engine_client.process_authority(
                field_name="author",
                values=["John Smith", "García, José María"],
                entity_type="person",
            )
        )
        assert resp is not None, "engine should return a response"
        # Check the response has expected structure
        assert hasattr(resp, "authority_result") or hasattr(resp, "typed_result")


class TestE2EFallback:
    """10.2: Python backend falls back gracefully when engine is stopped."""

    def test_fallback_when_engine_unavailable(self):
        from backend.services.engine_client import EngineClient

        # Connect to a port where nothing is running
        client = EngineClient(grpc_url="localhost:59999")
        result = asyncio.get_event_loop().run_until_complete(
            client.process_authority(
                field_name="author",
                values=["John Smith"],
            )
        )
        assert result is None, "should return None for fallback"
        asyncio.get_event_loop().run_until_complete(client.close())


class TestBenchmarkAuthority:
    """10.3: Benchmark Rust authority vs Python on 1000 entities."""

    def test_rust_authority_1000_entities(self, engine_client):
        values = [f"Author {i}" for i in range(1000)]

        start = time.perf_counter()
        resp = asyncio.get_event_loop().run_until_complete(
            engine_client.process_authority(
                field_name="author",
                values=values,
                entity_type="person",
            )
        )
        rust_elapsed = time.perf_counter() - start

        assert resp is not None
        print(f"\nRust authority (1000 values): {rust_elapsed:.3f}s")

        # Python baseline
        from backend.authority.resolver import resolve_all

        start = time.perf_counter()
        for v in values[:10]:  # Only 10 for Python (much slower with real API calls)
            resolve_all(v, "person")
        python_per_item = (time.perf_counter() - start) / 10
        python_estimated = python_per_item * 1000

        print(f"Python authority (estimated 1000 values): {python_estimated:.3f}s")
        print(f"Speedup: {python_estimated / rust_elapsed:.1f}x")


class TestBenchmarkDisambiguation:
    """10.4: Benchmark Rust disambiguation vs Python on 10k values."""

    def test_rust_disambiguation_10k(self, engine_client):
        # Generate 10k values with duplicates
        base_values = [f"Entity {i}" for i in range(5000)]
        # Add variations
        values = base_values + [v.lower() for v in base_values]

        start = time.perf_counter()
        resp = asyncio.get_event_loop().run_until_complete(
            engine_client.process_disambiguation(
                field_name="brand",
                values=values,
                similarity_threshold=0.85,
            )
        )
        rust_elapsed = time.perf_counter() - start

        assert resp is not None
        print(f"\nRust disambiguation (10k values): {rust_elapsed:.3f}s")
