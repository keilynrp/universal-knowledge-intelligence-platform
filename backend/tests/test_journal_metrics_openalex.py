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
def _clear_s77_cache():
    """Remove any stale S77 entry from the shared module-level cache before each test."""
    _SOURCE_CACHE.delete(make_key(("source", "S77")))
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
    """fetch_source_metrics should return None when the API responds with non-200."""
    adapter = OpenAlexAdapter()
    fake = MagicMock(status_code=404)
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    result = adapter.fetch_source_metrics("S99_nonexistent")
    assert result is None


def test_fetch_source_metrics_returns_none_for_empty_source_id():
    adapter = OpenAlexAdapter()
    assert adapter.fetch_source_metrics("") is None
    assert adapter.fetch_source_metrics(None) is None


def test_fetch_source_metrics_apc_source_none_when_no_apc(monkeypatch):
    """apc_source should be None when apc_usd is absent from the response."""
    adapter = OpenAlexAdapter()
    # Use a unique key to avoid cache bleed
    _SOURCE_CACHE.delete(make_key(("source", "S_no_apc")))
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
