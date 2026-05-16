"""
External Attention import endpoints.
  POST /external-attention/import         (bulk: CSV or JSON body)
  POST /entities/{id}/external-attention/import  (single entity JSON body)
"""
import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend import models
from backend.analyzers.external_attention import VALID_SOURCE_TYPES
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.routers.deps import _audit
from backend.tenant_access import resolve_request_org_id, scope_query_to_org

logger = logging.getLogger(__name__)

router = APIRouter(tags=["external-attention"])

_MAX_OBSERVATIONS_PER_REQUEST = 5_000
_MAX_SNIPPET_LENGTH = 1_000
_MAX_TITLE_LENGTH = 500
_MAX_URL_LENGTH = 2_000


class ObservationInput(BaseModel):
    entity_id: int = Field(..., ge=1)
    source_type: str = Field(..., min_length=1, max_length=50)
    mention_count: int = Field(default=1, ge=1)
    last_seen_at: Optional[str] = None
    title: Optional[str] = Field(default=None, max_length=_MAX_TITLE_LENGTH)
    url: Optional[str] = Field(default=None, max_length=_MAX_URL_LENGTH)
    snippet: Optional[str] = Field(default=None, max_length=_MAX_SNIPPET_LENGTH)

    @field_validator("source_type")
    @classmethod
    def normalize_source_type(cls, v: str) -> str:
        return v.strip().lower().replace("-", "_")


class SingleEntityObservationInput(BaseModel):
    source_type: str = Field(..., min_length=1, max_length=50)
    mention_count: int = Field(default=1, ge=1)
    last_seen_at: Optional[str] = None
    title: Optional[str] = Field(default=None, max_length=_MAX_TITLE_LENGTH)
    url: Optional[str] = Field(default=None, max_length=_MAX_URL_LENGTH)
    snippet: Optional[str] = Field(default=None, max_length=_MAX_SNIPPET_LENGTH)

    @field_validator("source_type")
    @classmethod
    def normalize_source_type(cls, v: str) -> str:
        return v.strip().lower().replace("-", "_")


class BulkImportResponse(BaseModel):
    imported: int
    skipped: int
    entities_updated: int
    warnings: List[str] = []


class SingleImportResponse(BaseModel):
    imported: int
    total_observations: int


# ── Bulk import (JSON body) ──────────────────────────────────────────────────

