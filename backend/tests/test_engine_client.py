"""Tests for engine gRPC client."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.engine_client import EngineClient


@pytest.mark.asyncio
async def test_health_returns_false_when_no_url():
    """When engine URL is empty, health returns False without connecting."""
    client = EngineClient(grpc_url="", auth_token="test")
    result = await client.health()
    assert result is False


@pytest.mark.asyncio
async def test_process_sync_returns_none_when_no_url():
    """process_sync returns None when engine is not configured."""
    client = EngineClient(grpc_url="", auth_token="test")
    result = await client.process_sync(
        pipeline="graph_materialization",
        job_id="test-job",
        import_batch_id=1,
        domain="science",
        publications=[],
    )
    assert result is None


@pytest.mark.asyncio
async def test_health_returns_false_on_grpc_error():
    """health returns False when gRPC channel raises an exception."""
    client = EngineClient(grpc_url="localhost:99999", auth_token="test")
    # Force channel creation to fail
    with patch("grpc.aio.insecure_channel", side_effect=Exception("connection refused")):
        result = await client.health()
    assert result is False


@pytest.mark.asyncio
async def test_health_returns_true_when_stub_healthy():
    """health returns True when stub returns healthy=True."""
    client = EngineClient(grpc_url="localhost:50051", auth_token="test")

    mock_stub = MagicMock()
    mock_stub.Health = AsyncMock(return_value=MagicMock(healthy=True))

    client._channel = MagicMock()
    client._stub = mock_stub

    with patch("backend.proto.ukip.engine.v1.engine_pb2.HealthRequest", return_value=MagicMock()):
        result = await client.health()

    assert result is True


@pytest.mark.asyncio
async def test_process_sync_builds_correct_request():
    """process_sync sends a ProcessRequest and returns the response."""
    client = EngineClient(grpc_url="localhost:50051", auth_token="test")

    mock_response = MagicMock()
    mock_response.status = 3  # COMPLETED
    mock_response.result = MagicMock(nodes_created=5, relationships_created=10)

    mock_stub = MagicMock()
    mock_stub.ProcessSync = AsyncMock(return_value=mock_response)

    client._channel = MagicMock()
    client._stub = mock_stub

    with patch("backend.proto.ukip.engine.v1.engine_pb2.ProcessRequest", return_value=MagicMock()):
        result = await client.process_sync(
            pipeline="graph_materialization",
            job_id="test-job",
            import_batch_id=1,
            domain="science",
            publications=[],
        )

    assert result is not None
    assert result.status == 3


@pytest.mark.asyncio
async def test_get_job_status_returns_none_when_no_url():
    """get_job_status returns None when engine is not configured."""
    client = EngineClient(grpc_url="")
    result = await client.get_job_status("nonexistent-job")
    assert result is None


@pytest.mark.asyncio
async def test_close_clears_channel():
    """close() resets channel and stub to None."""
    client = EngineClient(grpc_url="localhost:50051")
    client._channel = AsyncMock()
    client._channel.close = AsyncMock()
    client._stub = MagicMock()

    await client.close()

    assert client._channel is None
    assert client._stub is None
