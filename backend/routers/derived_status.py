"""
Derived Data Status endpoint.
  GET /derived-status/{domain_id}
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user
from backend.database import get_db
from backend.domain_scope import parse_scope
from backend.schema_registry import SchemaRegistry
from backend.services.derived_status_service import DerivedStatusService, status_cache

logger = logging.getLogger(__name__)
router = APIRouter(tags=["derived-status"])

_registry = SchemaRegistry()


def _cache_key(domain_id: str, user: models.User) -> str:
    org_id = getattr(user, "org_id", None) or 0
    return f"{domain_id}:{org_id}"


@router.get("/derived-status/{domain_id}", tags=["derived-status"])
def get_derived_status(
    domain_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Return the derived data status bundle for the given domain scope.

    - `domain_id` is any valid scope value: "all", "domain:science", etc.
    - The response is cached with a 30-second TTL per (domain_id, org_id).
    - Returns HTTP 404 if the domain does not exist in the registry (except "all").
    """
    scope = parse_scope(domain_id)

    # Domain existence check — "all" is always valid
    if scope != "all" and not scope.startswith("legacy"):
        bare_id = scope[len("domain:"):] if scope.startswith("domain:") else scope
        if _registry.get_domain(bare_id) is None:
            raise HTTPException(status_code=404, detail=f"Domain '{bare_id}' not found in registry")

    cache_key = _cache_key(domain_id, current_user)
    cached = status_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        bundle = DerivedStatusService.compute_all(scope, db)
    except Exception as exc:
        logger.exception("Failed to compute derived status for domain %s", domain_id)
        raise HTTPException(status_code=500, detail=f"Status computation failed: {exc}") from exc

    status_cache.set(cache_key, bundle)
    return bundle
