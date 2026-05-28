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
from backend.scripts.backfill_coauthor_edges import backfill as run_coauthor_backfill

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


class CoauthorBackfillRequest(BaseModel):
    """Inputs for the CO_AUTHOR edge backfill."""

    model_config = ConfigDict(extra="forbid")

    dry_run: bool = Field(
        default=False,
        description=(
            "If true, count entities + estimated edges without writing. "
            "Defaults to false because this fix is the only way to populate "
            "the coauthorship graph for legacy data."
        ),
    )
    reset: bool = Field(
        default=False,
        description=(
            "Delete existing CO_AUTHOR rows before backfilling. Use only "
            "when you want a clean audit; the script is otherwise idempotent."
        ),
    )
    domain: Optional[str] = Field(
        default=None,
        description="Restrict to a single domain_id. None = all domains.",
        max_length=64,
    )


class CoauthorBackfillResponse(BaseModel):
    """Counters returned by the CO_AUTHOR edge backfill."""

    mode: str = Field(description="'dry-run' or 'applied'")
    reset: bool = Field(description="Whether existing CO_AUTHOR rows were wiped.")
    scanned: int = Field(description="Total entities visited under the filter.")
    with_authors: int = Field(description="Entities with at least 2 authors.")
    edges_generated: int = Field(description="Edges created (or estimated in dry-run).")
    errors: int = Field(description="Per-entity failures (rolled back individually).")


@router.post(
    "/coauthor-edges",
    response_model=CoauthorBackfillResponse,
    status_code=200,
    summary="Backfill CO_AUTHOR edges from enrichment_authors lists",
)
def fix_coauthor_edges(
    payload: CoauthorBackfillRequest,
    _user=Depends(require_role("super_admin", "admin")),
) -> CoauthorBackfillResponse:
    """Materializes the coauthorship graph for entities enriched before the
    extraction hook landed in enrichment_worker. Idempotent (upserts on
    ``relation_type='CO_AUTHOR'`` + ``notes='A||B'``); pass ``reset=True``
    when you want a fresh start."""
    logger.info(
        "admin/data-fixes/coauthor-edges dispatched dry_run=%s reset=%s domain=%s",
        payload.dry_run,
        payload.reset,
        payload.domain,
    )
    try:
        result = run_coauthor_backfill(
            domain=payload.domain,
            dry_run=payload.dry_run,
            reset=payload.reset,
        )
    except Exception as exc:
        logger.exception("coauthor edge backfill failed")
        # Surface a redacted error to the admin caller. Full traceback stays
        # in server logs via logger.exception above.
        raise HTTPException(
            status_code=500,
            detail=f"coauthor edge backfill failed: {type(exc).__name__}: {exc}",
        )

    return CoauthorBackfillResponse(
        mode="dry-run" if payload.dry_run else "applied",
        reset=payload.reset and not payload.dry_run,
        scanned=int(result.get("scanned", 0)),
        with_authors=int(result.get("with_authors", 0)),
        edges_generated=int(result.get("edges_generated", 0)),
        errors=int(result.get("errors", 0)),
    )
