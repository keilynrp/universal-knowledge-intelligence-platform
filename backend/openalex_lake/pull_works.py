"""Targeted works puller — OpenAlex API -> DuckDB lake.

Pulls only the works matching a LakeScope (ISSN-L list × year window × optional
field/ROR/country) via server-side filters + cursor pagination, so the subset is
bounded without touching the 300 GB snapshot. Incremental refreshes use a
`from_updated_date` watermark, which makes this safe to schedule periodically.

Switching to the full corpus later is a scope change (drop the ISSN filter) or a
source swap (LakeScope.works_source = "snapshot"); the transform + store are
unchanged.

Run:  python -m backend.openalex_lake.pull_works [--incremental]
"""
from __future__ import annotations

import argparse
import dataclasses
import logging
import time
from datetime import date
from typing import Callable, Iterator, Optional

import httpx

from backend.openalex_lake.config import LakeScope, LakeSettings, default_scope, load_scored_issn_l
from backend.openalex_lake.store import LakeStore, RowBuffer
from backend.openalex_lake.transform import transform_work

logger = logging.getLogger(__name__)

WORKS_URL = "https://api.openalex.org/works"
PER_PAGE = 200            # OpenAlex max page size
# Fetch only the fields transform_work needs — roughly halves the page payload
# (8.9 MB -> 4.6 MB for 200 Nature works) and the parse cost.
_BASE_SELECT = (
    "id", "doi", "title", "display_name", "publication_year", "publication_date",
    "type", "cited_by_count", "primary_location", "open_access", "primary_topic",
    "topics", "counts_by_year", "authorships", "updated_date",
)
ISSN_CHUNK = 50           # keep the filter URL comfortably bounded
INTER_PAGE_DELAY = 0.1    # polite pacing between pages
_RETRY_STATUSES = frozenset({429, 503})
# Sustained pulls see 429 bursts even on the polite pool; be patient rather than
# crashing a multi-hour first pull. Honors Retry-After when present.
_MAX_RETRIES = 6
_MAX_BACKOFF = 60.0

# A fetch takes (url, params) and returns the parsed JSON body.
FetchFn = Callable[[str, dict], dict]


def chunk_issns(issns: list[str], size: int = ISSN_CHUNK) -> list[list[str]]:
    return [issns[i:i + size] for i in range(0, len(issns), size)] or [[]]


def parse_issn_list(raw: str) -> list[str]:
    """Comma-separated ISSN-L string -> deduped, trimmed list."""
    return list(dict.fromkeys(i.strip() for i in raw.split(",") if i.strip()))


def read_issn_file(path: str) -> list[str]:
    """One ISSN-L per line; blank lines and '#' comments ignored."""
    out: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return list(dict.fromkeys(out))


def build_filter(
    scope: LakeScope,
    issn_chunk: Optional[list[str]] = None,
    from_updated_date: Optional[str] = None,
) -> str:
    """Compose an OpenAlex `filter` string from the scope (AND of clauses)."""
    clauses: list[str] = []
    if issn_chunk:
        clauses.append("primary_location.source.issn:" + "|".join(issn_chunk))
    if scope.field_ids:
        clauses.append("primary_topic.field.id:" + "|".join(f"fields/{f}" for f in scope.field_ids))
    if scope.institution_ror:
        clauses.append(
            "authorships.institutions.ror:" + "|".join(f"https://ror.org/{r}" for r in scope.institution_ror)
        )
    if scope.country_codes:
        clauses.append(
            "authorships.institutions.country_code:" + "|".join(c.lower() for c in scope.country_codes)
        )
    if scope.year_from is not None:
        clauses.append(f"from_publication_date:{scope.year_from}-01-01")
    if scope.year_to is not None:
        clauses.append(f"to_publication_date:{scope.year_to}-12-31")
    if from_updated_date:
        clauses.append(f"from_updated_date:{from_updated_date}")
    return ",".join(clauses)


def _default_fetch(settings: LakeSettings) -> FetchFn:
    """Retry-aware httpx GET returning parsed JSON (mirrors OpenAlexAdapter)."""
    client = httpx.Client(timeout=30.0)

    def fetch(url: str, params: dict) -> dict:
        if settings.mailto:
            params = {**params, "mailto": settings.mailto}
        if settings.api_key:
            params = {**params, "api_key": settings.api_key}
        resp = client.get(url, params=params)
        for attempt in range(1, _MAX_RETRIES + 1):
            if resp.status_code not in _RETRY_STATUSES:
                break
            retry_after = resp.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else min(2.0 ** attempt, _MAX_BACKOFF)
            except (TypeError, ValueError):
                wait = min(2.0 ** attempt, _MAX_BACKOFF)
            time.sleep(wait)
            resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    return fetch


