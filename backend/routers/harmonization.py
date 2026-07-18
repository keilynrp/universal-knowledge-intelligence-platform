"""
Harmonization pipeline endpoints.
  GET  /harmonization/steps
  POST /harmonization/preview/{step_id}
  POST /harmonization/apply/{step_id}
  POST /harmonization/apply-all
  GET  /harmonization/logs
  POST /harmonization/undo/{log_id}
  POST /harmonization/redo/{log_id}
"""
import json
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import database, models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.routers.deps import _audit
from backend.notifications.emit import emit_outbound
from backend.routers.limiter import limiter
from backend.tenant_access import (
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["harmonization"])

# ── Harmonization pipeline metadata ──────────────────────────────────────────

from sqlalchemy import or_

HARMONIZATION_STEPS = [
    {
        "step_id":    "normalize_labels",
        "name":       "Normalize Labels",
        "description": "Trim whitespace and collapse internal spaces in primary_label and secondary_label.",
        "field":      "primary_label",
        "reversible": True,
    },
    {
        "step_id":    "normalize_canonical_ids",
        "name":       "Normalize Canonical IDs",
        "description": "Trim whitespace from canonical_id and set empty strings to NULL.",
        "field":      "canonical_id",
        "reversible": True,
    },
    {
        "step_id":    "normalize_entity_types",
        "name":       "Normalize Entity Types",
        "description": "Lowercase and strip entity_type values.",
        "field":      "entity_type",
        "reversible": True,
    },
    {
        "step_id":    "set_default_validation",
        "name":       "Set Default Validation Status",
        "description": "Set validation_status to 'pending' for any rows where it is NULL or empty.",
        "field":      "validation_status",
        "reversible": True,
    },
]

# ── Step functions ────────────────────────────────────────────────────────────

def _step_normalize_labels(db: Session, preview_only: bool, org_id: int | None = None):
    entities = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
        or_(
            models.RawEntity.primary_label != None,
            models.RawEntity.secondary_label != None,
        )
    ).all()
    changes = []
    for p in entities:
        for field in ("primary_label", "secondary_label"):
            val = getattr(p, field)
            if val is None:
                continue
            cleaned = re.sub(r"\s+", " ", val).strip()
            if cleaned != val:
                changes.append({
                    "record_id": p.id,
                    "field":     field,
                    "old_value": val,
                    "new_value": cleaned,
                })
                if not preview_only:
                    setattr(p, field, cleaned)
    if not preview_only:
        db.commit()
    return changes


def _step_normalize_canonical_ids(db: Session, preview_only: bool, org_id: int | None = None):
    entities = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
        models.RawEntity.canonical_id != None
    ).all()
    changes = []
    for p in entities:
        val = p.canonical_id
        if val is None:
            continue
        cleaned = val.strip() or None
        if cleaned != val:
            changes.append({
                "record_id": p.id,
                "field":     "canonical_id",
                "old_value": val,
                "new_value": cleaned,
            })
            if not preview_only:
                p.canonical_id = cleaned
    if not preview_only:
        db.commit()
    return changes


def _step_normalize_entity_types(db: Session, preview_only: bool, org_id: int | None = None):
    entities = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
        models.RawEntity.entity_type != None
    ).all()
    changes = []
    for p in entities:
        val = p.entity_type
        if val is None:
            continue
        cleaned = val.strip().lower()
        if cleaned != val:
            changes.append({
                "record_id": p.id,
                "field":     "entity_type",
                "old_value": val,
                "new_value": cleaned,
            })
            if not preview_only:
                p.entity_type = cleaned
    if not preview_only:
        db.commit()
    return changes


def _step_set_default_validation(db: Session, preview_only: bool, org_id: int | None = None):
    entities = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
        or_(
            models.RawEntity.validation_status == None,
            models.RawEntity.validation_status == "",
        )
    ).all()
    changes = []
    for p in entities:
        changes.append({
            "record_id": p.id,
            "field":     "validation_status",
            "old_value": p.validation_status,
            "new_value": "pending",
        })
        if not preview_only:
            p.validation_status = "pending"
    if not preview_only:
        db.commit()
    return changes


