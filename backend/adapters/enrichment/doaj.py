"""DOAJ adapter — look up APC (amount + currency) for Open Access journals by ISSN.

Uses the DOAJ public API v2. Results are cached positively only (never caches
None) to avoid suppressing journals that might be added to DOAJ later or were
temporarily unavailable due to a network/server error.
"""
from __future__ import annotations

from typing import Optional

import httpx

from backend.cache import MISS, get_cache, make_key

_DOAJ_CACHE = get_cache("enrichment:doaj_apc", ttl=7 * 24 * 3600, maxsize=20_000)


class DoajAdapter:
    """Lookup APC (amount + currency) for Open Access journals via DOAJ."""

    BASE_URL = "https://doaj.org/api/v2/search/journals/issn:"

    def __init__(self) -> None:
        self.client = httpx.Client(timeout=10.0)

    def fetch_apc(self, issn: str) -> Optional[dict]:
        """Return APC info for the given ISSN, or None if not found / unavailable.

        Returns a dict with keys:
            apc_amount    — int/float or None
            apc_currency  — str or None
            apc_source    — always "doaj"
            is_in_doaj    — always True (only set when journal is found)

        None is returned for:
          - empty/None ISSN
          - journal not listed in DOAJ (not cached — may be added later)
          - non-200 HTTP response (transient failure — not cached)
          - network error (not cached)
        """
        if not issn:
            return None

        key = make_key(("doaj", issn))
        cached = _DOAJ_CACHE.get(key)
        if cached is not MISS:
            return cached  # positive hit only; we never store None

        try:
            resp = self.client.get(f"{self.BASE_URL}{issn}")
        except Exception:
            return None  # network error — do NOT cache

        if resp.status_code != 200:
            return None  # transient failure — do NOT cache

        results = resp.json().get("results", [])
        if not results:
            return None  # journal not in DOAJ — do NOT cache (may be added later)

        apc = results[0].get("bibjson", {}).get("apc", {}) or {}
        if not apc.get("has_apc"):
            result: dict = {
                "apc_amount": None,
                "apc_currency": None,
                "apc_source": "doaj",
                "is_in_doaj": True,
            }
        else:
            prices = apc.get("max", []) or []
            if not prices:
                result = {
                    "apc_amount": None,
                    "apc_currency": None,
                    "apc_source": "doaj",
                    "is_in_doaj": True,
                }
            else:
                result = {
                    "apc_amount": prices[0].get("price"),
                    "apc_currency": prices[0].get("currency"),
                    "apc_source": "doaj",
                    "is_in_doaj": True,
                }

        _DOAJ_CACHE.set(key, result)
        return result