def select_fields(scope: LakeScope) -> str:
    """Comma-separated `select` list: only what transform_work reads."""
    fields = list(_BASE_SELECT)
    if scope.include_citations:
        fields.append("referenced_works")
    return ",".join(fields)


def iter_works(fetch: FetchFn, filter_str: str, select: Optional[str] = None) -> Iterator[dict]:
    """Cursor-paginate one filter combination, yielding raw works."""
    cursor = "*"
    while cursor:
        params = {"filter": filter_str, "per-page": PER_PAGE, "cursor": cursor}
        if select:
            params["select"] = select
        body = fetch(WORKS_URL, params)
        for work in body.get("results") or []:
            yield work
        cursor = (body.get("meta") or {}).get("next_cursor")
        if cursor:
            time.sleep(INTER_PAGE_DELAY)


def run_pull(
    scope: LakeScope,
    store: LakeStore,
    fetch: FetchFn,
    *,
    incremental: bool = False,
    watermark_key: str = "works",
    limit: Optional[int] = None,
    flush_every: int = 1000,
) -> dict:
    """Pull works for `scope` into `store`. Returns basic stats.

    `limit` caps the number of works (smoke test); a limited run is *partial* so
    it deliberately does NOT advance the watermark (that would skip data on the
    next real pull). Rows are buffered and flushed every `flush_every` works for
    bulk inserts.
    """
    from_updated = store.get_watermark(watermark_key) if incremental else None
    issn_chunks = chunk_issns(list(scope.issn_l)) if scope.issn_l else [None]
    run_started = date.today().isoformat()
    buffer = RowBuffer(store, flush_every=flush_every)

    select = select_fields(scope)
    works_seen = 0
    for chunk in issn_chunks:
        filter_str = build_filter(scope, chunk, from_updated)
        for work in iter_works(fetch, filter_str, select):
            buffer.add_work_rows(transform_work(work, include_citations=scope.include_citations))
            works_seen += 1
            if works_seen % 1000 == 0:
                logger.info("openalex-lake: %d works ingested…", works_seen)
            if limit is not None and works_seen >= limit:
                break
        if limit is not None and works_seen >= limit:
            break
    buffer.flush()

    limited = limit is not None and works_seen >= limit
    if not limited:  # advance watermark only after a full successful pass
        store.set_watermark(watermark_key, run_started)
    return {
        "works": works_seen,
        "limited": limited,
        "watermark": None if limited else run_started,
        "tables": store.summary(),
    }


def main() -> None:  # pragma: no cover - thin CLI wrapper
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Pull a targeted OpenAlex works subset into DuckDB.")
    parser.add_argument("--incremental", action="store_true", help="Only works updated since last run.")
    parser.add_argument("--include-citations", action="store_true", help="Also store referenced_works (heavy).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Smoke test: stop after N works (does not advance the watermark).")
    parser.add_argument("--issn", help="Comma-separated ISSN-L list (overrides journal_metrics).")
    parser.add_argument("--issn-file", help="File with one ISSN-L per line (overrides journal_metrics).")
    args = parser.parse_args()

    settings = LakeSettings()
    scope = default_scope()

    # Prefer explicit ISSNs (works in any env); else read the app's journal_metrics.
    issns: list[str] = []
    if args.issn:
        issns += parse_issn_list(args.issn)
    if args.issn_file:
        issns += read_issn_file(args.issn_file)
    if issns:
        scope = scope.with_issns(issns)
    else:
        from backend.database import SessionLocal
        with SessionLocal() as db:
            scope = scope.with_issns(load_scored_issn_l(db))

    if args.include_citations:
        scope = dataclasses.replace(scope, include_citations=True)

    if not scope.is_bounded():
        raise SystemExit(
            "Refusing to pull: scope is unbounded. Pass --issn / --issn-file, "
            "or populate journal_metrics."
        )

    with LakeStore(settings.db_path) as store:
        stats = run_pull(
            scope, store, _default_fetch(settings),
            incremental=args.incremental, limit=args.limit,
        )
    logger.info("openalex-lake pull complete: %s", stats)


if __name__ == "__main__":  # pragma: no cover
    main()
