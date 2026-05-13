#!/usr/bin/env python
"""
Generate data/demo/openalex_snapshot.json from live OpenAlex API.

Usage:
    python scripts/generate_openalex_snapshot.py

Fetches up to 1,000 records for concept C41008148 (Knowledge Management)
and writes them as a JSON array to data/demo/openalex_snapshot.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.adapters.enrichment.openalex import OpenAlexAdapter

_CONCEPT_ID = "C41008148"
_LIMIT = 1_000
_OUTPUT = Path("data/demo/openalex_snapshot.json")


def main() -> None:
    print(f"Fetching up to {_LIMIT} OpenAlex records (concept: {_CONCEPT_ID})...")
    adapter = OpenAlexAdapter()
    records = adapter.search_bulk(
        query="knowledge management",
        filters={"concept_id": _CONCEPT_ID},
        limit=_LIMIT,
    )

    if not records:
        print("ERROR: OpenAlex returned zero results. Check network.", file=sys.stderr)
        sys.exit(1)

    data = []
    for rec in records:
        data.append({
            "id": rec.id,
            "doi": rec.doi,
            "title": rec.title,
            "authors": rec.authors,
            "year": rec.publication_year,
            "citation_count": rec.citation_count,
            "concepts": rec.concepts,
            "publisher": rec.publisher,
            "is_open_access": rec.is_open_access,
        })

    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(data)} records to {_OUTPUT}")


if __name__ == "__main__":
    main()
