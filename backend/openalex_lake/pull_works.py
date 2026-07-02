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
import json
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
# Sustained pulls see transient 429/503 bursts; be patient rather than crashing.
_MAX_RETRIES = 6
_MAX_BACKOFF = 60.0
# OpenAlex enforces a daily request budget (x-ratelimit-remaining -> 0, with a
# multi-hour Retry-After). Don't sleep for hours or burn retries against it:
# stop cleanly above this threshold so the caller can resume after the reset.
_RATE_LIMIT_RETRY_AFTER_CAP = 300.0

# A fetch takes (url, params) and returns the parsed JSON body.
FetchFn = Callable[[str, dict], dict]


class RateLimitExhausted(Exception):
    """OpenAlex daily budget is spent — resume after `retry_after` seconds."""

    def __init__(self, retry_after: Optional[int] = None):
        super().__init__(f"OpenAlex rate limit exhausted; retry after {retry_after}s")
        self.retry_after = retry_after


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
    # httpx logs the full request URL at INFO — which would leak api_key (a
    # secret) into container/pull logs. Keep its request logger quiet; our own
    # "N works ingested" logs + status give progress.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    client = httpx.Client(timeout=30.0)

    def _retry_after_seconds(resp) -> Optional[float]:
        raw = resp.headers.get("Retry-After")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    def fetch(url: str, params: dict) -> dict:
        if settings.mailto:
            params = {**params, "mailto": settings.mailto}
        if settings.api_key:
            params = {**params, "api_key": settings.api_key}
        resp = client.get(url, params=params)
        for attempt in range(1, _MAX_RETRIES + 1):
            if resp.status_code not in _RETRY_STATUSES:
                break
            ra = _retry_after_seconds(resp)
            # Daily budget spent (remaining == 0 or a multi-hour Retry-After):
            # stop cleanly instead of sleeping for hours.
            if resp.status_code == 429 and (
                resp.headers.get("x-ratelimit-remaining") == "0"
                or (ra is not None and ra > _RATE_LIMIT_RETRY_AFTER_CAP)
            ):
                raise RateLimitExhausted(retry_after=int(ra) if ra is not None else None)
            wait = ra if ra is not None else min(2.0 ** attempt, _MAX_BACKOFF)
            time.sleep(min(wait, _MAX_BACKOFF))
            resp = client.get(url, params=params)
        if resp.status_code == 429:
            raise RateLimitExhausted(retry_after=int(_retry_after_seconds(resp) or 0) or None)
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


_DONE_ISSNS_KEY = "works_backfill_done_issns"


def _load_done_issns(store: LakeStore) -> set:
    raw = store.get_watermark(_DONE_ISSNS_KEY)
    return set(json.loads(raw)) if raw else set()


def _save_done_issns(store: LakeStore, done: set) -> None:
    store.set_watermark(_DONE_ISSNS_KEY, json.dumps(sorted(done)))


def run_pull(
    scope: LakeScope,
    store: LakeStore,
    fetch: FetchFn,
    *,
    incremental: bool = False,  # kept for CLI compat; mode is watermark-driven
    watermark_key: str = "works",
    limit: Optional[int] = None,
    flush_every: int = 1000,
) -> dict:
    """Pull works for `scope` into `store`, resumable across the daily quota.

    Mode is chosen by the watermark, so the same command works every run:
    - **backfill** (no watermark yet): iterate ISSNs one at a time, checkpointing
      each completed journal in `_meta`. If the daily rate limit is hit, stop and
      persist progress; the next run skips finished journals. When every journal
      is done, set the watermark and clear the checkpoint.
    - **incremental** (watermark set): batched `from_updated_date` delta pull.

    `limit` caps works (smoke test) and never advances the watermark.
    """
    existing_watermark = store.get_watermark(watermark_key)
    backfill = existing_watermark is None
    run_started = date.today().isoformat()
    buffer = RowBuffer(store, flush_every=flush_every)
    select = select_fields(scope)
    works_seen = 0
    rate_limited = False
    retry_after: Optional[int] = None
    limited = False

    if backfill and scope.issn_l:
        all_issns = list(dict.fromkeys(scope.issn_l))
        done = _load_done_issns(store)
        pending = [i for i in all_issns if i not in done]
        try:
            for issn in pending:
                for work in iter_works(fetch, build_filter(scope, [issn], None), select):
                    buffer.add_work_rows(transform_work(work, include_citations=scope.include_citations))
                    works_seen += 1
                    if works_seen % 1000 == 0:
                        logger.info("openalex-lake: %d works ingested…", works_seen)
                    if limit is not None and works_seen >= limit:
                        limited = True
                        break
                if limited:
                    break
                # Journal fully paginated — persist its rows, then checkpoint it.
                done.add(issn)
                buffer.flush()
                _save_done_issns(store, done)
        except RateLimitExhausted as exc:
            rate_limited = True
            retry_after = exc.retry_after
            logger.warning(
                "openalex-lake: daily rate limit hit; %d/%d journals done, resume in ~%ss",
                len(done), len(all_issns), retry_after,
            )
        buffer.flush()
        complete = len(done) >= len(all_issns) and not rate_limited and not limited
        if complete:
            store.set_watermark(watermark_key, run_started)
            _save_done_issns(store, set())  # clear -> future runs are incremental
        return {
            "mode": "backfill", "works": works_seen,
            "done_issns": len(done), "total_issns": len(all_issns),
            "complete": complete, "limited": limited,
            "rate_limited": rate_limited, "retry_after": retry_after,
            "watermark": run_started if complete else None,
            "tables": store.summary(),
        }

    # Incremental (or unbounded) path: batched chunks for fewer requests.
    from_updated = existing_watermark
    issn_chunks = chunk_issns(list(scope.issn_l)) if scope.issn_l else [None]
    try:
        for chunk in issn_chunks:
            for work in iter_works(fetch, build_filter(scope, chunk, from_updated), select):
                buffer.add_work_rows(transform_work(work, include_citations=scope.include_citations))
                works_seen += 1
                if works_seen % 1000 == 0:
                    logger.info("openalex-lake: %d works ingested…", works_seen)
                if limit is not None and works_seen >= limit:
                    limited = True
                    break
            if limited:
                break
    except RateLimitExhausted as exc:
        rate_limited = True
        retry_after = exc.retry_after
    buffer.flush()
    complete = not limited and not rate_limited
    if complete:
        store.set_watermark(watermark_key, run_started)
    return {
        "mode": "incremental", "works": works_seen, "limited": limited,
        "rate_limited": rate_limited, "retry_after": retry_after,
        "watermark": run_started if complete else None,
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
