"""
Store integration and sync engine endpoints.
  GET/POST/PUT/DELETE /stores
  GET /stores/{store_id}
  POST /stores/{store_id}/toggle
  GET  /stores/stats/summary
  POST /stores/{store_id}/test
  POST /stores/{store_id}/pull
  GET  /stores/{store_id}/mappings
  GET  /stores/{store_id}/queue
  POST /stores/queue/{item_id}/approve
  POST /stores/queue/{item_id}/reject
  POST /stores/queue/bulk-approve
  POST /stores/queue/bulk-reject
  GET  /stores/{store_id}/logs
"""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from backend import database, models, schemas
from backend.auth import require_role
from backend.database import get_db
from backend.encryption import encrypt
from backend.notifications.emit import emit_outbound
from backend.routers.deps import _audit, _get_store_adapter
from backend.routers.limiter import limiter
from backend.tenant_quotas import assert_org_quota_available
from backend.tenant_access import (
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stores"])


def _get_scoped_store(db: Session, store_id: int, org_id: int | None) -> models.StoreConnection | None:
    return get_scoped_record(db, models.StoreConnection, store_id, org_id)


@router.get("/stores")
def get_all_stores(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    stores = (
        scope_query_to_org(db.query(models.StoreConnection), models.StoreConnection, org_id)
        .order_by(models.StoreConnection.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id":             s.id,
            "name":           s.name,
            "platform":       s.platform,
            "base_url":       s.base_url,
            "is_active":      s.is_active,
            "last_sync_at":   str(s.last_sync_at) if s.last_sync_at else None,
            "created_at":     str(s.created_at) if s.created_at else None,
            "entity_count":   s.entity_count or 0,
            "sync_direction": s.sync_direction or "bidirectional",
            "notes":          s.notes,
        }
        for s in stores
    ]


@router.get("/stores/{store_id}")
def get_store(
    store_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")
    return {
        "id":               store.id,
        "name":             store.name,
        "platform":         store.platform,
        "base_url":         store.base_url,
        "is_active":        store.is_active,
        "last_sync_at":     str(store.last_sync_at) if store.last_sync_at else None,
        "created_at":       str(store.created_at) if store.created_at else None,
        "entity_count":     store.entity_count or 0,
        "sync_direction":   store.sync_direction or "bidirectional",
        "notes":            store.notes,
        "has_api_key":      bool(store.api_key),
        "has_api_secret":   bool(store.api_secret),
        "has_access_token": bool(store.access_token),
    }


@router.post("/stores", status_code=201)
def create_store(
    payload: schemas.StoreConnectionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = persisted_org_id(resolve_request_org_id(db, current_user))
    assert_org_quota_available(db, org_id, "stores", current_user=current_user)
    store = models.StoreConnection(
        org_id=org_id,
        name=payload.name.strip(),
        platform=payload.platform,
        base_url=payload.base_url.rstrip("/"),
        api_key=encrypt(payload.api_key),
        api_secret=encrypt(payload.api_secret),
        access_token=encrypt(payload.access_token),
        custom_headers=payload.custom_headers,
        sync_direction=payload.sync_direction,
        notes=payload.notes,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        entity_count=0,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return {
        "message":  f"Store '{store.name}' created successfully",
        "id":       store.id,
        "platform": store.platform,
    }


@router.put("/stores/{store_id}")
def update_store(
    store_id: int = Path(..., ge=1),
    payload: schemas.StoreConnectionUpdate = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"]:
        update_data["name"] = update_data["name"].strip()
    if "base_url" in update_data and update_data["base_url"]:
        update_data["base_url"] = update_data["base_url"].rstrip("/")

    for cred_field in ("api_key", "api_secret", "access_token"):
        if cred_field in update_data and update_data[cred_field] is not None:
            update_data[cred_field] = encrypt(update_data[cred_field])

    for field, value in update_data.items():
        setattr(store, field, value)

    db.commit()
    db.refresh(store)
    return {"message": f"Store '{store.name}' updated successfully", "id": store.id}


@router.delete("/stores/{store_id}")
def delete_store(
    store_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")

    db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.store_id == store_id
    ).delete()
    db.query(models.StoreSyncMapping).filter(
        models.StoreSyncMapping.store_id == store_id
    ).delete()
    db.query(models.SyncLog).filter(models.SyncLog.store_id == store_id).delete()
    db.delete(store)
    db.commit()
    return {
        "message": f"Store '{store.name}' and all associated data deleted",
        "id":      store_id,
    }


@router.post("/stores/{store_id}/toggle")
def toggle_store(
    store_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")
    store.is_active = not store.is_active
    db.commit()
    return {
        "message":   f"Store '{store.name}' {'activated' if store.is_active else 'deactivated'}",
        "is_active": store.is_active,
    }


@router.get("/stores/stats/summary")
def get_stores_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    store_query = scope_query_to_org(db.query(models.StoreConnection), models.StoreConnection, org_id)
    total_stores = store_query.count()
    active_stores = (
        scope_query_to_org(db.query(models.StoreConnection), models.StoreConnection, org_id)
        .filter(models.StoreConnection.is_active == True)
        .count()
    )
    store_ids = [store.id for store in store_query.all()]
    total_mappings = (
        db.query(func.count(models.StoreSyncMapping.id))
        .filter(models.StoreSyncMapping.store_id.in_(store_ids))
        .scalar() or 0
    ) if store_ids else 0
    platform_counts = scope_query_to_org(db.query(
        models.StoreConnection.platform,
        func.count(models.StoreConnection.id),
    ), models.StoreConnection, org_id).group_by(models.StoreConnection.platform).all()

    return {
        "total_stores":   total_stores,
        "active_stores":  active_stores,
        "total_mappings": total_mappings,
        "platforms":      {p[0]: p[1] for p in platform_counts},
    }


# ── Sync engine ───────────────────────────────────────────────────────────────

@router.post("/stores/{store_id}/test")
@limiter.limit("10/minute")
def test_store_connection(
    request: Request,
    store_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    try:
        adapter = _get_store_adapter(store)
        result = adapter.test_connection()
        return {
            "success":      result.success,
            "message":      result.message,
            "store_name":   result.store_name,
            "entity_count": result.entity_count,
            "api_version":  result.api_version,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/stores/{store_id}/pull")
@limiter.limit("60/minute")
def pull_entities_from_store(
    request: Request,
    store_id: int = Path(..., ge=1),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Pull entities from remote store and create queue items for human review."""
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    if not store.is_active:
        raise HTTPException(status_code=400, detail="Store connection is inactive")

    try:
        adapter = _get_store_adapter(store)
        remote_entities = adapter.fetch_entities(page=page, per_page=per_page)
    except Exception as e:
        db.add(models.SyncLog(
            store_id=store_id, action="pull", status="error",
            records_affected=0, details=str(e),
            executed_at=datetime.now(timezone.utc),
        ))
        db.commit()
        raise HTTPException(status_code=502, detail=f"Failed to fetch from store: {e}")

    new_mappings    = 0
    new_queue_items = 0
    skipped         = 0

    for rp in remote_entities:
        if not rp.canonical_url:
            skipped += 1
            continue

        existing = db.query(models.StoreSyncMapping).filter(
            models.StoreSyncMapping.store_id    == store_id,
            models.StoreSyncMapping.canonical_url == rp.canonical_url,
        ).first()

        if not existing:
            mapping = models.StoreSyncMapping(
                store_id=store_id,
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
                created_at=datetime.now(timezone.utc),
            )
            db.add(mapping)
            db.flush()
            new_mappings += 1

            db.add(models.SyncQueueItem(
                store_id=store_id,
                mapping_id=mapping.id,
                direction="pull",
                entity_name=rp.name,
                canonical_url=rp.canonical_url,
                field="new_entity",
                local_value=None,
                remote_value=rp.name,
                status="pending",
                created_at=datetime.now(timezone.utc),
            ))
            new_queue_items += 1
        else:
            changes = []
            if existing.remote_name   != rp.name   and rp.name:
                changes.append(("name",   existing.remote_name,   rp.name))
            if existing.remote_price  != rp.price  and rp.price:
                changes.append(("price",  existing.remote_price,  rp.price))
            if existing.remote_stock  != rp.stock  and rp.stock:
                changes.append(("stock",  existing.remote_stock,  rp.stock))
            if existing.remote_sku    != rp.sku    and rp.sku:
                changes.append(("sku",    existing.remote_sku,    rp.sku))
            if existing.remote_status != rp.status and rp.status:
                changes.append(("status", existing.remote_status, rp.status))

            for field, old_val, new_val in changes:
                already_pending = db.query(models.SyncQueueItem).filter(
                    models.SyncQueueItem.mapping_id == existing.id,
                    models.SyncQueueItem.field      == field,
                    models.SyncQueueItem.status     == "pending",
                ).first()
                if not already_pending:
                    db.add(models.SyncQueueItem(
                        store_id=store_id,
                        mapping_id=existing.id,
                        direction="pull",
                        entity_name=rp.name,
                        canonical_url=rp.canonical_url,
                        field=field,
                        local_value=old_val,
                        remote_value=new_val,
                        status="pending",
                        created_at=datetime.now(timezone.utc),
                    ))
                    new_queue_items += 1

            existing.remote_name    = rp.name   or existing.remote_name
            existing.remote_price   = rp.price  or existing.remote_price
            existing.remote_stock   = rp.stock  or existing.remote_stock
            existing.remote_sku     = rp.sku    or existing.remote_sku
            existing.remote_status  = rp.status or existing.remote_status
            existing.remote_data_json = (
                json.dumps(rp.raw_data, default=str, ensure_ascii=False)
                if rp.raw_data else existing.remote_data_json
            )
            existing.last_synced_at = datetime.now(timezone.utc)

    store.last_sync_at = datetime.now(timezone.utc)
    db.add(models.SyncLog(
        store_id=store_id, action="pull", status="success",
        records_affected=new_mappings + new_queue_items,
        details=json.dumps({"new_mappings": new_mappings, "queue_items": new_queue_items, "skipped": skipped}),
        executed_at=datetime.now(timezone.utc),
    ))
    _audit(
        db, "pull",
        entity_type="store", entity_id=store_id,
        details={"new_mappings": new_mappings, "queue_items": new_queue_items, "skipped": skipped},
    )
    db.commit()

    emit_outbound(
        "pull",
        {"store_id": store_id, "new_mappings": new_mappings, "queue_items": new_queue_items},
        database.SessionLocal,
    )
    return {
        "message":       f"Pull completed: {len(remote_entities)} entities fetched",
        "new_mappings":  new_mappings,
        "new_queue_items": new_queue_items,
        "skipped":       skipped,
        "total_fetched": len(remote_entities),
    }


@router.get("/stores/{store_id}/mappings")
def get_store_mappings(
    store_id: int = Path(..., ge=1),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")
    total = (
        db.query(func.count(models.StoreSyncMapping.id))
        .filter(models.StoreSyncMapping.store_id == store_id)
        .scalar() or 0
    )
    mappings = (
        db.query(models.StoreSyncMapping)
        .filter(models.StoreSyncMapping.store_id == store_id)
        .order_by(models.StoreSyncMapping.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return {
        "total":    total,
        "mappings": [
            {
                "id":               m.id,
                "local_entity_id":  m.local_entity_id,
                "remote_entity_id": m.remote_entity_id,
                "canonical_url":    m.canonical_url,
                "remote_sku":       m.remote_sku,
                "remote_name":      m.remote_name,
                "remote_price":     m.remote_price,
                "remote_stock":     m.remote_stock,
                "remote_status":    m.remote_status,
                "sync_status":      m.sync_status,
                "last_synced_at":   str(m.last_synced_at) if m.last_synced_at else None,
            }
            for m in mappings
        ],
    }


@router.get("/stores/{store_id}/queue")
def get_store_queue(
    store_id: int = Path(..., ge=1),
    status: str = "pending",
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")
    query = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.store_id == store_id
    )
    if status != "all":
        query = query.filter(models.SyncQueueItem.status == status)

    total = query.count()
    items = query.order_by(models.SyncQueueItem.id.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id":           q.id,
                "mapping_id":   q.mapping_id,
                "direction":    q.direction,
                "entity_name":  q.entity_name,
                "canonical_url": q.canonical_url,
                "field":        q.field,
                "local_value":  q.local_value,
                "remote_value": q.remote_value,
                "status":       q.status,
                "created_at":   str(q.created_at) if q.created_at else None,
                "resolved_at":  str(q.resolved_at) if q.resolved_at else None,
            }
            for q in items
        ],
    }


# Queue actions — static paths must come before /{store_id} routes,
# but since these use /stores/queue/* (not /stores/{store_id}/queue/*),
# FastAPI correctly routes them via literal "queue" segment.

@router.post("/stores/queue/{item_id}/approve")
def approve_queue_item(
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    item = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.id == item_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    store = _get_scoped_store(db, item.store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item.status != "pending":
        raise HTTPException(status_code=409, detail=f"Item is already {item.status}")

    now = datetime.now(timezone.utc)
    item.status = "approved"
    item.resolved_at = now
    db.commit()
    return {"message": "Item approved", "id": item_id, "status": "approved"}


@router.post("/stores/queue/{item_id}/reject")
def reject_queue_item(
    item_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    item = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.id == item_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    store = _get_scoped_store(db, item.store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if item.status != "pending":
        raise HTTPException(status_code=409, detail=f"Item is already {item.status}")

    now = datetime.now(timezone.utc)
    item.status = "rejected"
    item.resolved_at = now
    db.commit()
    return {"message": "Item rejected", "id": item_id, "status": "rejected"}


@router.post("/stores/queue/bulk-approve")
def bulk_approve_queue(
    store_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Approve all pending queue items for a store."""
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")
    updated = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.store_id == store_id,
        models.SyncQueueItem.status   == "pending",
    ).update({"status": "approved", "resolved_at": datetime.now(timezone.utc)})
    db.commit()
    return {"message": f"{updated} items approved", "count": updated}


@router.post("/stores/queue/bulk-reject")
def bulk_reject_queue(
    store_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Reject all pending queue items for a store."""
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")
    updated = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.store_id == store_id,
        models.SyncQueueItem.status   == "pending",
    ).update({"status": "rejected", "resolved_at": datetime.now(timezone.utc)})
    db.commit()
    return {"message": f"{updated} items rejected", "count": updated}


@router.get("/stores/{store_id}/logs")
def get_store_logs(
    store_id: int = Path(..., ge=1),
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    store = _get_scoped_store(db, store_id, org_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")
    logs = (
        db.query(models.SyncLog)
        .filter(models.SyncLog.store_id == store_id)
        .order_by(models.SyncLog.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id":               l.id,
            "action":           l.action,
            "status":           l.status,
            "records_affected": l.records_affected,
            "details":          l.details,
            "executed_at":      str(l.executed_at) if l.executed_at else None,
        }
        for l in logs
    ]
