"""
API-based scientific import endpoints.
  POST /import/openalex  — bulk import from OpenAlex
  POST /import/pubmed    — bulk import from PubMed/NCBI
  GET  /import/status/{job_id} — poll async import job progress
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models
from backend.adapters.enrichment.openalex import OpenAlexAdapter
from backend.adapters.enrichment.pubmed import PubMedAdapter
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.schemas_enrichment import EnrichedRecord
from backend.tenant_access import persisted_org_id, resolve_request_org_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api-import"])

# ---------------------------------------------------------------------------
# In-memory job store
# ---------------------------------------------------------------------------

_jobs: Dict[str, dict] = {}


def _update_job(job_id: str, **kwargs: object) -> None:
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)


# ---------------------------------------------------------------------------
# Shared ingestion helper
# ---------------------------------------------------------------------------


def _ingest_records(
    db: Session,
    records: List[EnrichedRecord],
    domain: str,
    source: str,
    org_id: Optional[int] = None,
) -> int:
    """
    Create RawEntity rows from EnrichedRecord objects.
    Skips records whose DOI already exists within the same org scope.
    Returns number of new rows inserted.
    """
    existing_dois: set[str] = set()
    dois_in_batch = [r.doi for r in records if r.doi]
    if dois_in_batch:
        query = db.query(models.RawEntity.enrichment_doi).filter(
            models.RawEntity.enrichment_doi.in_(dois_in_batch)
        )
        if org_id is not None:
            query = query.filter(models.RawEntity.org_id == org_id)
        existing_dois = {row[0] for row in query.all() if row[0]}

    inserted = 0
    batch: list[models.RawEntity] = []
    for rec in records:
        if rec.doi and rec.doi in existing_dois:
            continue

        attrs = {}
        if rec.authors:
            attrs["authors"] = ", ".join(rec.authors)
        if rec.publication_year:
            attrs["year"] = rec.publication_year
        if rec.publisher:
            attrs["affiliation"] = rec.publisher

        entity = models.RawEntity(
            primary_label=rec.title,
            secondary_label=", ".join(rec.authors[:3]) if rec.authors else None,
            domain=domain,
            source=source,
            enrichment_doi=rec.doi,
            enrichment_citation_count=rec.citation_count or 0,
            enrichment_concepts=", ".join(rec.concepts) if rec.concepts else None,
            enrichment_source=rec.source_api,
            enrichment_status="pending",
            attributes_json=json.dumps(attrs, ensure_ascii=False) if attrs else "{}",
            org_id=persisted_org_id(org_id),
        )
        batch.append(entity)
        if rec.doi:
            existing_dois.add(rec.doi)

        if len(batch) >= 500:
            db.add_all(batch)
            db.commit()
            inserted += len(batch)
            batch = []

    if batch:
        db.add_all(batch)
        db.commit()
        inserted += len(batch)

    return inserted


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class OpenAlexImportRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=100, ge=1, le=1000)
    filters: Optional[Dict[str, str]] = None
    domain: str = Field(default="science")
    preview: bool = False


class PubMedImportRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=100, ge=1, le=500)
    domain: str = Field(default="science")
    preview: bool = False


class ImportJobResponse(BaseModel):
    job_id: str
    status: str
    record_count: int = 0


class ImportStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: float = 0.0
    records_inserted: int = 0
    total: int = 0


# ---------------------------------------------------------------------------
# Background task runners
# ---------------------------------------------------------------------------


def _run_openalex_import(
    job_id: str,
    query: str,
    filters: Optional[Dict[str, str]],
    limit: int,
    domain: str,
    org_id: Optional[int],
    db_factory,
) -> None:
    _update_job(job_id, status="running", progress=0.0)
    try:
        adapter = OpenAlexAdapter()
        records = adapter.search_bulk(query, filters=filters, limit=limit)
        _update_job(job_id, total=len(records), progress=0.5)

        db = next(db_factory)
        try:
            inserted = _ingest_records(db, records, domain, "openalex", org_id)
        finally:
            db.close()

        _update_job(job_id, status="done", progress=1.0, records_inserted=inserted)
    except Exception as exc:
        logger.error("OpenAlex import job %s failed: %s", job_id, exc)
        _update_job(job_id, status="failed", progress=0.0)


def _run_pubmed_import(
    job_id: str,
    query: str,
    limit: int,
    domain: str,
    org_id: Optional[int],
    db_factory,
) -> None:
    _update_job(job_id, status="running", progress=0.0)
    try:
        adapter = PubMedAdapter()
        records = adapter.search_bulk(query, limit=limit)
        _update_job(job_id, total=len(records), progress=0.5)

        db = next(db_factory)
        try:
            inserted = _ingest_records(db, records, domain, "pubmed", org_id)
        finally:
            db.close()

        _update_job(job_id, status="done", progress=1.0, records_inserted=inserted)
    except Exception as exc:
        logger.error("PubMed import job %s failed: %s", job_id, exc)
        _update_job(job_id, status="failed", progress=0.0)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/import/openalex", status_code=202, response_model=ImportJobResponse)
def import_openalex(
    payload: OpenAlexImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)

    if payload.preview:
        adapter = OpenAlexAdapter()
        records = adapter.search_bulk(
            payload.query, filters=payload.filters, limit=min(payload.limit, 10)
        )
        inserted = _ingest_records(db, records, payload.domain, "openalex", org_id)
        return ImportJobResponse(job_id="preview", status="done", record_count=inserted)

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "progress": 0.0,
        "records_inserted": 0,
        "total": payload.limit,
    }

    from backend.database import get_db as db_factory
    background_tasks.add_task(
        _run_openalex_import,
        job_id,
        payload.query,
        payload.filters,
        payload.limit,
        payload.domain,
        org_id,
        db_factory(),
    )

    return ImportJobResponse(job_id=job_id, status="queued", record_count=0)


@router.post("/import/pubmed", status_code=202, response_model=ImportJobResponse)
def import_pubmed(
    payload: PubMedImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)

    if payload.preview:
        adapter = PubMedAdapter()
        records = adapter.search_bulk(payload.query, limit=min(payload.limit, 10))
        inserted = _ingest_records(db, records, payload.domain, "pubmed", org_id)
        return ImportJobResponse(job_id="preview", status="done", record_count=inserted)

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": "queued",
        "progress": 0.0,
        "records_inserted": 0,
        "total": payload.limit,
    }

    from backend.database import get_db as db_factory
    background_tasks.add_task(
        _run_pubmed_import,
        job_id,
        payload.query,
        payload.limit,
        payload.domain,
        org_id,
        db_factory(),
    )

    return ImportJobResponse(job_id=job_id, status="queued", record_count=0)


@router.get("/import/status/{job_id}", response_model=ImportStatusResponse)
def import_status(
    job_id: str,
    _: models.User = Depends(get_current_user),
):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Import job not found")

    job = _jobs[job_id]
    return ImportStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        progress=job.get("progress", 0.0),
        records_inserted=job.get("records_inserted", 0),
        total=job.get("total", 0),
    )
