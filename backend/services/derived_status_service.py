"""
Derived Data Status Service
Computes the current build/freshness status of the six tracked derived resources
for a given domain scope. Read-only — does not modify data or trigger pipelines.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend import models
from backend.domain_scope import parse_scope, resolve_domain_filter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

TRACKED_RESOURCES: tuple[str, ...] = (
    "enrichment",
    "graph",
    "semantic_keyword_signals",
    "rag_index",
    "executive_dashboard_snapshot",
    "report_readiness",
)

STATUS_MISSING     = "missing"
STATUS_PENDING     = "pending"
STATUS_PROCESSING  = "processing"
STATUS_READY       = "ready"
STATUS_STALE       = "stale"
STATUS_FAILED      = "failed"
STATUS_UNKNOWN     = "unknown"

CANONICAL_STATUSES = frozenset({
    STATUS_MISSING, STATUS_PENDING, STATUS_PROCESSING,
    STATUS_READY, STATUS_STALE, STATUS_FAILED, STATUS_UNKNOWN,
})

# Rebuild endpoints per resource (None = no direct rebuild available)
_REBUILD_ENDPOINTS: dict[str, Optional[str]] = {
    "enrichment": "/enrich/bulk",
    "graph": None,
    "semantic_keyword_signals": None,
    "rag_index": "/rag/index",
    "executive_dashboard_snapshot": "/analytics/cache/invalidate",
    "report_readiness": None,
}

# ---------------------------------------------------------------------------
# TTL cache for derived-status responses
# ---------------------------------------------------------------------------

class _StatusCache:
    """Thread-safe in-memory TTL cache for derived-status bundles."""

    def __init__(self, ttl_seconds: int = 30):
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._store:
                ts, val = self._store[key]
                if time.time() - ts < self._ttl:
                    return val
                del self._store[key]
        return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)

    def invalidate(self, domain_id: str) -> None:
        """Evict all cache entries whose key starts with the domain prefix."""
        prefix = f"{domain_id}:"
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
        if keys:
            logger.debug("derived-status cache invalidated for domain %s (%d entries)", domain_id, len(keys))


status_cache = _StatusCache(ttl_seconds=30)


def invalidate_derived_status_cache(domain_id: str) -> None:
    """
    Invalidate the derived-status cache for a domain.
    Call this from enrichment workers or materializers after a build completes.
    """
    status_cache.invalidate(domain_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_count(scope: str, db: Session) -> int:
    """Count total (non-derived) entities in scope."""
    filt = resolve_domain_filter(scope, models.RawEntity)
    q = db.query(models.RawEntity).filter(models.RawEntity.source != "graph_materializer")
    if filt is not None:
        q = q.filter(filt)
    return q.count()


def _resource_entry(
    status: str,
    source_count: int,
    derived_count: int,
    last_error: Optional[str] = None,
    updated_at: Optional[str] = None,
    resource_key: str = "",
) -> dict[str, Any]:
    rebuild_ep = _REBUILD_ENDPOINTS.get(resource_key)
    can_rebuild = status in (STATUS_STALE, STATUS_MISSING, STATUS_FAILED, STATUS_UNKNOWN) and rebuild_ep is not None
    return {
        "status": status,
        "updated_at": updated_at or _now_iso(),
        "source_count": source_count,
        "derived_count": derived_count,
        "last_error": last_error,
        "can_rebuild": can_rebuild,
        "rebuild_endpoint": rebuild_ep,
    }


# ---------------------------------------------------------------------------
# Per-resource computation
# ---------------------------------------------------------------------------

def _compute_enrichment(scope: str, db: Session) -> dict[str, Any]:
    filt = resolve_domain_filter(scope, models.RawEntity)
    base_q = db.query(models.RawEntity).filter(models.RawEntity.source != "graph_materializer")
    if filt is not None:
        base_q = base_q.filter(filt)

    source_count = base_q.count()
    if source_count == 0:
        return _resource_entry(STATUS_MISSING, 0, 0, resource_key="enrichment")

    derived_count = (
        base_q
        .filter(models.RawEntity.enrichment_status.in_(["completed", "done", "enriched"]))
        .count()
    )

    if derived_count == source_count:
        status = STATUS_READY
    elif derived_count > 0:
        status = STATUS_STALE
    else:
        status = STATUS_MISSING

    return _resource_entry(status, source_count, derived_count, resource_key="enrichment")


def _compute_graph(scope: str, db: Session) -> dict[str, Any]:
    filt = resolve_domain_filter(scope, models.RawEntity)
    base_q = db.query(models.RawEntity).filter(models.RawEntity.source != "graph_materializer")
    if filt is not None:
        base_q = base_q.filter(filt)

    source_count = base_q.count()
    if source_count == 0:
        return _resource_entry(STATUS_MISSING, 0, 0, resource_key="graph")

    # Count distinct entity IDs that appear as source_id in at least one relationship
    rel_q = db.query(models.EntityRelationship.source_id).distinct()
    if filt is not None:
        # Scope relationships to this domain by joining source entity
        rel_q = (
            db.query(models.EntityRelationship.source_id)
            .join(models.RawEntity, models.RawEntity.id == models.EntityRelationship.source_id)
            .distinct()
        )
        rel_q = rel_q.filter(filt)

    derived_count = rel_q.count()

    if derived_count == 0:
        status = STATUS_MISSING
    elif derived_count >= source_count:
        status = STATUS_READY
    else:
        status = STATUS_STALE

    return _resource_entry(status, source_count, derived_count, resource_key="graph")


def _compute_semantic_keyword_signals(scope: str, db: Session) -> dict[str, Any]:
    filt = resolve_domain_filter(scope, models.RawEntity)
    base_q = db.query(models.RawEntity).filter(models.RawEntity.source != "graph_materializer")
    if filt is not None:
        base_q = base_q.filter(filt)

    source_count = base_q.count()
    if source_count == 0:
        return _resource_entry(STATUS_MISSING, 0, 0, resource_key="semantic_keyword_signals")

    derived_count = (
        base_q
        .filter(models.RawEntity.enrichment_concepts.isnot(None))
        .filter(models.RawEntity.enrichment_concepts != "")
        .count()
    )

    if derived_count == 0:
        status = STATUS_MISSING
    elif derived_count >= source_count:
        status = STATUS_READY
    else:
        status = STATUS_STALE

    return _resource_entry(status, source_count, derived_count, resource_key="semantic_keyword_signals")


def _compute_rag_index(scope: str, db: Session) -> dict[str, Any]:
    filt = resolve_domain_filter(scope, models.RawEntity)
    base_q = db.query(models.RawEntity).filter(models.RawEntity.source != "graph_materializer")
    if filt is not None:
        base_q = base_q.filter(filt)
    source_count = base_q.count()

    # Short-circuit: no entities → missing, no need to probe ChromaDB
    if source_count == 0:
        return _resource_entry(STATUS_MISSING, 0, 0, resource_key="rag_index")

    try:
        from backend.analytics.vector_store import VectorStoreService
        derived_count = VectorStoreService.get_stats()["total_indexed"]
    except Exception as exc:
        error_msg = f"ChromaDB unreachable: {exc}"
        logger.warning("RAG index status check failed: %s", exc)
        return _resource_entry(
            STATUS_UNKNOWN, source_count, 0,
            last_error=error_msg, resource_key="rag_index",
        )

    if derived_count == 0:
        status = STATUS_MISSING
    elif derived_count >= source_count:
        status = STATUS_READY
    else:
        status = STATUS_STALE

    return _resource_entry(status, source_count, derived_count, resource_key="rag_index")


def _compute_executive_dashboard_snapshot(scope: str, db: Session) -> dict[str, Any]:
    """
    Checks whether the dashboard analytics cache has a warm entry for the domain.
    Falls back to entity-existence check if cache inspection is unavailable.
    """
    filt = resolve_domain_filter(scope, models.RawEntity)
    base_q = db.query(models.RawEntity).filter(models.RawEntity.source != "graph_materializer")
    if filt is not None:
        base_q = base_q.filter(filt)
    source_count = base_q.count()

    if source_count == 0:
        return _resource_entry(STATUS_MISSING, 0, 0, resource_key="executive_dashboard_snapshot")

    # Try to inspect the analytics dashboard cache
    try:
        from backend.routers.analytics import _dashboard_cache
        # The cache key pattern is "dashboard_{domain_id}_*"
        # Extract the bare domain portion for prefix matching
        if scope == "all":
            domain_key_prefix = "dashboard_all"
        elif scope.startswith("domain:"):
            bare = scope[len("domain:"):]
            domain_key_prefix = f"dashboard_{bare}"
        else:
            domain_key_prefix = f"dashboard_{scope}"

        with _dashboard_cache._lock:
            now = time.time()
            is_warm = any(
                k.startswith(domain_key_prefix) and (now - ts) < _dashboard_cache._ttl
                for k, (ts, _) in _dashboard_cache._store.items()
            )

        status = STATUS_READY if is_warm else STATUS_STALE
        derived_count = source_count if is_warm else 0
    except Exception:
        # Cache not inspectable — report ready since dashboard is live-computed
        status = STATUS_READY
        derived_count = source_count

    return _resource_entry(status, source_count, derived_count, resource_key="executive_dashboard_snapshot")


def _compute_report_readiness(scope: str, db: Session) -> dict[str, Any]:
    """
    Checks report readiness. Since reports are generated on-demand (not persisted),
    any domain with enriched entities is considered report-ready.
    """
    filt = resolve_domain_filter(scope, models.RawEntity)
    base_q = db.query(models.RawEntity).filter(models.RawEntity.source != "graph_materializer")
    if filt is not None:
        base_q = base_q.filter(filt)
    source_count = base_q.count()

    if source_count == 0:
        return _resource_entry(STATUS_MISSING, 0, 0, resource_key="report_readiness")

    # Count enriched entities as a proxy for report-readiness
    derived_count = (
        base_q
        .filter(models.RawEntity.enrichment_status.in_(["completed", "done", "enriched"]))
        .count()
    )

    if derived_count == 0:
        status = STATUS_MISSING
    elif derived_count >= source_count * 0.5:
        # At least half enriched → reports would be meaningful
        status = STATUS_READY
    else:
        status = STATUS_STALE

    return _resource_entry(status, source_count, derived_count, resource_key="report_readiness")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_COMPUTE_FNS = {
    "enrichment":                   _compute_enrichment,
    "graph":                        _compute_graph,
    "semantic_keyword_signals":     _compute_semantic_keyword_signals,
    "rag_index":                    _compute_rag_index,
    "executive_dashboard_snapshot": _compute_executive_dashboard_snapshot,
    "report_readiness":             _compute_report_readiness,
}


class DerivedStatusService:
    """Read-only service that computes derived resource status from existing DB state."""

    @staticmethod
    def compute(resource: str, scope: str, db: Session) -> dict[str, Any]:
        """
        Compute the status of a single resource for the given domain scope.
        scope should be a parsed DomainScope string (e.g. "all", "domain:science").
        """
        if resource not in _COMPUTE_FNS:
            raise ValueError(f"Unknown resource: {resource!r}. Must be one of {list(TRACKED_RESOURCES)}")
        parsed = parse_scope(scope)
        return _COMPUTE_FNS[resource](parsed, db)

    @staticmethod
    def compute_all(scope: str, db: Session) -> dict[str, Any]:
        """
        Compute the status of all six tracked resources and return the full bundle.
        """
        parsed = parse_scope(scope)
        computed_at = _now_iso()
        resources: dict[str, Any] = {}
        for resource in TRACKED_RESOURCES:
            try:
                resources[resource] = _COMPUTE_FNS[resource](parsed, db)
            except Exception as exc:
                logger.exception("Error computing %s status for scope %s", resource, parsed)
                resources[resource] = _resource_entry(
                    STATUS_UNKNOWN, 0, 0,
                    last_error=str(exc),
                    resource_key=resource,
                )
        return {
            "domain_id": scope,
            "computed_at": computed_at,
            "resources": resources,
        }
