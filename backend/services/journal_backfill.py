"""Surgical journal-metrics backfill for already-enriched works.

Populates ``journal_metrics`` (NIF base + APC) for works that were enriched
*before* the journal feature shipped, WITHOUT running the full enrichment
worker. ``enrich_single_record`` re-runs the legacy co-author edge path, which
re-inserts self-edges that violate ``uq_entity_relationships_pair_global`` and
rolls back the whole transaction (journal metric included). This module talks to
OpenAlex directly via each work's stored DOI, mirroring only the worker's
journal block (the ``upsert_journal_metric`` step), so it is safe to re-run.

Idempotent: ``only_missing=True`` skips works that already carry
``enrichment_issn_l``. Positive-only: a failed/empty lookup writes nothing.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy.orm import Session

from backend import models
from backend.adapters.enrichment.doaj import DoajAdapter
from backend.adapters.enrichment.openalex import OpenAlexAdapter, clear_source_cache
from backend.services.journal_metrics_service import upsert_journal_metric

logger = logging.getLogger(__name__)

# Module-level singleton so the OpenAlex source cache is shared across a run.
_default_openalex: Optional[OpenAlexAdapter] = None


def _get_openalex() -> OpenAlexAdapter:
    global _default_openalex
    if _default_openalex is None:
        _default_openalex = OpenAlexAdapter()
    return _default_openalex


def backfill_entity_journal(
    db: Session,
    entity: models.RawEntity,
    *,
    openalex: Optional[OpenAlexAdapter] = None,
    doaj_adapter: Optional[DoajAdapter] = None,
) -> bool:
    """Look up one work's OpenAlex source by DOI and upsert its JournalMetric.

    Returns True iff a journal metric was written. Does NOT commit — the caller
    owns the transaction so it can batch/commit and isolate per-entity failures.
    """
    openalex = openalex or _get_openalex()

    doi = getattr(entity, "enrichment_doi", None)
    if not doi:
        return False

    record = openalex.search_by_doi(doi)
    journal = getattr(record, "journal", None) if record else None
    if not journal or not journal.source_id:
        return False

    full = openalex.fetch_source_metrics(journal.source_id) or journal
    if not full.issn_l:
        full.issn_l = journal.issn_l
    if not full.issn_l:
        return False

    doaj_apc = None
    if full.is_in_doaj and full.issn_l:
        try:
            doaj_apc = (doaj_adapter or DoajAdapter()).fetch_apc(full.issn_l)
        except Exception:  # noqa: BLE001 — DOAJ is a non-essential override
            doaj_apc = None

    upsert_journal_metric(db, full, org_id=entity.org_id, doaj=doaj_apc)
    entity.enrichment_issn_l = full.issn_l
    return True


def backfill_all(
    db: Session,
    *,
    openalex: Optional[OpenAlexAdapter] = None,
    doaj_adapter: Optional[DoajAdapter] = None,
    only_missing: bool = True,
    limit: Optional[int] = None,
    delay: float = 0.0,
    refresh: bool = False,
) -> dict:
    """Backfill journal metrics for completed works that have a DOI.

    Commits per entity so one failure never discards prior progress. ``delay``
    sleeps that many seconds between works (polite-pool throttle to avoid
    OpenAlex 429s on large runs); the library default is 0 (no throttle) and the
    operator script opts into a delay. ``refresh`` clears the cached OpenAlex
    ``/sources`` metrics first, so a changed ``nif_field`` resolver recomputes
    instead of reusing stale (Redis-persisted) values. Returns
    ``{processed, written, skipped, errors}``.
    """
    openalex = openalex or _get_openalex()
    doaj_adapter = doaj_adapter or DoajAdapter()

    if refresh:
        cleared = clear_source_cache()
        logger.info("journal backfill: cleared %d cached OpenAlex source entries (refresh)", cleared)

    q = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.enrichment_doi.isnot(None))
    )
    if only_missing:
        q = q.filter(models.RawEntity.enrichment_issn_l.is_(None))
    if limit:
        q = q.limit(limit)

    processed = written = skipped = errors = 0
    for index, entity in enumerate(q.all()):
        if delay and index:
            time.sleep(delay)
        processed += 1
        try:
            if backfill_entity_journal(
                db, entity, openalex=openalex, doaj_adapter=doaj_adapter
            ):
                db.commit()
                written += 1
            else:
                db.rollback()
                skipped += 1
        except Exception:  # noqa: BLE001 — isolate one bad work, keep going
            db.rollback()
            errors += 1
            logger.warning(
                "journal backfill failed for entity %s", entity.id, exc_info=True
            )

    return {
        "processed": processed,
        "written": written,
        "skipped": skipped,
        "errors": errors,
    }