@router.post(
    "/external-attention/import",
    response_model=BulkImportResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "admin", "editor"))],
)
def bulk_import_observations_json(
    observations: List[ObservationInput],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Import external attention observations for multiple entities (JSON body)."""
    if len(observations) > _MAX_OBSERVATIONS_PER_REQUEST:
        raise HTTPException(
            status_code=422,
            detail=f"Maximum {_MAX_OBSERVATIONS_PER_REQUEST} observations per request.",
        )

    org_id = resolve_request_org_id(db, current_user)
    result = _merge_observations(db, observations, org_id)
    db.commit()

    _audit(db, current_user, "external_attention.bulk_import", {
        "imported": result["imported"],
        "entities_updated": result["entities_updated"],
    })

    return BulkImportResponse(**result)


# ── Bulk import (CSV file) ───────────────────────────────────────────────────

@router.post(
    "/external-attention/import/csv",
    response_model=BulkImportResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "admin", "editor"))],
)
async def bulk_import_observations_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Import external attention observations from a CSV file.

    Expected columns: entity_id, source_type, mention_count, last_seen_at, title, url, snippet
    Only entity_id and source_type are required.
    """
    if file.content_type and file.content_type not in (
        "text/csv",
        "application/csv",
        "text/plain",
        "application/octet-stream",
    ):
        raise HTTPException(status_code=422, detail="File must be CSV.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(status_code=413, detail="CSV file exceeds 10 MB limit.")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File must be UTF-8 encoded.")

    reader = csv.DictReader(io.StringIO(text))
    observations: list[ObservationInput] = []
    warnings: list[str] = []

    for row_num, row in enumerate(reader, start=2):  # header is row 1
        if row_num - 1 > _MAX_OBSERVATIONS_PER_REQUEST:
            warnings.append(f"Truncated at {_MAX_OBSERVATIONS_PER_REQUEST} rows.")
            break

        entity_id_raw = row.get("entity_id", "").strip()
        source_type_raw = row.get("source_type", "").strip()

        if not entity_id_raw or not source_type_raw:
            warnings.append(f"Row {row_num}: missing entity_id or source_type, skipped.")
            continue

        try:
            entity_id = int(entity_id_raw)
        except ValueError:
            warnings.append(f"Row {row_num}: invalid entity_id '{entity_id_raw}', skipped.")
            continue

        mention_count_raw = row.get("mention_count", "1").strip()
        try:
            mention_count = max(1, int(mention_count_raw)) if mention_count_raw else 1
        except ValueError:
            mention_count = 1

        observations.append(ObservationInput(
            entity_id=entity_id,
            source_type=source_type_raw,
            mention_count=mention_count,
            last_seen_at=row.get("last_seen_at", "").strip() or None,
            title=(row.get("title", "").strip() or None),
            url=(row.get("url", "").strip() or None),
            snippet=(row.get("snippet", "").strip() or None),
        ))

    org_id = resolve_request_org_id(db, current_user)
    result = _merge_observations(db, observations, org_id)
    result["warnings"] = warnings + result.get("warnings", [])
    db.commit()

    _audit(db, current_user, "external_attention.csv_import", {
        "imported": result["imported"],
        "entities_updated": result["entities_updated"],
        "filename": file.filename,
    })

    return BulkImportResponse(**result)


# ── Single-entity import ─────────────────────────────────────────────────────

@router.post(
    "/entities/{entity_id}/external-attention/import",
    response_model=SingleImportResponse,
    status_code=201,
    dependencies=[Depends(require_role("super_admin", "admin", "editor"))],
)
def single_entity_import(
    observations: List[SingleEntityObservationInput],
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Import external attention observations for a single entity."""
    if len(observations) > 500:
        raise HTTPException(status_code=422, detail="Maximum 500 observations per entity per request.")

    org_id = resolve_request_org_id(db, current_user)
    query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
    entity = query.filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found.")

    existing_attrs = _parse_attributes(entity.attributes_json)
    existing_obs = existing_attrs.get("external_attention_observations", [])
    if not isinstance(existing_obs, list):
        existing_obs = []

    imported = 0
    for obs in observations:
        new_entry = _build_observation_dict(obs)
        dedup_key = (obs.source_type, obs.url)
        merged = _dedup_merge(existing_obs, new_entry, dedup_key)
        if merged:
            imported += 1

    existing_attrs["external_attention_observations"] = existing_obs
    entity.attributes_json = json.dumps(existing_attrs, ensure_ascii=False)
    entity.updated_at = datetime.now(timezone.utc)
    db.commit()

    _audit(db, current_user, "external_attention.single_import", {
        "entity_id": entity_id,
        "imported": imported,
    })

    return SingleImportResponse(imported=imported, total_observations=len(existing_obs))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _merge_observations(
    db: Session,
    observations: list[ObservationInput],
    org_id: int | None,
) -> dict[str, Any]:
    """Merge observations into entity attributes_json, grouped by entity_id."""
    # Group by entity_id
    by_entity: dict[int, list[ObservationInput]] = {}
    for obs in observations:
        by_entity.setdefault(obs.entity_id, []).append(obs)

    # Load all referenced entities in one query
    entity_ids = list(by_entity.keys())
    query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
    entities = query.filter(models.RawEntity.id.in_(entity_ids)).all()
    entity_map = {e.id: e for e in entities}

    imported = 0
    skipped = 0
    entities_updated = 0
    warnings: list[str] = []

    for eid, obs_list in by_entity.items():
        entity = entity_map.get(eid)
        if entity is None:
            skipped += len(obs_list)
            warnings.append(f"Entity {eid} not found, {len(obs_list)} observations skipped.")
            continue

        existing_attrs = _parse_attributes(entity.attributes_json)
        existing_obs = existing_attrs.get("external_attention_observations", [])
        if not isinstance(existing_obs, list):
            existing_obs = []

        entity_imported = 0
        for obs in obs_list:
            new_entry = _build_observation_dict(obs)
            dedup_key = (obs.source_type, obs.url)
            merged = _dedup_merge(existing_obs, new_entry, dedup_key)
            if merged:
                entity_imported += 1

        if entity_imported > 0:
            existing_attrs["external_attention_observations"] = existing_obs
            entity.attributes_json = json.dumps(existing_attrs, ensure_ascii=False)
            entity.updated_at = datetime.now(timezone.utc)
            entities_updated += 1
            imported += entity_imported

    return {
        "imported": imported,
        "skipped": skipped,
        "entities_updated": entities_updated,
        "warnings": warnings,
    }


def _build_observation_dict(obs: ObservationInput | SingleEntityObservationInput) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "source_type": obs.source_type,
        "mention_count": obs.mention_count,
    }
    if obs.last_seen_at:
        entry["last_seen_at"] = obs.last_seen_at
    if obs.title:
        entry["title"] = obs.title[:_MAX_TITLE_LENGTH]
    if obs.url:
        entry["url"] = obs.url[:_MAX_URL_LENGTH]
    if obs.snippet:
        entry["snippet"] = obs.snippet[:_MAX_SNIPPET_LENGTH]
    return entry


def _dedup_merge(existing_obs: list[dict], new_entry: dict, dedup_key: tuple) -> bool:
    """Append or update observation. Dedup by (source_type, url).
    Returns True if a new entry was added or an existing one was updated."""
    source_type, url = dedup_key

    if url:
        for i, existing in enumerate(existing_obs):
            if existing.get("source_type") == source_type and existing.get("url") == url:
                # Update: higher mention_count wins, refresh last_seen_at
                existing["mention_count"] = max(
                    existing.get("mention_count", 1),
                    new_entry["mention_count"],
                )
                if new_entry.get("last_seen_at"):
                    existing["last_seen_at"] = new_entry["last_seen_at"]
                if new_entry.get("title"):
                    existing["title"] = new_entry["title"]
                if new_entry.get("snippet"):
                    existing["snippet"] = new_entry["snippet"]
                return True

    # No URL match — append
    existing_obs.append(new_entry)
    return True


def _parse_attributes(attributes_json: str | None) -> dict[str, Any]:
    if not attributes_json:
        return {}
    try:
        attrs = json.loads(attributes_json)
    except (TypeError, json.JSONDecodeError):
        return {}
    return attrs if isinstance(attrs, dict) else {}
