"""Admin data-fix endpoints.

  POST /admin/data-fixes/legacy-affiliations
      Remove journal/publisher values that the cbe3255 → 19e97ff bug wrote
      into attributes_json.affiliation for entities imported via OpenAlex /
      PubMed between 2026-05-13 and 2026-05-20. Wraps
      ``backend.scripts.fix_legacy_affiliations.run``.

  POST /admin/data-fixes/canonical-identity
      Populate canonical_id and/or entity_type for existing entities from
      enrichment_doi, attributes_json, or normalized_json. Wraps
      ``backend.scripts.backfill_canonical_id_entity_type.run``.

All routes here require the ``super_admin`` role. They are intentionally
disjoint from feature routers so data-repair operations stay auditable
and easy to disable.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from backend.auth import require_role
from backend.scripts.fix_legacy_affiliations import run as run_legacy_affiliation_fix
from backend.scripts.backfill_canonical_id_entity_type import run as run_canonical_identity_fix

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/data-fixes", tags=["admin", "data-fixes"])


class LegacyAffiliationFixRequest(BaseModel):
    """Inputs for the legacy-affiliation backfill.

    Defaults bias toward safety: ``dry_run=True`` and no re-enrichment.
    Callers must explicitly opt out of dry-run to mutate the database.
    """

    model_config = ConfigDict(extra="forbid")

    dry_run: bool = Field(
        default=True,
        description=(
            "If true, scan and report counters without committing changes. "
            "Defaults to true so unprivileged misuse cannot mutate data."
        ),
    )
    requeue_enrichment: bool = Field(
        default=False,
        description=(
            "If true, mark fixed entities with enrichment_status='pending' "
            "so the worker repopulates affiliation from canonical institutions."
        ),
    )
    org_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Restrict to a single org id. Omit to scan all orgs.",
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1_000_000,
        description="Cap the number of rows scanned. Omit for no cap.",
    )


class LegacyAffiliationFixResponse(BaseModel):
    """Counter shape returned by the backfill script."""

    mode: str = Field(description="'dry-run' or 'applied'")
    requeue_enrichment: bool
    scanned: int = Field(description="Total entities visited under the filter.")
    matched: int = Field(description="Entities whose enrichment_source matched the affected providers.")
    fixed: int = Field(description="Entities whose attributes_json.affiliation was cleared.")


class CanonicalIdentityFixRequest(BaseModel):
    """Inputs for canonical_id/entity_type backfill.

    Defaults bias toward safety: ``dry_run=True`` and both fields included.
    The operation is idempotent and never overwrites existing non-empty values.
    """

    model_config = ConfigDict(extra="forbid")

    dry_run: bool = Field(
        default=True,
        description="If true, scan and report counters without committing changes.",
    )
    only: Optional[str] = Field(
        default=None,
        pattern="^(canonical_id|entity_type)$",
        description="Limit the backfill to one field. Omit to repair both.",
    )
    org_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Restrict to a single org id. Omit to scan all orgs.",
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1_000_000,
        description="Cap the number of rows scanned. Omit for no cap.",
    )


class CanonicalIdentityFixResponse(BaseModel):
    """Counter shape returned by the canonical identity backfill script."""

    mode: str = Field(description="'dry-run' or 'applied'")
    scanned: int = Field(description="Total entities visited under the filter.")
    fixed_canonical_id: int = Field(description="Entities whose canonical_id was populated.")
    fixed_entity_type: int = Field(description="Entities whose entity_type was populated.")
    skipped_duplicates: int = Field(description="Rows skipped to avoid canonical uniqueness collisions.")


@router.post(
    "/legacy-affiliations",
    response_model=LegacyAffiliationFixResponse,
    status_code=200,
    summary="Backfill legacy affiliation residue (cbe3255 bug)",
)
def fix_legacy_affiliations(
    payload: LegacyAffiliationFixRequest,
    _user=Depends(require_role("super_admin")),
) -> LegacyAffiliationFixResponse:
    """Idempotent. Safe to call repeatedly. Always log the request shape so
    the audit trail captures who initiated which run."""
    logger.info(
        "admin/data-fixes/legacy-affiliations dispatched dry_run=%s "
        "requeue_enrichment=%s org_id=%s limit=%s",
        payload.dry_run,
        payload.requeue_enrichment,
        payload.org_id,
        payload.limit,
    )
    try:
        result = run_legacy_affiliation_fix(
            dry_run=payload.dry_run,
            requeue_enrichment=payload.requeue_enrichment,
            org_id=payload.org_id,
            limit=payload.limit,
        )
    except Exception:
        logger.exception("legacy affiliation fix failed")
        raise HTTPException(status_code=500, detail="legacy affiliation fix failed")

    return LegacyAffiliationFixResponse(
        mode="dry-run" if payload.dry_run else "applied",
        requeue_enrichment=payload.requeue_enrichment and not payload.dry_run,
        scanned=int(result.get("scanned", 0)),
        matched=int(result.get("matched", 0)),
        fixed=int(result.get("fixed", 0)),
    )


@router.post(
    "/canonical-identity",
    response_model=CanonicalIdentityFixResponse,
    status_code=200,
    summary="Backfill canonical_id and entity_type for existing entities",
)
def fix_canonical_identity(
    payload: CanonicalIdentityFixRequest,
    _user=Depends(require_role("super_admin")),
) -> CanonicalIdentityFixResponse:
    """Idempotent. Safe to call repeatedly. Intended for production data
    repair after imports that stored identifiers in enrichment/attribute
    fields but left the canonical columns empty."""
    logger.info(
        "admin/data-fixes/canonical-identity dispatched dry_run=%s "
        "only=%s org_id=%s limit=%s",
        payload.dry_run,
        payload.only,
        payload.org_id,
        payload.limit,
    )
    try:
        result = run_canonical_identity_fix(
            dry_run=payload.dry_run,
            only=payload.only,
            org_id=payload.org_id,
            limit=payload.limit,
        )
    except Exception:
        logger.exception("canonical identity fix failed")
        raise HTTPException(status_code=500, detail="canonical identity fix failed")

    return CanonicalIdentityFixResponse(
        mode="dry-run" if payload.dry_run else "applied",
        scanned=int(result.get("scanned", 0)),
        fixed_canonical_id=int(result.get("fixed_canonical_id", 0)),
        fixed_entity_type=int(result.get("fixed_entity_type", 0)),
        skipped_duplicates=int(result.get("skipped_duplicates", 0)),
    )
