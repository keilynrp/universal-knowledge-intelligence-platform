"""OpenAlex adapter must retry on rate-limit/transient statuses (429/503) rather
than silently dropping the call (which made the journal backfill skip works)."""
from unittest.mock import MagicMock

import backend.adapters.enrichment.openalex as oa_mod
from backend.adapters.enrichment.openalex import OpenAlexAdapter, _SOURCE_CACHE
from backend.cache import make_key


def _resp(status, json_body=None, headers=None):
    m = MagicMock(status_code=status)
    m.headers = headers or {}
    m.json.return_value = json_body or {}
    return m


def _seq_get(responses):
    seq = list(responses)
    return lambda *a, **k: seq.pop(0)


def test_search_by_doi_retries_on_429(monkeypatch):
    monkeypatch.setattr(oa_mod.time, "sleep", lambda *_: None)  # no real wait
    adapter = OpenAlexAdapter()
    ok = {"results": [{"id": "https://openalex.org/W1", "display_name": "X"}]}
    monkeypatch.setattr(adapter.client, "get",
                        _seq_get([_resp(429, headers={"Retry-After": "1"}), _resp(200, ok)]))
    rec = adapter.search_by_doi("10.1/x")
    assert rec is not None  # retried past the 429 and parsed the 200


def test_fetch_source_metrics_retries_on_503(monkeypatch):
    monkeypatch.setattr(oa_mod.time, "sleep", lambda *_: None)
    _SOURCE_CACHE.delete(make_key(("source", "S429")))
    adapter = OpenAlexAdapter()
    body = {"id": "https://openalex.org/S429", "issn_l": "1234-5678", "display_name": "J",
            "summary_stats": {"2yr_mean_citedness": 1.0, "h_index": 2}, "topics": []}
    monkeypatch.setattr(adapter.client, "get",
                        _seq_get([_resp(503), _resp(200, body)]))
    jm = adapter.fetch_source_metrics("S429")
    assert jm is not None and jm.issn_l == "1234-5678"


def test_search_by_doi_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(oa_mod.time, "sleep", lambda *_: None)
    adapter = OpenAlexAdapter()
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: _resp(429))
    assert adapter.search_by_doi("10.1/x") is None  # persistent 429 → None, no crash


def test_non_rate_limit_error_is_not_retried(monkeypatch):
    """A 404 must NOT trigger retries — only 429/503 do."""
    monkeypatch.setattr(oa_mod.time, "sleep", lambda *_: None)
    _SOURCE_CACHE.delete(make_key(("source", "S404")))
    adapter = OpenAlexAdapter()
    calls = {"n": 0}

    def _get(*a, **k):
        calls["n"] += 1
        return _resp(404)

    monkeypatch.setattr(adapter.client, "get", _get)
    assert adapter.fetch_source_metrics("S404") is None
    assert calls["n"] == 1  # single attempt, no retry loop
