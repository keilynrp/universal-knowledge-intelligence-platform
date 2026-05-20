"""
Domain registry and OLAP cube endpoints.
  GET/POST/DELETE /domains
  GET /domains/{domain_id}
  GET /olap/{domain_id}
  GET /cube/dimensions/{domain_id}
  POST /cube/query
  GET /cube/export/{domain_id}
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.olap import olap_engine
from backend.schema_registry import (
    AttributeSchema,
    DomainSchema,
    EpistemologyConfig,
    EvidenceLevel,
    Paradigm,
    ParadigmIndicators,
    registry,
)
from backend.tenant_access import resolve_request_org_id, scope_query_to_org

logger = logging.getLogger(__name__)

router = APIRouter(tags=["domains"])


def _domain_label(domain_id: str) -> str:
    return domain_id.replace("_", " ").replace("-", " ").title() or "Domain"


def _synthetic_ingested_domain(domain_id: str, entity_count: int, first_entity_id: int) -> DomainSchema:
    return DomainSchema(
        id=domain_id,
        name=_domain_label(domain_id),
        description=f"Ingested domain detected from {entity_count} active records.",
        primary_entity="Entity",
        icon="Database",
        entity_count=entity_count,
        first_entity_id=first_entity_id,
        attributes=[
            AttributeSchema(name="primary_label", type="string", label="Primary Label", required=True, is_core=True),
            AttributeSchema(name="domain", type="string", label="Domain", required=True, is_core=True),
            AttributeSchema(name="entity_type", type="string", label="Entity Type", required=False, is_core=True),
        ],
    )


@router.get("/domains", response_model=List[DomainSchema])
def get_domains(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Returns available domain schemas, enriched with ingestion-derived ordering metadata."""
    org_id = resolve_request_org_id(db, current_user)
    registry_domains = {domain.id: domain for domain in registry.get_all_domains()}
    ingested_rows = (
        scope_query_to_org(
            db.query(
                models.RawEntity.domain,
                func.count(models.RawEntity.id),
                func.min(models.RawEntity.id),
            ),
            models.RawEntity,
            org_id,
        )
        .filter(models.RawEntity.domain.isnot(None), models.RawEntity.domain != "")
        .group_by(models.RawEntity.domain)
        .order_by(func.min(models.RawEntity.id).asc())
        .all()
    )

    result: list[DomainSchema] = []
    seen: set[str] = set()
    for domain_id, count, first_entity_id in ingested_rows:
        if not domain_id:
            continue
        count_value = int(count or 0)
        first_id_value = int(first_entity_id or 0)
        schema = registry_domains.get(domain_id)
        if schema:
            enriched = schema.model_copy(update={"entity_count": count_value, "first_entity_id": first_id_value})
        else:
            enriched = _synthetic_ingested_domain(domain_id, count_value, first_id_value)
        result.append(enriched)
        seen.add(domain_id)

    for domain in registry.get_all_domains():
        if domain.id not in seen:
            result.append(domain.model_copy(update={"entity_count": 0, "first_entity_id": None}))

    return result


