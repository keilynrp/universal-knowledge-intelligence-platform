"""
Scientific literature import endpoints.
  GET  /scientific/sources              — list available sources
  POST /scientific/search               — search without importing
  POST /scientific/dois/preview         — batch DOI resolver without importing
  POST /scientific/import               — search + save as RawEntity (201)
  POST /scientific/dois                 — batch DOI resolver + save (201)
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fastapi import Request

from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend import models
from backend.adapters.scientific import get_scientific_adapter, list_sources
from backend.adapters.scientific.base import ScientificRecord
from backend.parsers.science_mapper import science_record_to_entity
from backend.services.engine_delegation import _get_engine_client, try_engine_connectors
from backend.tenant_access import resolve_request_org_id, persisted_org_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scientific", tags=["scientific-import"])


_VALID_SOURCES = {s["id"] for s in list_sources()}


class AdapterConfig(BaseModel):
    """Typed config for scientific adapters — only known keys allowed."""
    email: Optional[str] = None
    api_key_name: Optional[str] = None


class SearchRequest(BaseModel):
    source: str
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=20, ge=1, le=100)
    config: AdapterConfig = Field(default_factory=AdapterConfig)
    use_engine: bool = Field(default=False, description="Opt-in to Rust engine delegation")


class DoiBatchRequest(BaseModel):
    dois: list[str] = Field(min_length=1, max_length=200)
    source: str = Field(default="crossref")
    config: AdapterConfig = Field(default_factory=AdapterConfig)


def _record_to_dict(r: ScientificRecord) -> dict:
    return {
        "title": r.title,
        "doi": r.doi,
        "authors": r.authors,
        "year": r.year,
        "abstract": r.abstract,
        "journal": r.journal,
        "publisher": r.publisher,
        "concepts": r.concepts,
        "citation_count": r.citation_count,
        "is_open_access": r.is_open_access,
        "url": r.url,
        "source_api": r.source_api,
        "external_id": r.external_id,
    }


def _save_records(records: list, db: Session, org_id: Optional[int]) -> dict:
    """Convert ScientificRecords → RawEntity rows. Skips duplicates by DOI."""
    imported = 0
    skipped = 0
    stored_org = persisted_org_id(org_id)
    for rec in records:
        if rec.doi:
            exists_query = db.query(models.RawEntity).filter(models.RawEntity.enrichment_doi == rec.doi)
            if stored_org is None:
                exists_query = exists_query.filter(models.RawEntity.org_id.is_(None))
            else:
                exists_query = exists_query.filter(models.RawEntity.org_id == stored_org)
            exists = exists_query.first()
            if exists:
                skipped += 1
                continue
        entity_kwargs = science_record_to_entity({
            "title": rec.title,
            "authors": "; ".join(rec.authors) if rec.authors else None,
            "doi": rec.doi,
            "keywords": ", ".join(rec.concepts) if rec.concepts else None,
            "year": str(rec.year) if rec.year else None,
            "abstract": rec.abstract,
            "journal": rec.journal,
            "publisher": rec.publisher,
        })
        entity_kwargs["enrichment_doi"] = rec.doi
        entity_kwargs["enrichment_citation_count"] = rec.citation_count or 0
        entity_kwargs["enrichment_source"] = rec.source_api
        entity_kwargs["source"] = "scientific_import"
        if stored_org is not None:
            entity_kwargs["org_id"] = stored_org
        db.add(models.RawEntity(**entity_kwargs))
        imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped}


def _fetch_doi_records(body: DoiBatchRequest) -> list[ScientificRecord]:
    try:
        adapter = get_scientific_adapter(body.source, body.config.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return adapter.fetch_batch_dois(body.dois)
    except Exception as e:
        logger.exception("DOI batch failed for source=%s", body.source)
        raise HTTPException(status_code=502, detail=f"Source unavailable: {e}")


def _save_engine_publications(pubs: list[dict], db: Session, org_id: Optional[int]) -> dict:
    """Save publications returned by the engine connector to the database."""
    imported = 0
    skipped = 0
    stored_org = persisted_org_id(org_id)
    for pub in pubs:
        doi = pub.get("doi")
        if doi:
            exists_query = db.query(models.RawEntity).filter(models.RawEntity.enrichment_doi == doi)
            if stored_org is None:
                exists_query = exists_query.filter(models.RawEntity.org_id.is_(None))
            else:
                exists_query = exists_query.filter(models.RawEntity.org_id == stored_org)
            if exists_query.first():
                skipped += 1
                continue
        authors = pub.get("authors", [])
        entity_kwargs = science_record_to_entity({
            "title": pub.get("title"),
            "authors": "; ".join(authors) if authors else None,
            "doi": doi,
            "year": str(pub["year"]) if pub.get("year") else None,
            "abstract": pub.get("abstract"),
            "journal": pub.get("journal"),
        })
        entity_kwargs["enrichment_doi"] = doi
        entity_kwargs["enrichment_citation_count"] = pub.get("citations", 0)
        entity_kwargs["enrichment_source"] = pub.get("source", "engine")
        entity_kwargs["source"] = "scientific_import"
        if stored_org is not None:
            entity_kwargs["org_id"] = stored_org
        db.add(models.RawEntity(**entity_kwargs))
        imported += 1
    db.commit()
    return {"imported": imported, "skipped": skipped}


@router.get("/sources")
def get_sources(_=Depends(get_current_user)):
    return list_sources()


@router.post("/search")
async def search_scientific(request: Request, body: SearchRequest, _=Depends(get_current_user)):
    if body.source not in _VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source '{body.source}'. Available: {sorted(_VALID_SOURCES)}")
    # Try engine delegation if opted-in
    if body.use_engine:
        engine_client = _get_engine_client(request)
        engine_pubs = await try_engine_connectors(
            engine_client, body.source, "search", [body.query], limit=body.max_results,
        )
        if engine_pubs is not None:
            return engine_pubs
    try:
        adapter = get_scientific_adapter(body.source, body.config.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        records = adapter.search(body.query, max_results=body.max_results)
    except Exception as e:
        logger.exception("Scientific search failed for source=%s", body.source)
        raise HTTPException(status_code=502, detail=f"Source unavailable: {e}")
    return [_record_to_dict(r) for r in records]


@router.post("/dois/preview")
def preview_dois(body: DoiBatchRequest, _=Depends(get_current_user)):
    return [_record_to_dict(r) for r in _fetch_doi_records(body)]


@router.post("/import", status_code=201)
async def import_scientific(
    request: Request,
    body: SearchRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("super_admin", "admin", "editor")),
):
    if body.source not in _VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source '{body.source}'. Available: {sorted(_VALID_SOURCES)}")
    org_id = resolve_request_org_id(db, current_user)
    # Try engine delegation if opted-in (bypasses Python rate limiter)
    if body.use_engine:
        engine_client = _get_engine_client(request)
        engine_pubs = await try_engine_connectors(
            engine_client, body.source, "search", [body.query], limit=body.max_results,
        )
        if engine_pubs is not None:
            return _save_engine_publications(engine_pubs, db, org_id)
    try:
        adapter = get_scientific_adapter(body.source, body.config.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        records = adapter.search(body.query, max_results=body.max_results)
    except Exception as e:
        logger.exception("Scientific import failed for source=%s", body.source)
        raise HTTPException(status_code=502, detail=f"Source unavailable: {e}")
    return _save_records(records, db, org_id)


@router.post("/dois", status_code=201)
def import_dois(
    body: DoiBatchRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("super_admin", "admin", "editor")),
):
    records = _fetch_doi_records(body)
    org_id = resolve_request_org_id(db, current_user)
    return _save_records(records, db, org_id)
