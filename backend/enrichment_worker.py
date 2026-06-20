import asyncio
import json
import logging
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend import models
from backend.schemas import EnrichmentStatus
from backend.adapters.enrichment.openalex import OpenAlexAdapter
from backend.adapters.enrichment.scopus import ScopusAdapter
from backend.adapters.enrichment.wos import WebOfScienceAdapter
from backend.adapters.enrichment.crossref import CrossrefAdapter
from backend.adapters.enrichment.pubmed import PubMedAdapter
from backend.adapters.enrichment.dblp import DBLPAdapter
from backend.circuit_breaker import CircuitBreaker, CircuitOpenError
from backend.tenant_access import LEGACY_GLOBAL_ORG_ID, scope_query_to_org
from backend.domain_scope import parse_scope, resolve_domain_filter

logger = logging.getLogger(__name__)


def _jsonable_model(value):
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_jsonable_model(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable_model(item) for key, item in value.items()}
    return value


def _scholar_enabled() -> bool:
    return os.environ.get("SCHOLAR_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _scholar_use_free_proxies() -> bool:
    return os.environ.get("SCHOLAR_USE_FREE_PROXIES", "").strip().lower() in {"1", "true", "yes", "on"}

# Enrichment adapters — initialized once at module load
adapter_wos = WebOfScienceAdapter(api_key=os.environ.get("WOS_API_KEY"))
adapter_scopus = ScopusAdapter(api_key=os.environ.get("SCOPUS_API_KEY"))
adapter_openalex = OpenAlexAdapter()
adapter_crossref = CrossrefAdapter()
adapter_pubmed = PubMedAdapter()
adapter_dblp = DBLPAdapter()
adapter_s2 = None  # Lazy-import to avoid hard dep on semantic_scholar module at startup
try:
    from backend.adapters.enrichment.semantic_scholar import SemanticScholarAdapter
    adapter_s2 = SemanticScholarAdapter()
except ImportError:
    logger.info("SemanticScholarAdapter not available — skipping.")

adapter_scholar = None
if _scholar_enabled():
    try:
        from backend.adapters.enrichment.scholar import ScholarAdapter
        adapter_scholar = ScholarAdapter(use_free_proxies=_scholar_use_free_proxies())
    except ImportError:
        logger.warning("SCHOLAR_ENABLED=1 but 'scholarly' is not installed. Install via: pip install -r requirements-scholar.txt")

# Circuit breakers — trip after 3 consecutive failures; recover after 60 s
_cb_wos = CircuitBreaker(name="wos", failure_threshold=3, recovery_timeout=60)
_cb_scopus = CircuitBreaker(name="scopus", failure_threshold=3, recovery_timeout=60)
_cb_openalex = CircuitBreaker(name="openalex", failure_threshold=3, recovery_timeout=60)
_cb_crossref = CircuitBreaker(name="crossref", failure_threshold=3, recovery_timeout=60)
_cb_pubmed = CircuitBreaker(name="pubmed", failure_threshold=3, recovery_timeout=60)
_cb_s2 = CircuitBreaker(name="semantic_scholar", failure_threshold=3, recovery_timeout=90)
_cb_dblp = CircuitBreaker(name="dblp", failure_threshold=3, recovery_timeout=60)
_cb_scholar = CircuitBreaker(name="scholar", failure_threshold=5, recovery_timeout=120)

# ── Provider Registry ────────────────────────────────────────────────────────
# Maps provider ID → (adapter_instance, circuit_breaker)
# Default cascade order: BYOK first, then free by coverage breadth
_DEFAULT_CASCADE = ["scopus", "wos", "openalex", "crossref", "pubmed", "semantic_scholar", "dblp", "scholar"]

_PROVIDER_MAP: dict[str, tuple] = {
    "scopus": (adapter_scopus, _cb_scopus),
    "wos": (adapter_wos, _cb_wos),
    "openalex": (adapter_openalex, _cb_openalex),
    "crossref": (adapter_crossref, _cb_crossref),
    "pubmed": (adapter_pubmed, _cb_pubmed),
    "semantic_scholar": (adapter_s2, _cb_s2),
    "dblp": (adapter_dblp, _cb_dblp),
    "scholar": (adapter_scholar, _cb_scholar),
}


def _parse_cascade() -> list[str]:
    """Parse ENRICHMENT_CASCADE env var or return default order."""
    raw = os.environ.get("ENRICHMENT_CASCADE", "").strip()
    if not raw:
        return _DEFAULT_CASCADE
    names = [n.strip() for n in raw.split(",") if n.strip()]
    valid = []
    for name in names:
        if name in _PROVIDER_MAP:
            valid.append(name)
        else:
            logger.warning("ENRICHMENT_CASCADE: unrecognized provider '%s' — skipping.", name)
    return valid if valid else _DEFAULT_CASCADE


_ACTIVE_CASCADE: list[str] = _parse_cascade()


def get_provider_registry() -> dict[str, tuple]:
    """Returns the provider registry for introspection (used by /enrichment/providers)."""
    return {name: _PROVIDER_MAP[name] for name in _ACTIVE_CASCADE if name in _PROVIDER_MAP}


# ── Circuit breaker registry — used by /enrichment/sources/health endpoint ───
# Exposes all circuit breakers for real-time state introspection from the API.
_CB_REGISTRY: dict[str, "CircuitBreaker"] = {
    "scopus":            _cb_scopus,
    "wos":               _cb_wos,
    "openalex":          _cb_openalex,
    "crossref":          _cb_crossref,
    "pubmed":            _cb_pubmed,
    "semantic_scholar":  _cb_s2,
    "dblp":              _cb_dblp,
    "scholar":           _cb_scholar,
}


# ── Failure reason constants ──────────────────────────────────────────────────
class EnrichmentFailureReason:
    """Machine-readable failure category stored on enrichment_failure_reason."""
    NO_MATCH           = "no_match"           # All sources searched, no usable record
    API_ERROR          = "api_error"          # Source returned non-rate-limit 4xx/5xx
    RATE_LIMITED       = "rate_limited"       # Source returned 429
    CIRCUIT_OPEN       = "circuit_open"       # Circuit breaker was OPEN, call skipped
    TIMEOUT            = "timeout"            # Request exceeded configured timeout
    ALL_SOURCES_FAILED = "all_sources_failed" # Every source attempted, all failed

# Any record stuck in "processing" for longer than this after a server
# crash will be reclaimed on the next startup.
VALID_STATUSES = {s.value for s in EnrichmentStatus}

_FAILURE_RECOMMENDATIONS = {
    "missing_title": [
        "Complete el título o etiqueta principal antes de reintentar.",
        "Incluya un identificador estable como DOI si está disponible.",
    ],
    "no_provider_match": [
        "Revise que el título no tenga abreviaturas, HTML residual o errores tipográficos.",
        "Agregue o corrija el DOI para aumentar la probabilidad de coincidencia.",
        "Active una fuente adicional de enriquecimiento si el registro no está cubierto por OpenAlex.",
    ],
    "data_error": [
        "Revise DOI, título, autores y metadatos base del registro.",
        "Reintente el enriquecimiento después de corregir los campos incompletos o inconsistentes.",
    ],
    "unexpected_error": [
        "Reintente el enriquecimiento; si se repite, revise los logs del backend.",
        "Verifique conectividad y configuración de las fuentes externas activas.",
    ],
}


def _attrs(entity: models.RawEntity) -> dict:
    try:
        parsed = json.loads(entity.attributes_json or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _clear_enrichment_failure(entity: models.RawEntity) -> None:
    attrs = _attrs(entity)
    if attrs.pop("enrichment_failure", None) is not None:
        entity.attributes_json = json.dumps(attrs, ensure_ascii=False)


def clear_enrichment_failure(entity: models.RawEntity) -> None:
    """Public wrapper used by routers when re-queueing explicit records."""

    _clear_enrichment_failure(entity)


def _set_enrichment_failed(
    entity: models.RawEntity,
    *,
    code: str,
    evidence: str,
    provider_attempts: list[str] | None = None,
    exception_type: str | None = None,
    failure_reason: str | None = None,
) -> None:
    attrs = _attrs(entity)
    attrs["enrichment_failure"] = {
        "code": code,
        "evidence": evidence,
        "recommendations": _FAILURE_RECOMMENDATIONS.get(code, _FAILURE_RECOMMENDATIONS["unexpected_error"]),
        "provider_attempts": provider_attempts or [],
        "exception_type": exception_type,
        "record_snapshot": {
            "primary_label": entity.primary_label,
            "canonical_id": entity.canonical_id,
            "enrichment_doi": entity.enrichment_doi,
            "domain": entity.domain,
        },
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    entity.attributes_json = json.dumps(attrs, ensure_ascii=False)
    entity.enrichment_status = EnrichmentStatus.failed
    if failure_reason is not None:
        entity.enrichment_failure_reason = failure_reason


def reset_stale_processing_records(db: Session) -> int:
    """
    Called once on startup. Resets records left in 'processing' status
    (caused by a server crash mid-enrichment) back to 'pending'.
    """
    result = db.execute(
        update(models.RawEntity)
        .where(models.RawEntity.enrichment_status == EnrichmentStatus.processing)
        .values(enrichment_status=EnrichmentStatus.pending.value)
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
        .filter(models.RawEntity.enrichment_status == EnrichmentStatus.pending)
        .first()
    )
    if not candidate:
        return None

    entity_id = candidate[0]

    result = db.execute(
        update(models.RawEntity)
        .where(
            models.RawEntity.id == entity_id,
            models.RawEntity.enrichment_status == EnrichmentStatus.pending,
        )
        .values(enrichment_status=EnrichmentStatus.processing.value)
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


def _extract_and_persist_coauthor_edges(db: Session, entity: models.RawEntity) -> None:
    """Materialize CO_AUTHOR edges from this entity's `enrichment_authors`.

    The coauthorship analyzer reads ``entity_relationships`` rows with
    ``relation_type='CO_AUTHOR'``. Without this hook the table would stay
    empty for entities enriched by the worker, even though the structured
    author list is already on ``attributes_json``.
    """
    from backend.analyzers.coauthorship import authors_from_attrs, extract_coauthor_edges

    authors = authors_from_attrs(entity.attributes_json)
    if len(authors) < 2:
        return

    try:
        extract_coauthor_edges(
            entity.id,
            authors,
            db,
            org_id=getattr(entity, "org_id", None),
        )
    except Exception:
        logger.exception(
            "coauthor edge extraction failed for entity %s", entity.id,
        )


def write_coauthor_artifacts(db: Session, entity: models.RawEntity, *, force: bool = False) -> None:
    """Write V2 coauthorship rows for one entity. Idempotent.

    Gated by ``config.COAUTHOR_V2_WRITE`` unless ``force=True`` (the migration
    script orchestrates writes regardless of the runtime flag — safer than
    mutating the global flag).

    **Transaction ownership: the caller owns the outer commit.** This helper
    resolves authors via ``get_or_create_author`` (which commits author rows on
    its own) and then stages publications / edges / contributions plus the
    dirty-scope marker WITHOUT committing them. The caller commits so the
    coauthor write lands as one unit with — or right after — the enrichment.

    Does NOT touch legacy ``entity_relationships`` (spec Appendix B item 2).
    The V2 legacy/global scope sentinel is ``org_id = 0`` (distinct from
    tenant_access's ``LEGACY_GLOBAL_ORG_ID = -1``); a NULL entity org maps to 0.
    """
    from itertools import combinations

    from sqlalchemy.exc import IntegrityError

    from backend import config
    from backend.analyzers.coauthorship import authors_from_attrs, MAX_AUTHORS_FOR_COAUTH
    from backend.coauthorship.identity import get_or_create_author

    if not force and not config.COAUTHOR_V2_WRITE:
        return

    authors = authors_from_attrs(entity.attributes_json)
    if len(authors) < 2:
        return

    org_id = entity.org_id if entity.org_id is not None else 0
    domain_id = entity.domain or "default"

    # 1. Resolve authors (get_or_create commits author rows individually).
    author_ids: list[tuple[int, int]] = []
    for pos, name in enumerate(authors[:MAX_AUTHORS_FOR_COAUTH], start=1):
        a = get_or_create_author(db, name)
        author_ids.append((a.id, pos))

    # 2. Tenancy reassignment: if this entity's publications were previously
    #    recorded under a different scope, move them and enqueue the old scope
    #    for recompute (its edges lose this entity's contributions).
    prior_scopes = {
        (p.org_id, p.domain_id)
        for p in db.query(models.AuthorPublication).filter_by(entity_id=entity.id).all()
    }
    if prior_scopes and (org_id, domain_id) not in prior_scopes:
        for prior_org, prior_dom in prior_scopes:
            db.merge(models.CoauthorDirtyScope(
                org_id=prior_org, domain_id=prior_dom, reason="reassign"))
        db.query(models.AuthorPublication).filter_by(entity_id=entity.id).update(
            {"org_id": org_id, "domain_id": domain_id}, synchronize_session=False)
        db.query(models.CoauthorContribution).filter_by(entity_id=entity.id).delete(
            synchronize_session=False)

    # 3. Upsert publications (idempotent via PK on author_id + entity_id).
    existing_pubs = {
        p.author_id
        for p in db.query(models.AuthorPublication.author_id)
        .filter_by(entity_id=entity.id)
        .all()
    }
    for aid, pos in author_ids:
        if aid not in existing_pubs:
            db.add(models.AuthorPublication(
                author_id=aid, entity_id=entity.id,
                org_id=org_id, domain_id=domain_id, position=pos))

    # 4. Flush publications BEFORE the contribution loop. A contribution
    #    SAVEPOINT rollback must not discard the publications added above.
    db.flush()

    # 5. One contribution per (entity, author_a, author_b) triple; each triple
    #    increments the edge weight exactly once. SAVEPOINT per pair so a
    #    duplicate contribution rolls back only itself.
    for (a_id, _), (b_id, _) in combinations(author_ids, 2):
        if a_id == b_id:
            continue  # same author resolved twice (e.g. name collision) -> no self-edge
        lo, hi = sorted([a_id, b_id])
        try:
            with db.begin_nested():
                db.add(models.CoauthorContribution(
                    entity_id=entity.id, author_a_id=lo, author_b_id=hi,
                    org_id=org_id, domain_id=domain_id))
                db.flush()
        except IntegrityError:
            continue  # already counted — skip the edge increment

        edge = (
            db.query(models.CoauthorEdge)
            .filter_by(author_a_id=lo, author_b_id=hi, org_id=org_id, domain_id=domain_id)
            .first()
        )
        if edge:
            edge.weight += 1
            edge.last_seen_at = datetime.now(timezone.utc)
        else:
            db.add(models.CoauthorEdge(
                author_a_id=lo, author_b_id=hi,
                org_id=org_id, domain_id=domain_id, weight=1))

    # 6. Enqueue the current scope for recompute. Caller commits.
    db.merge(models.CoauthorDirtyScope(org_id=org_id, domain_id=domain_id, reason="enrichment"))


def _try_epistemic_classify(db: Session, entity: models.RawEntity) -> None:
    """Auto-classify entity if its domain has epistemology configuration."""
    try:
        from backend.schema_registry import registry
        from backend.analyzers.epistemic_classifier import classify_entity

        domain = registry.get_domain(entity.domain or "default")
        if domain and domain.epistemology and domain.epistemology.paradigms:
            classify_entity(db, entity, domain.epistemology.paradigms, commit=False)
    except Exception as e:
        logger.debug("Epistemic classification skipped for entity %s: %s", entity.id, e)


def _after_enrichment_commit(
    db: Session,
    entity: models.RawEntity,
    *,
    previous_status: str | None,
) -> None:
    """Synchronize downstream analytics/RAG surfaces after enrichment writes commit."""
    domain_id = entity.domain or "default"
    logger.debug(
        "Post-enrichment sync for entity %s: %s -> %s",
        entity.id,
        previous_status,
        entity.enrichment_status,
    )

    try:
        from backend.routers.analytics import invalidate_analytics_for_domain

        invalidate_analytics_for_domain(domain_id)
    except Exception as exc:
        logger.warning("Failed to invalidate analytics cache for entity %s: %s", entity.id, exc)

    try:
        from backend.services.derived_status_service import invalidate_derived_status_cache

        invalidate_derived_status_cache(domain_id)
    except Exception as exc:
        logger.warning("Failed to invalidate derived-status cache for entity %s: %s", entity.id, exc)

    # V2 coauthorship materialization (flag-gated; no-op unless COAUTHOR_V2_WRITE).
    # Runs AFTER the enrichment commit, in its own unit of work, so a coauthor
    # failure can never roll back the already-committed enrichment.
    try:
        write_coauthor_artifacts(db, entity)
        db.commit()
    except Exception:
        logger.exception(
            "V2 coauthor write failed for entity %s; enrichment already committed", entity.id
        )
        db.rollback()

    if entity.enrichment_status != EnrichmentStatus.completed:
        return

    try:
        from backend.workflow_engine import fire_trigger

        fire_trigger("entity.enriched", entity, db)
    except Exception as exc:
        logger.warning("Failed to fire entity.enriched workflow for entity %s: %s", entity.id, exc)

    try:
        from backend.analytics import rag_engine
        from backend.routers.deps import _get_active_integration

        integration = _get_active_integration(db)
        if integration:
            result = rag_engine.index_entity(entity, integration)
            logger.debug("RAG incremental index result for entity %s: %s", entity.id, result)
    except Exception as exc:
        logger.warning("Failed to incrementally index enriched entity %s: %s", entity.id, exc)

    if entity.import_batch_id:
        try:
            from backend.services.graph_materializer import materialize_scientific_import_graph

            result = materialize_scientific_import_graph(db, entity.import_batch_id, org_id=entity.org_id)
            logger.debug("Graph materialization result after enrichment for entity %s: %s", entity.id, result)
        except Exception as exc:
            logger.warning("Failed to materialize graph after enrichment for entity %s: %s", entity.id, exc)

    try:
        from backend.services.semantic_keyword_signal_engine import materialize_keyword_signals

        result = materialize_keyword_signals(db, domain_id, org_id=entity.org_id, persist=True, limit=50)
        logger.debug("Semantic keyword signal result after enrichment for entity %s: %s", entity.id, {
            "corpus_size": result.get("corpus_size"),
            "total_candidates": result.get("total_candidates"),
        })
    except Exception as exc:
        logger.warning("Failed to materialize semantic keyword signals after enrichment for entity %s: %s", entity.id, exc)


def enrich_single_record(db: Session, entity: models.RawEntity) -> models.RawEntity:
    """
    Synchronously enriches a single record by title or DOI.
    Uses a cascade fallback strategy prioritizing Premium Data:
    Web of Science (BYOK) -> OpenAlex (Free API) -> Google Scholar (Scraping).
    """
    previous_status = entity.enrichment_status

    if not entity.primary_label:
        _set_enrichment_failed(
            entity,
            code="missing_title",
            evidence="El registro no tiene título o etiqueta principal para buscar en fuentes externas.",
        )
        db.commit()
        _after_enrichment_commit(db, entity, previous_status=previous_status)
        return entity

    query = entity.primary_label
    enriched_data = None
    source = "Unknown"
    provider_attempts: list[str] = []
    circuit_open_count = 0

    try:
        # Cascade through configured providers in order
        for provider_name in _ACTIVE_CASCADE:
            if enriched_data:
                break
            entry = _PROVIDER_MAP.get(provider_name)
            if not entry:
                continue
            adapter, cb = entry
            if adapter is None:
                continue
            if not getattr(adapter, "is_active", False):
                continue

            provider_attempts.append(provider_name)
            try:
                results = cb.call(adapter.search_by_title, query, limit=1)
                if results:
                    enriched_data = results[0]
                    source = provider_name
            except CircuitOpenError as e:
                circuit_open_count += 1
                logger.warning(str(e))

        if enriched_data:
            entity.enrichment_doi = enriched_data.doi
            entity.enrichment_citation_count = enriched_data.citation_count
            entity.enrichment_concepts = (
                ", ".join(enriched_data.concepts) if enriched_data.concepts else None
            )
            entity.enrichment_source = source
            entity.enrichment_status = EnrichmentStatus.completed
            _clear_enrichment_failure(entity)

            # Persist author names, ORCIDs, and concept IDs from enrichment source
            attrs = json.loads(entity.attributes_json) if entity.attributes_json else {}
            if enriched_data.authors:
                attrs["enrichment_authors"] = enriched_data.authors
                if enriched_data.author_orcids and any(enriched_data.author_orcids):
                    attrs["enrichment_author_orcids"] = enriched_data.author_orcids
            if enriched_data.concept_ids and any(enriched_data.concept_ids):
                attrs["enrichment_concept_ids"] = enriched_data.concept_ids
            # Persist extended fields from scientific connectors
            if enriched_data.affiliations:
                attrs["affiliation"] = "; ".join(enriched_data.affiliations)
                attrs["affiliations"] = enriched_data.affiliations
            canonical_affiliations_raw = getattr(enriched_data, "canonical_affiliations", None)
            canonical_affiliations = (
                _jsonable_model(canonical_affiliations_raw)
                if isinstance(canonical_affiliations_raw, list)
                else None
            )
            if canonical_affiliations:
                attrs["canonical_affiliations"] = canonical_affiliations
            author_affiliations_raw = getattr(enriched_data, "author_affiliations", None)
            author_affiliations = (
                _jsonable_model(author_affiliations_raw)
                if isinstance(author_affiliations_raw, list)
                else None
            )
            if author_affiliations:
                attrs["author_affiliations"] = author_affiliations
            if enriched_data.funding:
                attrs["funding"] = enriched_data.funding
            if enriched_data.tldr:
                attrs["tldr"] = enriched_data.tldr
            if enriched_data.mesh_terms:
                attrs["mesh_terms"] = enriched_data.mesh_terms
            if enriched_data.influential_citation_count is not None:
                attrs["influential_citation_count"] = enriched_data.influential_citation_count
            if enriched_data.references_count is not None:
                attrs["references_count"] = enriched_data.references_count
            if enriched_data.license:
                attrs["license"] = enriched_data.license
            if enriched_data.venue:
                attrs["venue"] = enriched_data.venue

            # Journal-level metrics (NIF base + APC) — non-essential add-on; a
            # journal sub-step failure (e.g. OpenAlex /sources timeout) must NEVER
            # abort persistence of the work's primary enrichment, so wrap it all.
            try:
                from backend.schemas_enrichment import JournalMetrics as _JournalMetrics
                journal = getattr(enriched_data, "journal", None)
                if isinstance(journal, _JournalMetrics) and journal.source_id:
                    full = adapter_openalex.fetch_source_metrics(journal.source_id) or journal
                    if not full.issn_l:
                        full.issn_l = journal.issn_l
                    doaj_apc = None
                    if full.is_in_doaj and full.issn_l:
                        try:
                            from backend.adapters.enrichment.doaj import DoajAdapter
                            doaj_apc = DoajAdapter().fetch_apc(full.issn_l)
                        except Exception:
                            doaj_apc = None
                    if full.issn_l:
                        from backend.services.journal_metrics_service import upsert_journal_metric
                        upsert_journal_metric(db, full, org_id=entity.org_id, doaj=doaj_apc)
                        attrs["issn_l"] = full.issn_l
                        entity.enrichment_issn_l = full.issn_l
            except Exception:
                logger.warning(
                    "Journal metric enrichment failed for entity %s; continuing with work enrichment",
                    entity.id, exc_info=True,
                )

            entity.attributes_json = json.dumps(attrs, ensure_ascii=False)

            # Extract and cache country from affiliation data
            _extract_and_cache_country(entity)

            # Materialize co-author relationships into entity_relationships
            # so the coauthorship analyzer has data to work with.
            _extract_and_persist_coauthor_edges(db, entity)

            # Epistemic classification (if domain has epistemology config)
            _try_epistemic_classify(db, entity)
        else:
            # Fallback: try active web scraper configs
            scraped = enrich_with_web_scrapers(db, entity)
            if not scraped:
                entity.enrichment_source = "None"
                # Classify failure reason
                active_providers = [
                    n for n in _ACTIVE_CASCADE
                    if _PROVIDER_MAP.get(n) and _PROVIDER_MAP[n][0] is not None
                    and getattr(_PROVIDER_MAP[n][0], "is_active", False)
                ]
                if active_providers and circuit_open_count >= len(active_providers):
                    _failure_reason = EnrichmentFailureReason.CIRCUIT_OPEN
                else:
                    _failure_reason = EnrichmentFailureReason.NO_MATCH
                _set_enrichment_failed(
                    entity,
                    code="no_provider_match",
                    evidence=f"No se encontraron coincidencias para '{query}' en las fuentes de enriquecimiento disponibles.",
                    provider_attempts=provider_attempts,
                    failure_reason=_failure_reason,
                )

    except (ValueError, KeyError, AttributeError) as e:
        # Domain / data errors — mark failed, log details
        logger.error(f"Data error enriching record ID {entity.id}: {e}")
        _set_enrichment_failed(
            entity,
            code="data_error",
            evidence=f"Error de datos durante el enriquecimiento: {e}",
            provider_attempts=provider_attempts,
            exception_type=type(e).__name__,
            failure_reason=EnrichmentFailureReason.API_ERROR,
        )
    except Exception as e:
        # Unexpected errors — mark failed but log at WARNING so they're visible
        logger.warning(f"Unexpected error enriching record ID {entity.id}: {type(e).__name__}: {e}")
        _set_enrichment_failed(
            entity,
            code="unexpected_error",
            evidence=f"Error inesperado durante el enriquecimiento: {type(e).__name__}: {e}",
            provider_attempts=provider_attempts,
            exception_type=type(e).__name__,
            failure_reason=EnrichmentFailureReason.ALL_SOURCES_FAILED,
        )

    db.commit()
    if previous_status != entity.enrichment_status or entity.enrichment_status == EnrichmentStatus.completed:
        _after_enrichment_commit(db, entity, previous_status=previous_status)
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


_COAUTHOR_RECOMPUTE_INTERVAL_S = 30
_COAUTHOR_RECOMPUTE_DEBOUNCE_S = 30


async def coauthor_recompute_loop():
    """Periodically materialize author_stats for scopes marked dirty by the
    write hook. Polls coauthor_dirty_scopes every 30s and recomputes each scope
    whose marker is older than the 30s debounce window (so a burst of writes to
    one scope collapses into a single recompute)."""
    from datetime import timedelta

    from backend.database import SessionLocal
    from backend.coauthorship.recompute import recompute_coauthor_stats

    while True:
        try:
            await asyncio.sleep(_COAUTHOR_RECOMPUTE_INTERVAL_S)
            db = SessionLocal()
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(
                    seconds=_COAUTHOR_RECOMPUTE_DEBOUNCE_S
                )
                scopes = (
                    db.query(models.CoauthorDirtyScope)
                    .filter(models.CoauthorDirtyScope.enqueued_at < cutoff)
                    .all()
                )
                for scope in scopes:
                    try:
                        recompute_coauthor_stats(
                            db, org_id=scope.org_id, domain_id=scope.domain_id
                        )
                    except Exception:
                        logger.exception(
                            "coauthor recompute failed for scope=(%s,%s)",
                            scope.org_id, scope.domain_id,
                        )
            finally:
                db.close()
        except Exception:
            logger.exception("coauthor recompute loop iteration failed")


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
                entity.enrichment_status = EnrichmentStatus.completed
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
    return_ids: bool = False,
) -> int | list[int]:
    """
    Marks a batch of 'none' or 'failed' entities as 'pending' so the background
    worker picks them up. Does NOT re-queue records already 'processing' or 'completed'.
    """
    entities = (
        scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
        .filter(models.RawEntity.enrichment_status.in_([EnrichmentStatus.none, EnrichmentStatus.failed]))
    )
    _domain_filt = resolve_domain_filter(parse_scope(domain_id), models.RawEntity)
    if _domain_filt is not None:
        entities = entities.filter(_domain_filt)
    entities = entities.order_by(models.RawEntity.id.asc()).offset(skip).limit(limit).all()
    queued_ids: list[int] = []
    for entity in entities:
        entity.enrichment_status = EnrichmentStatus.pending
        _clear_enrichment_failure(entity)
        queued_ids.append(entity.id)
    db.commit()
    return queued_ids if return_ids else len(queued_ids)