@router.post("/domains", response_model=DomainSchema, status_code=201)
def create_domain(
    schema: DomainSchema,
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Create a new custom domain schema. Persists as YAML in backend/domains/."""
    if registry.get_domain(schema.id):
        raise HTTPException(status_code=409, detail="A domain with this ID already exists")
    if not schema.attributes:
        raise HTTPException(status_code=422, detail="Domain must have at least one attribute")
    try:
        registry.save_domain(schema)
    except Exception:
        logger.exception("Failed to save domain schema '%s'", schema.id)
        raise HTTPException(status_code=500, detail="Failed to persist domain schema")
    return schema


@router.delete("/domains/{domain_id}")
def delete_domain(
    domain_id: str,
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Delete a custom domain schema. Built-in domains (default, science, healthcare) are protected."""
    if registry.is_builtin(domain_id):
        raise HTTPException(status_code=403, detail="Built-in domains cannot be deleted")
    if not registry.delete_domain(domain_id):
        raise HTTPException(status_code=404, detail="Domain schema not found")
    return {"deleted": domain_id}


@router.get("/domains/{domain_id}", response_model=DomainSchema)
def get_domain(domain_id: str, _: models.User = Depends(get_current_user)):
    domain = registry.get_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain schema not found")
    return domain


class _ParadigmIndicatorsPayload(BaseModel):
    terms: List[str] = []
    document_types: List[str] = []
    journals_affinity: List[str] = []


class _ParadigmPayload(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=128)
    description: str = ""
    indicators: _ParadigmIndicatorsPayload = _ParadigmIndicatorsPayload()


class _EpistemologyPatch(BaseModel):
    paradigms: List[_ParadigmPayload] = []
    evidence_hierarchy: List[dict] = []


@router.patch(
    "/domains/{domain_id}/epistemology",
    response_model=DomainSchema,
    dependencies=[Depends(require_role("super_admin", "admin"))],
)
def patch_domain_epistemology(domain_id: str, payload: _EpistemologyPatch):
    """
    Update (or clear) the epistemology configuration for a domain.
    Passing an empty `paradigms` list disables epistemic analysis for that domain.
    """
    domain = registry.get_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain schema not found")

    new_epistemology = EpistemologyConfig(
        paradigms=[
            Paradigm(
                id=p.id,
                label=p.label,
                description=p.description,
                indicators=ParadigmIndicators(
                    terms=p.indicators.terms,
                    document_types=p.indicators.document_types,
                    journals_affinity=p.indicators.journals_affinity,
                ),
            )
            for p in payload.paradigms
        ],
        evidence_hierarchy=[
            EvidenceLevel(**ev) for ev in payload.evidence_hierarchy if ev
        ],
    )

    updated = domain.model_copy(update={"epistemology": new_epistemology})
    try:
        registry.save_domain(updated)
    except Exception:
        logger.exception("Failed to save epistemology for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Failed to persist epistemology config")

    return updated


@router.get("/olap/{domain_id}")
def get_olap_cube(domain_id: str, _: models.User = Depends(get_current_user)):
    """
    Returns DuckDB OLAP distributions and multidimensional slice metrics for the given domain schema.
    """
    try:
        cube = olap_engine.generate_cube_metrics(domain_id)
        return cube
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("OLAP error for domain '%s'", domain_id)
        raise HTTPException(
            status_code=500, detail="OLAP processing error. Check server logs for details."
        )


# ── OLAP Cube Explorer ────────────────────────────────────────────────────────

class _CubeQueryPayload(BaseModel):
    domain_id: str = Field(min_length=1, max_length=64)
    group_by: List[str] = Field(min_length=1, max_length=2)
    filters: dict = {}


@router.get("/cube/dimensions/{domain_id}")
def cube_dimensions(domain_id: str, _: models.User = Depends(get_current_user)):
    """
    Returns the list of groupable dimensions for a domain with distinct-value counts.
    Used by the OLAP Cube Explorer dimension selector.
    """
    try:
        return olap_engine.get_dimensions(domain_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("cube_dimensions error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="OLAP error")


@router.post("/cube/query")
def cube_query(
    payload: _CubeQueryPayload,
    _: models.User = Depends(get_current_user),
):
    """
    GROUP BY query against the domain data cube.
    Accepts 1 or 2 dimensions and optional equality filters.
    """
    try:
        return olap_engine.query_cube(
            payload.domain_id, payload.group_by, payload.filters or None
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("cube_query error")
        raise HTTPException(status_code=500, detail="OLAP query error")


@router.get("/cube/export/{domain_id}")
def cube_export(
    domain_id: str,
    dimension: str = Query(min_length=1, max_length=64),
    _: models.User = Depends(get_current_user),
):
    """Export a single-dimension GROUP BY as an Excel (.xlsx) file."""
    try:
        xlsx_bytes = olap_engine.export_to_excel(domain_id, dimension)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception(
            "cube_export error for domain '%s', dimension '%s'", domain_id, dimension
        )
        raise HTTPException(status_code=500, detail="Export error")

    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="cube_{domain_id}_{dimension}.xlsx"'
            )
        },
    )