_PREVIEW_SAMPLE_CAP = 200  # Max change rows returned to the client for preview display


STEP_FUNCTIONS = {
    "normalize_labels":        _step_normalize_labels,
    "normalize_canonical_ids": _step_normalize_canonical_ids,
    "normalize_entity_types":  _step_normalize_entity_types,
    "set_default_validation":  _step_set_default_validation,
}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/harmonization/steps")
def get_harmonization_steps(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    total_entities = (
        scope_query_to_org(db.query(func.count(models.RawEntity.id)), models.RawEntity, org_id)
        .scalar()
        or 0
    )
    steps_with_status = []
    for idx, step in enumerate(HARMONIZATION_STEPS):
        last_log = (
            scope_query_to_org(db.query(models.HarmonizationLog), models.HarmonizationLog, org_id)
            .filter(models.HarmonizationLog.step_id == step["step_id"])
            .order_by(models.HarmonizationLog.id.desc())
            .first()
        )
        steps_with_status.append({
            **step,
            "order":                idx + 1,
            "status":               "completed" if last_log else "pending",
            "last_run":             last_log.executed_at.isoformat() if last_log and last_log.executed_at else None,
            "last_records_updated": last_log.records_updated if last_log else None,
        })
    return {"steps": steps_with_status, "total_entities": total_entities}


@router.post("/harmonization/preview/{step_id}")
def preview_harmonization_step(
    step_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    if step_id not in STEP_FUNCTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step_id}")
    step_def = next(s for s in HARMONIZATION_STEPS if s["step_id"] == step_id)
    changes = STEP_FUNCTIONS[step_id](db, preview_only=True, org_id=org_id)
    return {
        "step_id":       step_id,
        "step_name":     step_def["name"],
        "description":   step_def["description"],
        "total_affected": len(changes),
        "changes":       changes[:_PREVIEW_SAMPLE_CAP],
        "sample_changes": changes[:50],
    }


@router.post("/harmonization/apply/{step_id}")
def apply_harmonization_step(
    step_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    log_org_id = persisted_org_id(org_id)
    if step_id not in STEP_FUNCTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step_id}")
    step_def = next(s for s in HARMONIZATION_STEPS if s["step_id"] == step_id)
    changes = STEP_FUNCTIONS[step_id](db, preview_only=False, org_id=org_id)

    fields_modified = list({c["field"] for c in changes})
    log_entry = models.HarmonizationLog(
        org_id=log_org_id,
        step_id=step_id,
        step_name=step_def["name"],
        records_updated=len(changes),
        fields_modified=json.dumps(fields_modified),
        executed_at=datetime.now(timezone.utc),
        details=json.dumps({"sample": changes[:20]}),
        reverted=False,
    )
    db.add(log_entry)
    db.flush()

    for c in changes:
        db.add(models.HarmonizationChangeRecord(
            log_id=log_entry.id,
            record_id=c["record_id"],
            field=c["field"],
            old_value=c["old_value"],
            new_value=c["new_value"],
        ))

    _audit(
        db, "harmonization.apply",
        user_id=current_user.id,
        details={
            "step_id":         step_id,
            "step_name":       step_def["name"],
            "records_updated": len(changes),
        },
    )
    db.commit()
    emit_outbound(
        "harmonization.apply",
        {"step_id": step_id, "records_updated": len(changes)},
        database.SessionLocal,
    )
    return {
        "step_id":          step_id,
        "step_name":        step_def["name"],
        "records_updated":  len(changes),
        "fields_modified":  fields_modified,
        "log_id":           log_entry.id,
    }


@router.post("/harmonization/apply-all")
@limiter.limit("5/minute")
def apply_all_harmonization_steps(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    log_org_id = persisted_org_id(org_id)
    results = []
    for step in HARMONIZATION_STEPS:
        step_id = step["step_id"]
        changes = STEP_FUNCTIONS[step_id](db, preview_only=False, org_id=org_id)
        fields_modified = list({c["field"] for c in changes})

        log_entry = models.HarmonizationLog(
            org_id=log_org_id,
            step_id=step_id,
            step_name=step["name"],
            records_updated=len(changes),
            fields_modified=json.dumps(fields_modified),
            executed_at=datetime.now(timezone.utc),
            reverted=False,
        )
        db.add(log_entry)
        db.flush()

        for c in changes:
            db.add(models.HarmonizationChangeRecord(
                log_id=log_entry.id,
                record_id=c["record_id"],
                field=c["field"],
                old_value=c["old_value"],
                new_value=c["new_value"],
            ))

        _audit(
            db, "harmonization.apply",
            user_id=current_user.id,
            details={
                "step_id":         step_id,
                "step_name":       step["name"],
                "records_updated": len(changes),
                "via":             "apply_all",
            },
        )

        results.append({
            "step_id":         step_id,
            "step_name":       step["name"],
            "records_updated": len(changes),
            "fields_modified": fields_modified,
            "log_id":          log_entry.id,
        })

    db.commit()
    for r in results:
        emit_outbound(
            "harmonization.apply",
            {"step_id": r["step_id"], "records_updated": r["records_updated"]},
            database.SessionLocal,
        )
    return {"results": results, "total_steps": len(results)}


@router.get("/harmonization/logs")
def get_harmonization_logs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    logs = (
        scope_query_to_org(db.query(models.HarmonizationLog), models.HarmonizationLog, org_id)
        .order_by(models.HarmonizationLog.id.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id":               log.id,
            "step_id":          log.step_id,
            "step_name":        log.step_name,
            "records_updated":  log.records_updated,
            "fields_modified":  json.loads(log.fields_modified) if log.fields_modified else [],
            "executed_at":      log.executed_at.isoformat() if log.executed_at else None,
            "reverted":         bool(log.reverted) if log.reverted is not None else False,
        }
        for log in logs
    ]


@router.post("/harmonization/undo/{log_id}")
def undo_harmonization(
    log_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    log_entry = get_scoped_record(db, models.HarmonizationLog, log_id, org_id)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
    if log_entry.reverted:
        raise HTTPException(status_code=400, detail="This operation has already been reverted")

    change_records = db.query(models.HarmonizationChangeRecord).filter(
        models.HarmonizationChangeRecord.log_id == log_id
    ).all()

    if not change_records and log_entry.records_updated > 0:
        raise HTTPException(
            status_code=400,
            detail="No change records found for this log entry (pre-undo data not available)",
        )

    restored = 0
    for cr in change_records:
        entity = get_scoped_record(db, models.RawEntity, cr.record_id, org_id)
        if entity:
            setattr(entity, cr.field, cr.old_value)
            restored += 1

    log_entry.reverted = True
    db.commit()
    return {
        "log_id":           log_id,
        "action":           "undo",
        "records_restored": restored,
        "step_id":          log_entry.step_id,
        "step_name":        log_entry.step_name,
    }


@router.post("/harmonization/redo/{log_id}")
def redo_harmonization(
    log_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    log_entry = get_scoped_record(db, models.HarmonizationLog, log_id, org_id)
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
    if not log_entry.reverted:
        raise HTTPException(
            status_code=400, detail="This operation has not been reverted, cannot redo"
        )

    change_records = db.query(models.HarmonizationChangeRecord).filter(
        models.HarmonizationChangeRecord.log_id == log_id
    ).all()

    reapplied = 0
    for cr in change_records:
        entity = get_scoped_record(db, models.RawEntity, cr.record_id, org_id)
        if entity:
            setattr(entity, cr.field, cr.new_value)
            reapplied += 1

    log_entry.reverted = False
    db.commit()
    return {
        "log_id":           log_id,
        "action":           "redo",
        "records_restored": reapplied,
        "step_id":          log_entry.step_id,
        "step_name":        log_entry.step_name,
    }
