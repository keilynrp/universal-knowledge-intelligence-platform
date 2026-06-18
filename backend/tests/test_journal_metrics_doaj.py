from unittest.mock import MagicMock
import pytest
from backend.adapters.enrichment.doaj import DoajAdapter, _DOAJ_CACHE
from backend.cache import MISS, make_key

# ---------------------------------------------------------------------------
# Autouse fixture — wipe the cache keys touched by these tests so each run
# starts deterministic regardless of ordering.
# ---------------------------------------------------------------------------
_TEST_ISSNS = ["0028-0836", "0000-0000", "1234-5678"]


@pytest.fixture(autouse=True, scope="module")
def clear_doaj_cache_keys():
    for issn in _TEST_ISSNS:
        _DOAJ_CACHE.delete(make_key(("doaj", issn)))
    yield
    for issn in _TEST_ISSNS:
        _DOAJ_CACHE.delete(make_key(("doaj", issn)))


# ---------------------------------------------------------------------------
# Spec tests (provided in task — must pass exactly as written)
# ---------------------------------------------------------------------------

def test_doaj_returns_apc_with_currency(monkeypatch):
    adapter = DoajAdapter()
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "results": [{"bibjson": {"apc": {"has_apc": True, "max": [{"price": 900, "currency": "EUR"}]}}}]
    }
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    apc = adapter.fetch_apc("0028-0836")
    assert apc == {"apc_amount": 900, "apc_currency": "EUR", "apc_source": "doaj", "is_in_doaj": True}


def test_doaj_no_result_returns_none(monkeypatch):
    adapter = DoajAdapter()
    fake = MagicMock(status_code=200)
    fake.json.return_value = {"results": []}
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    assert adapter.fetch_apc("0000-0000") is None


# ---------------------------------------------------------------------------
# Cache-hit test — positive result must be served from cache on second call
# ---------------------------------------------------------------------------

def test_doaj_positive_result_is_cached(monkeypatch):
    issn = "1234-5678"
    # Ensure clean slate for this specific key
    _DOAJ_CACHE.delete(make_key(("doaj", issn)))

    adapter = DoajAdapter()
    mock_get = MagicMock()
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "results": [{"bibjson": {"apc": {"has_apc": True, "max": [{"price": 500, "currency": "USD"}]}}}]
    }
    mock_get.return_value = fake
    monkeypatch.setattr(adapter.client, "get", mock_get)

    # First call — hits network
    result1 = adapter.fetch_apc(issn)
    assert result1 == {"apc_amount": 500, "apc_currency": "USD", "apc_source": "doaj", "is_in_doaj": True}
    assert mock_get.call_count == 1

    # Second call — must be served from cache, no additional network hit
    result2 = adapter.fetch_apc(issn)
    assert result2 == result1
    assert mock_get.call_count == 1  # still 1, not 2


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------

def test_doaj_no_apc_returns_none_amounts(monkeypatch):
    adapter = DoajAdapter()
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "results": [{"bibjson": {"apc": {"has_apc": False}}}]
    }
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    result = adapter.fetch_apc("9999-0001")
    assert result == {"apc_amount": None, "apc_currency": None, "apc_source": "doaj", "is_in_doaj": True}


def test_doaj_non_200_returns_none_not_cached(monkeypatch):
    adapter = DoajAdapter()
    fake = MagicMock(status_code=503)
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    result = adapter.fetch_apc("9999-0002")
    assert result is None
    # Verify it was not cached — the next call should still hit the network
    mock_get = MagicMock(return_value=fake)
    monkeypatch.setattr(adapter.client, "get", mock_get)
    adapter.fetch_apc("9999-0002")
    assert mock_get.call_count == 1  # would be 0 if it had been cached


def test_doaj_empty_issn_returns_none():
    adapter = DoajAdapter()
    assert adapter.fetch_apc("") is None
    assert adapter.fetch_apc(None) is None


def test_doaj_network_error_returns_none(monkeypatch):
    adapter = DoajAdapter()
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: (_ for _ in ()).throw(Exception("timeout")))
    assert adapter.fetch_apc("9999-0003") is None
