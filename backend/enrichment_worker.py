import asyncio
import logging
import os

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend import models
from backend.adapters.enrichment.openalex import OpenAlexAdapter
from backend.adapters.enrichment.scholar import ScholarAdapter
from backend.adapters.enrichment.scopus import ScopusAdapter
from backend.adapters.enrichment.wos import WebOfScienceAdapter
from backend.circuit_breaker import CircuitBreaker, CircuitOpenError
from backend.tenant_access import LEGACY_GLOBAL_ORG_ID, scope_query_to_org

logger = logging.getLogger(__name__)


def _scholar_enabled() -> bool:
    return os.environ.get("SCHOLAR_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _scholar_use_free_proxies() -> bool:
    return os.environ.get("SCHOLAR_USE_FREE_PROXIES", "").strip().lower() in {"1", "true", "yes", "on"}

# Enrichment adapters — initialized once at module load
adapter_wos = WebOfScienceAdapter(api_key=os.environ.get("WOS_API_KEY"))
adapter_scopus = ScopusAdapter(api_key=os.environ.get("SCOPUS_API_KEY"))
adapter_openalex = OpenAlexAdapter()
adapter_scholar = ScholarAdapter(use_free_proxies=_scholar_use_free_proxies()) if _scholar_enabled() else None

# Circuit breakers — trip after 3 consecutive failures; recover after 60 s
_cb_wos = CircuitBreaker(name="wos", failure_threshold=3, recovery_timeout=60)
_cb_scopus = CircuitBreaker(name="scopus", failure_threshold=3, recovery_timeout=60)
_cb_openalex = CircuitBreaker(name="openalex", failure_threshold=3, recovery_timeout=60)
_cb_scholar = CircuitBreaker(name="scholar", failure_threshold=5, recovery_timeout=120)

# Any record stuck in "processing" for longer than this after a server
# crash will be reclaimed on the next startup.
VALID_STATUSES = {"none", "pending", "processing", "completed", "failed"}


def reset_stale_processing_records(db: Session) -> int:
    """
    Called once on startup. Resets records left in 'processing' status
    (caused by a server crash mid-enrichment) back to 'pending'.
    """
    result = db.execute(
        update(models.RawEntity)
        .where(models.RawEntity.enrichment_status == "processing")
        .values(enrichment_status="pending")
    )
    db.commit()
    count = result.rowcount
    if count:
        logger.warning(f"Startup: reset {count} stale 'processing' record(s) to 'pending'.")
    return count


def _atomic_claim_next(db: Session) -> int | None:
    """
    Atomically claims the next 'pending' record by setting its status to
    'processing'. Returns the claimed entity ID, or None if no record is available.

    Uses an optimistic two-step approach safe for SQLite:
    1. Find a candidate ID (SELECT).
    2. UPDATE ... WHERE id=<candidate> AND status='pending'.
       If another worker already claimed it, rowcount == 0 — we skip it.
    """
    candidate = (
        db.query(models.RawEntity.id)
        .filter(models.RawEntity.enrichment_status == "pending")
        .first()
    )
    if not candidate:
        return None

    entity_id = candidate[0]

    result = db.execute(
        update(models.RawEntity)
        .where(
            models.RawEntity.id == entity_id,
            models.RawEntity.enrichment_status == "pending",
        )
        .values(enrichment_status="processing")
    )
    db.commit()

    if result.rowcount == 0:
        # Another worker or endpoint raced us — try again next cycle
        return None

    return entity_id


def _extract_and_cache_country(entity: models.RawEntity) -> None:
    """Extract country from affiliation in attributes_json and cache it."""
    import json
    from backend.analyzers.geographic import extract_country

    try:
        attrs = json.loads(entity.attributes_json or "{}") or {}
    except (ValueError, TypeError):
        return

    if attrs.get("extracted_country"):
        return  # Already cached

    affiliation = None
    for key in ("affiliation", "affiliations", "institution"):
        val = attrs.get(key)
        if val:
            affiliation = str(val) if not isinstance(val, str) else val
            break

    if not affiliation:
        return

    country_code = extract_country(affiliation)
    if country_code:
        attrs["extracted_country"] = country_code
        entity.attributes_json = json.dumps(attrs)


def enrich_single_record(db: Session, entity: models.RawEntity) -> models.RawEntity:
    """
    Synchronously enriches a single record by title or DOI.
    Uses a cascade fallback strategy prioritizing Premium Data:
    Web of Science (BYOK) -> OpenAlex (Free API) -> Google Scholar (Scraping).
    """
    if not entity.primary_label:
        entity.enrichment_status = "failed"
        db.commit()
        return entity

    query = entity.primary_label
    enriched_data = None
    source = "Unknown"

    try:
        # Phase 3: Premium BYOK Priority
        # Phase 3: Premium BYOK Priority (Scopus -> WoS)
        if adapter_scopus.is_active:
            try:
                results_scopus = _cb_scopus.call(adapter_scopus.search_by_title, query, limit=1)
                if results_scopus:
                    enriched_data = results_scopus[0]
                    source = "Elsevier Scopus"
            except CircuitOpenError as e:
                logger.warning(str(e))

        if not enriched_data and adapter_wos.is_active:
            try:
                results_wos = _cb_wos.call(adapter_wos.search_by_title, query, limit=1)
                if results_wos:
                    enriched_data = results_wos[0]
                    source = "Web of Science"
            except CircuitOpenError as e:
                logger.warning(str(e))

        # Phase 1: Free Open API
        if not enriched_data:
            try:
                results = _cb_openalex.call(adapter_openalex.search_by_title, query, limit=1)
                if results:
                    enriched_data = results[0]
                    source = "OpenAlex"
                else:
                    # Phase 2: Scraping Fallback
                    if adapter_scholar is not None:
                        logger.info(f"OpenAlex found nothing for '{query}'. Falling back to Google Scholar.")
                        try:
                            results_scholar = _cb_scholar.call(adapter_scholar.search_by_title, query, limit=1)
                            if results_scholar:
                                enriched_data = results_scholar[0]
                                source = "Google Scholar"
                        except CircuitOpenError as e:
                            logger.warning(str(e))
                    else:
                        logger.info(
                            "OpenAlex found nothing for '%s'. Scholar fallback skipped because SCHOLAR_ENABLED is disabled.",
                            query,
                        )
            except CircuitOpenError as e:
                logger.warning(str(e))

        if enriched_data:
            entity.enrichment_doi = enriched_data.doi
            entity.enrichment_citation_count = enriched_data.citation_count
            entity.enrichment_concepts = (
                ", ".join(enriched_data.concepts) if enriched_data.concepts else None
            )
            entity.enrichment_source = source
            entity.enrichment_status = "completed"

            # Extract and cache country from affiliation data
            _extract_and_cache_country(entity)
        else:
            # Fallback: try active web scraper configs
            scraped = enrich_with_web_scrapers(db, entity)
            if not scraped:
                entity.enrichment_status = "failed"
                entity.enrichment_source = "None"

    except (ValueError, KeyError, AttributeError) as e:
        # Domain / data errors — mark failed, log details
        logger.error(f"Data error enriching record ID {entity.id}: {e}")
        entity.enrichment_status = "failed"
    except Exception as e:
        # Unexpected errors — mark failed but log at WARNING so they're visible
        logger.warning(f"Unexpected error enriching record ID {entity.id}: {type(e).__name__}: {e}")
        entity.enrichment_status = "failed"

    db.commit()
    return entity


async def background_enrichment_worker(db_generator):
    """
    Background async worker. Atomically claims and enriches 'pending' records
    one at a time with rate-limiting delays to avoid API bans.
    """
    await asyncio.sleep(5)  # Let the server finish booting

    while True:
        try:
            db = next(db_generator)

            entity_id = _atomic_claim_next(db)

            if entity_id is not None:
                entity = db.get(models.RawEntity, entity_id)
                if entity:
                    enrich_single_record(db, entity)
                db.close()
                await asyncio.sleep(2)  # Polite rate limiting
            else:
                db.close()
                await asyncio.sleep(10)  # No pending records — idle

        except Exception as e:
            logger.error(f"Background worker loop error: {type(e).__name__}: {e}")
            await asyncio.sleep(10)


def enrich_with_web_scrapers(db: Session, entity: models.RawEntity) -> bool:
    """
    Try active web scraper configs against *entity* in priority order.
    Returns True if any scraper successfully enriched the entity.
    Caller must commit after this returns.
    """
    from backend.adapters.web_scraper import ScrapeError, adapter_from_config
    from backend.circuit_breaker import CircuitBreaker, CircuitOpenError

    if not entity.primary_label:
        return False

    scope_org_id = getattr(entity, "org_id", None)
    if scope_org_id is None:
        scope_org_id = LEGACY_GLOBAL_ORG_ID

    configs = (
        scope_query_to_org(
            db.query(models.WebScraperConfig),
            models.WebScraperConfig,
            scope_org_id,
        )
        .filter(models.WebScraperConfig.is_active == True)  # noqa: E712
        .all()
    )

    for cfg in configs:
        cb = CircuitBreaker(
            name=f"web_scraper_{cfg.id}",
            failure_threshold=3,
            recovery_timeout=60,
        )
        adapter = adapter_from_config(cfg)
        try:
            fields = cb.call(adapter.scrape, entity.primary_label)
            if fields:
                for field, value in fields.items():
                    if hasattr(entity, field):
                        setattr(entity, field, value)
                entity.enrichment_source = cfg.name
                entity.enrichment_status = "completed"
                return True
        except CircuitOpenError as exc:
            logger.warning("Circuit open for web_scraper_%s: %s", cfg.id, exc)
        except ScrapeError as exc:
            logger.warning("Scrape error (scraper=%s, entity=%s): %s", cfg.id, entity.id, exc)

    return False


def trigger_enrichment_bulk(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    org_id: int | None = None,
    domain_id: str | None = None,
) -> int:
    """
    Marks a batch of 'none' or 'failed' entities as 'pending' so the background
    worker picks them up. Does NOT re-queue records already 'processing' or 'completed'.
    """
    entities = (
        scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        .filter(models.RawEntity.enrichment_status.in_(["none", "failed"]))
    )
    if domain_id and domain_id != "all":
        if domain_id == "default":
            entities = entities.filter(
                (models.RawEntity.domain == domain_id)
                | (models.RawEntity.domain == None)  # noqa: E711
            )
        else:
            entities = entities.filter(models.RawEntity.domain == domain_id)
    entities = entities.offset(skip).limit(limit).all()
    for entity in entities:
        entity.enrichment_status = "pending"
    db.commit()
    return len(entities)
