"""
Sprint 61 — Scheduled Imports: background scheduler + router.

Provides:
  - Background scheduler thread that checks for due imports every 30 seconds
  - CRUD endpoints for scheduled imports (admin+)
  - Manual trigger endpoint
  - Import execution that reuses the existing store pull logic
"""
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, List

from backend import models, database
from backend.auth import require_role
from backend.database import get_db
from backend.routers.deps import _get_store_adapter

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class ScheduledImportCreate(BaseModel):
    store_id: int
    name: str = Field(min_length=1, max_length=200)
    interval_minutes: int = Field(ge=5, le=10080)  # 5 min to 7 days


class ScheduledImportUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    interval_minutes: Optional[int] = Field(None, ge=5, le=10080)
    is_active: Optional[bool] = None


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize(s: models.ScheduledImport) -> dict:
    return {
        "id": s.id,
        "store_id": s.store_id,
        "name": s.name,
        "interval_minutes": s.interval_minutes,
        "is_active": s.is_active,
        "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
        "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
        "last_status": s.last_status,
        "last_result": json.loads(s.last_result) if s.last_result else None,
        "total_runs": s.total_runs,
        "total_entities_imported": s.total_entities_imported,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ── CRUD Endpoints ────────────────────────────────────────────────────────────

@router.post("/scheduled-imports", status_code=201, tags=["scheduled-imports"])
def create_scheduled_import(
    payload: ScheduledImportCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    # Verify store exists
    store = db.get(models.StoreConnection, payload.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")

    now = datetime.now(timezone.utc)
    schedule = models.ScheduledImport(
        store_id=payload.store_id,
        name=payload.name.strip(),
        interval_minutes=payload.interval_minutes,
        is_active=True,
        next_run_at=now + timedelta(minutes=payload.interval_minutes),
        created_at=now,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return _serialize(schedule)


@router.get("/scheduled-imports", tags=["scheduled-imports"])
def list_scheduled_imports(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    items = db.query(models.ScheduledImport).order_by(
        models.ScheduledImport.id.desc()
    ).all()
    # Enrich with store name
    store_ids = {s.store_id for s in items}
    stores = {
        s.id: s.name
        for s in db.query(models.StoreConnection).filter(
            models.StoreConnection.id.in_(store_ids)
        ).all()
    } if store_ids else {}
    result = []
    for s in items:
        d = _serialize(s)
        d["store_name"] = stores.get(s.store_id, "Unknown")
        result.append(d)
    return result


@router.get("/scheduled-imports/stats", tags=["scheduled-imports"])
def scheduled_imports_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    total = db.query(models.ScheduledImport).count()
    active = db.query(models.ScheduledImport).filter(
        models.ScheduledImport.is_active == True  # noqa: E712
    ).count()
    total_runs = sum(
        s.total_runs or 0
        for s in db.query(models.ScheduledImport).all()
    )
    total_entities = sum(
        s.total_entities_imported or 0
        for s in db.query(models.ScheduledImport).all()
    )
    return {
        "total": total,
        "active": active,
        "inactive": total - active,
        "total_runs": total_runs,
        "total_entities_imported": total_entities,
    }


@router.get("/scheduled-imports/{schedule_id}", tags=["scheduled-imports"])
def get_scheduled_import(
    schedule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    s = db.get(models.ScheduledImport, schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _serialize(s)


@router.put("/scheduled-imports/{schedule_id}", tags=["scheduled-imports"])
def update_scheduled_import(
    schedule_id: int = Path(..., ge=1),
    payload: ScheduledImportUpdate = ...,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    s = db.get(models.ScheduledImport, schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if payload.name is not None:
        s.name = payload.name.strip()
    if payload.interval_minutes is not None:
        s.interval_minutes = payload.interval_minutes
        # Recalculate next run
        base = s.last_run_at or datetime.now(timezone.utc)
        s.next_run_at = base + timedelta(minutes=payload.interval_minutes)
    if payload.is_active is not None:
        s.is_active = payload.is_active
        if payload.is_active and not s.next_run_at:
            s.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=s.interval_minutes)
    db.commit()
    db.refresh(s)
    return _serialize(s)


@router.delete("/scheduled-imports/{schedule_id}", tags=["scheduled-imports"])
def delete_scheduled_import(
    schedule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    s = db.get(models.ScheduledImport, schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(s)
    db.commit()
    return {"deleted": schedule_id}


@router.post("/scheduled-imports/{schedule_id}/trigger", tags=["scheduled-imports"])
def trigger_scheduled_import(
    schedule_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Manually trigger a scheduled import right now."""
    s = db.get(models.ScheduledImport, schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="Schedule not found")
    result = _execute_import(s, db)
    return result


# ── Import executor ───────────────────────────────────────────────────────────

def _execute_import(schedule: models.ScheduledImport, db: Session) -> dict:
    """Execute a single scheduled import. Reuses the store pull logic."""
    now = datetime.now(timezone.utc)
    schedule.last_run_at = now
    schedule.last_status = "running"
    db.commit()

    store = db.get(models.StoreConnection, schedule.store_id)
    if not store or not store.is_active:
        schedule.last_status = "error"
        schedule.last_result = json.dumps({"error": "Store not found or inactive"})
        schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)
        db.commit()
        return {"success": False, "error": "Store not found or inactive"}

    try:
        adapter = _get_store_adapter(store)
        remote_entities = adapter.fetch_entities(page=1, per_page=100)
    except Exception as e:
        schedule.last_status = "error"
        schedule.last_result = json.dumps({"error": str(e)})
        schedule.total_runs = (schedule.total_runs or 0) + 1
        schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)
        db.add(models.SyncLog(
            store_id=schedule.store_id, action="scheduled_pull", status="error",
            records_affected=0, details=str(e),
            executed_at=now,
        ))
        db.commit()
        return {"success": False, "error": str(e)}

    # Process remote entities (simplified pull logic)
    new_mappings = 0
    new_queue_items = 0
    skipped = 0

    for rp in remote_entities:
        if not rp.canonical_url:
            skipped += 1
            continue

        existing = db.query(models.StoreSyncMapping).filter(
            models.StoreSyncMapping.store_id == schedule.store_id,
            models.StoreSyncMapping.canonical_url == rp.canonical_url,
        ).first()

        if not existing:
            mapping = models.StoreSyncMapping(
                store_id=schedule.store_id,
                local_entity_id=None,
                remote_entity_id=rp.remote_id,
                canonical_url=rp.canonical_url,
                remote_sku=rp.sku,
                remote_name=rp.name,
                remote_price=rp.price,
                remote_stock=rp.stock,
                remote_status=rp.status,
                remote_data_json=(
                    json.dumps(rp.raw_data, default=str, ensure_ascii=False) if rp.raw_data else None
                ),
                sync_status="pending",
                created_at=now,
            )
            db.add(mapping)
            db.flush()
            new_mappings += 1

            db.add(models.SyncQueueItem(
                store_id=schedule.store_id,
                mapping_id=mapping.id,
                direction="pull",
                entity_name=rp.name,
                canonical_url=rp.canonical_url,
                field="new_entity",
                local_value=None,
                remote_value=rp.name,
                status="pending",
                created_at=now,
            ))
            new_queue_items += 1
        else:
            skipped += 1

    store.last_sync_at = now
    result_data = {
        "total_fetched": len(remote_entities),
        "new_mappings": new_mappings,
        "new_queue_items": new_queue_items,
        "skipped": skipped,
    }

    schedule.last_status = "success"
    schedule.last_result = json.dumps(result_data)
    schedule.total_runs = (schedule.total_runs or 0) + 1
    schedule.total_entities_imported = (schedule.total_entities_imported or 0) + new_mappings
    schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)

    db.add(models.SyncLog(
        store_id=schedule.store_id, action="scheduled_pull", status="success",
        records_affected=new_mappings + new_queue_items,
        details=json.dumps(result_data),
        executed_at=now,
    ))
    db.commit()

    return {"success": True, **result_data}


# ── Background scheduler ─────────────────────────────────────────────────────

_scheduler_thread: threading.Thread | None = None


def _scheduler_loop():
    """Check for due imports every 30 seconds."""
    while True:
        try:
            with database.SessionLocal() as db:
                now = datetime.now(timezone.utc)
                due = db.query(models.ScheduledImport).filter(
                    models.ScheduledImport.is_active == True,  # noqa: E712
                    models.ScheduledImport.next_run_at <= now,
                    models.ScheduledImport.last_status != "running",
                ).all()
                for schedule in due:
                    try:
                        logger.info("Scheduled import %d (%s) is due — executing",
                                    schedule.id, schedule.name)
                        _execute_import(schedule, db)
                    except Exception:
                        logger.exception("Error executing scheduled import %d", schedule.id)
        except Exception:
            logger.exception("Scheduler loop error")
        time.sleep(30)


def start_scheduler():
    """Start the background scheduler thread (called once during app lifespan)."""
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="import-scheduler")
    _scheduler_thread.start()
    logger.info("Import scheduler started")
