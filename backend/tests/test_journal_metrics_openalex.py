"""Tests for OpenAlex adapter: journal/source identity in _parse_record and
cached fetch_source_metrics method.

Cache-determinism note: _SOURCE_CACHE is a module-level singleton (InProcessBackend
backed by a TTLCache). Two tests in the same session share it. We avoid bleed by:
  - test_parse_record_* uses no cache (only _parse_record, which doesn't call fetch).
  - test_fetch_source_metrics_parses_summary_stats uses a unique source_id ("S77")
    that no other test would populate. The first call always misses and runs the
    monkeypatched loader. If a future test uses "S77" first, the fixture below clears
    the cache entry before the test runs.
"""
import pytest
from unittest.mock import MagicMock
from backend.adapters.enrichment.openalex import OpenAlexAdapter, _SOURCE_CACHE
from backend.cache.base import make_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _work_with_source():
    return {
        "display_name": "Paper",
        "primary_location": {
            "source": {"id": "https://openalex.org/S77", "display_name": "Nat", "issn_l": "0028-0836"},
        },
        "authorships": [],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_cache_entries():
    """Remove all source-id cache entries used across this module before each test.

    This prevents cross-test bleed in the shared module-level InProcessBackend
    singleton, and guarantees each test starts from a cold-miss regardless of
    execution order or session reuse.
    """
    for sid in ("S77", "S99_nonexistent", "S_no_apc", "S_cache_hit_test"):
        _SOURCE_CACHE.delete(make_key(("source", sid)))
    yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_parse_record_captures_source_id_and_issn():
    rec = OpenAlexAdapter()._parse_record(_work_with_source())
    assert rec.journal is not None
    assert rec.journal.source_id == "S77"          # URL prefix stripped
    assert rec.journal.issn_l == "0028-0836"


def test_parse_record_journal_none_when_no_source():
    """_parse_record should not set journal when primary_location has no source."""
    work = {
        "display_name": "Paper without source",
        "primary_location": {},
        "authorships": [],
    }
    rec = OpenAlexAdapter()._parse_record(work)
    assert rec.journal is None


def test_parse_record_journal_none_when_no_primary_location():
    """_parse_record should not set journal when primary_location is absent."""
    work = {
        "display_name": "Paper without location",
        "authorships": [],
    }
    rec = OpenAlexAdapter()._parse_record(work)
    assert rec.journal is None


def test_fetch_source_metrics_parses_summary_stats(monkeypatch):
    adapter = OpenAlexAdapter()
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "id": "https://openalex.org/S77",
        "display_name": "Nat",
        "issn_l": "0028-0836",
        "summary_stats": {"2yr_mean_citedness": 17.4, "h_index": 1200},
        "apc_usd": 11690,
        "is_in_doaj": False,
    }
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    jm = adapter.fetch_source_metrics("S77")
    assert jm.two_yr_mean_citedness == 17.4
    assert jm.h_index == 1200
    assert jm.apc_usd == 11690
    assert jm.apc_source == "openalex"
    assert jm.is_in_doaj is False


def test_fetch_source_metrics_returns_none_on_non_200(monkeypatch):
    """fetch_source_metrics should return None when the API responds with non-200.

    The mock must actually be invoked (not a cached hit), and the result must NOT
    be stored in the cache (positive-only caching invariant).
    """
    adapter = OpenAlexAdapter()
    mock_get = MagicMock(return_value=MagicMock(status_code=404))
    monkeypatch.setattr(adapter.client, "get", mock_get)
    result = adapter.fetch_source_metrics("S99_nonexistent")
    assert result is None
    assert mock_get.call_count == 1, "Expected the HTTP client to be called exactly once"
    # A second call must also hit the network — non-200 must NOT be cached.
    result2 = adapter.fetch_source_metrics("S99_nonexistent")
    assert result2 is None
    assert mock_get.call_count == 2, "Non-200 response must not be cached; second call must reach the network"


def test_fetch_source_metrics_returns_none_for_empty_source_id():
    adapter = OpenAlexAdapter()
    assert adapter.fetch_source_metrics("") is None
    assert adapter.fetch_source_metrics(None) is None


def test_fetch_source_metrics_apc_source_none_when_no_apc(monkeypatch):
    """apc_source should be None when apc_usd is absent from the response."""
    adapter = OpenAlexAdapter()
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "id": "https://openalex.org/S_no_apc",
        "display_name": "Open Journal",
        "issn_l": "1234-5678",
        "summary_stats": {"2yr_mean_citedness": 1.2, "h_index": 10},
        "apc_usd": None,
        "is_in_doaj": True,
    }
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    jm = adapter.fetch_source_metrics("S_no_apc")
    assert jm.apc_source is None
    assert jm.is_in_doaj is True


def test_fetch_source_metrics_caches_positive_result(monkeypatch):
    """A successful 200 response is cached: the second call must NOT hit the network.

    Verifies the positive-only caching invariant: client.get is invoked exactly
    once across two fetch_source_metrics calls for the same source_id.
    """
    adapter = OpenAlexAdapter()
    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {
        "id": "https://openalex.org/S_cache_hit_test",
        "display_name": "Cached Journal",
        "issn_l": "9999-0001",
        "summary_stats": {"2yr_mean_citedness": 5.0, "h_index": 42},
        "apc_usd": 500,
        "is_in_doaj": True,
    }
    mock_get = MagicMock(return_value=fake_response)
    monkeypatch.setattr(adapter.client, "get", mock_get)

    # First call: cold miss — must call the network and populate the cache.
    jm1 = adapter.fetch_source_metrics("S_cache_hit_test")
    assert jm1 is not None
    assert jm1.display_name == "Cached Journal"
    assert mock_get.call_count == 1, "First call must reach the network (cold miss)"

    # Second call: cache hit — must NOT call the network again.
    jm2 = adapter.fetch_source_metrics("S_cache_hit_test")
    assert jm2 is not None
    assert jm2.two_yr_mean_citedness == 5.0
    assert mock_get.call_count == 1, "Second call must be served from cache (no extra network call)"
