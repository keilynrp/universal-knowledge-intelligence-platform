"""Integration tests for engine routing in the ingest pipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_engine(*, fail=False):
    engine = MagicMock()
    if fail:
        engine.process_sync = AsyncMock(side_effect=Exception("engine down"))
        engine.process_async = AsyncMock(side_effect=Exception("engine down"))
    else:
        result = MagicMock(nodes_created=5, relationships_created=10)
        resp = MagicMock(result=result, job_id="job-1")
        engine.process_sync = AsyncMock(return_value=resp)
        engine.process_async = AsyncMock(return_value=resp)
    return engine


def _make_request(engine=None):
    request = MagicMock()
    request.app.state.engine_client = engine
    return request


def _make_db(entities=None):
    """Mock a SQLAlchemy session whose query chain returns given entities."""
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.all.return_value = entities or []
    db.query.return_value = q
    return db


def _python_result():
    return {"publications": 2, "nodes_created": 3, "relationships_created": 5}


# ── no engine configured ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_engine_uses_python_fallback(monkeypatch):
    """When engine is None, Python graph_materializer is called directly."""
    from backend.routers.ingest import _materialize_graph

    monkeypatch.setenv("ENGINE_SHADOW_MODE", "false")
    request = _make_request(engine=None)

    with patch("backend.routers.ingest.materialize_scientific_import_graph",
               return_value=_python_result()) as mock_py:
        result = await _materialize_graph(
            request=request, db=_make_db(), import_batch_id=1, org_id=None, domain="science"
        )

    mock_py.assert_called_once()
    assert result["nodes_created"] == 3


# ── shadow mode ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_shadow_mode_returns_python_result(monkeypatch):
    """Shadow mode: Python result is returned, engine fires async for comparison."""
    from backend.routers.ingest import _materialize_graph

    monkeypatch.setenv("ENGINE_SHADOW_MODE", "true")
    engine = _make_engine()
    request = _make_request(engine=engine)
    mock_entities = [MagicMock(id=i) for i in range(2)]

    with patch("backend.routers.ingest.materialize_scientific_import_graph",
               return_value=_python_result()) as mock_py, \
         patch("backend.routers.ingest.engine_bridge.entity_to_publication",
               return_value=MagicMock()), \
         patch("asyncio.ensure_future"):
        result = await _materialize_graph(
            request=request, db=_make_db(mock_entities), import_batch_id=1, org_id=None, domain="science"
        )

    mock_py.assert_called_once()
    assert result["nodes_created"] == 3
    assert result["engine_mode"] == "shadow"


# ── primary mode (engine success) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_primary_mode_uses_engine_sync(monkeypatch):
    """Primary mode with ≤ threshold pubs → process_sync is called."""
    from backend.routers.ingest import _materialize_graph

    monkeypatch.setenv("ENGINE_SHADOW_MODE", "false")
    monkeypatch.setenv("ENGINE_SYNC_THRESHOLD", "500")
    engine = _make_engine()
    request = _make_request(engine=engine)
    mock_entities = [MagicMock(id=i) for i in range(3)]

    with patch("backend.routers.ingest.engine_bridge.entity_to_publication",
               return_value=MagicMock()), \
         patch("backend.routers.ingest.materialize_scientific_import_graph") as mock_py:
        result = await _materialize_graph(
            request=request, db=_make_db(mock_entities), import_batch_id=1, org_id=None, domain="science"
        )

    engine.process_sync.assert_called_once()
    mock_py.assert_not_called()
    assert result["engine_mode"] == "primary"
    assert result["nodes_created"] == 5


# ── primary mode (engine failure + fallback) ──────────────────────────────────

@pytest.mark.asyncio
async def test_engine_failure_falls_back_to_python(monkeypatch):
    """Engine raises → fallback to Python when ENGINE_FALLBACK_PYTHON=true."""
    from backend.routers.ingest import _materialize_graph

    monkeypatch.setenv("ENGINE_SHADOW_MODE", "false")
    monkeypatch.setenv("ENGINE_FALLBACK_PYTHON", "true")
    engine = _make_engine(fail=True)
    request = _make_request(engine=engine)
    mock_entities = [MagicMock(id=1)]

    with patch("backend.routers.ingest.engine_bridge.entity_to_publication",
               return_value=MagicMock()), \
         patch("backend.routers.ingest.materialize_scientific_import_graph",
               return_value=_python_result()) as mock_py:
        result = await _materialize_graph(
            request=request, db=_make_db(mock_entities), import_batch_id=1, org_id=None, domain="science"
        )

    mock_py.assert_called_once()
    assert result["engine_mode"] == "fallback"
    assert result["nodes_created"] == 3


# ── primary mode (engine failure + no fallback) ───────────────────────────────

@pytest.mark.asyncio
async def test_engine_failure_no_fallback_returns_zeros(monkeypatch):
    """Engine fails + fallback disabled → zero-count result, Python not called."""
    from backend.routers.ingest import _materialize_graph

    monkeypatch.setenv("ENGINE_SHADOW_MODE", "false")
    monkeypatch.setenv("ENGINE_FALLBACK_PYTHON", "false")
    engine = _make_engine(fail=True)
    request = _make_request(engine=engine)
    mock_entities = [MagicMock(id=1)]

    with patch("backend.routers.ingest.engine_bridge.entity_to_publication",
               return_value=MagicMock()), \
         patch("backend.routers.ingest.materialize_scientific_import_graph") as mock_py:
        result = await _materialize_graph(
            request=request, db=_make_db(mock_entities), import_batch_id=1, org_id=None, domain="science"
        )

    mock_py.assert_not_called()
    assert result["engine_mode"] == "skipped"
    assert result["nodes_created"] == 0


# ── async threshold routing ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_large_batch_uses_process_async(monkeypatch):
    """Publications > sync threshold → process_async is called."""
    from backend.routers.ingest import _materialize_graph

    monkeypatch.setenv("ENGINE_SHADOW_MODE", "false")
    monkeypatch.setenv("ENGINE_SYNC_THRESHOLD", "2")
    monkeypatch.setenv("ENGINE_FALLBACK_PYTHON", "true")
    engine = _make_engine()
    request = _make_request(engine=engine)
    mock_entities = [MagicMock(id=i) for i in range(5)]  # 5 > threshold 2

    with patch("backend.routers.ingest.engine_bridge.entity_to_publication",
               return_value=MagicMock()), \
         patch("backend.routers.ingest.materialize_scientific_import_graph"):
        await _materialize_graph(
            request=request, db=_make_db(mock_entities), import_batch_id=1, org_id=None, domain="science"
        )

    engine.process_async.assert_called_once()
    engine.process_sync.assert_not_called()
