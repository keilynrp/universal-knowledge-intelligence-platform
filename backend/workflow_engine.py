"""
Sprint 92 — Workflow Automation Engine.

Evaluates trigger → conditions → actions chains against entity events.

Supported triggers
------------------
entity.created      fired when a new entity is ingested
entity.enriched     fired when enrichment_status changes to "completed"
entity.flagged      fired when validation_status changes to "failed"
manual              fired explicitly via the API

Supported conditions (all are AND-ed together)
-------------------------------------------------
field_equals        entity.<field> == value
field_contains      value in str(entity.<field>)
field_empty         entity.<field> is None or ""
enrichment_status_is  entity.enrichment_status == value

Supported actions
-----------------
send_webhook        POST JSON payload to a URL
tag_entity          Set entity.enrichment_concepts (append tag)
send_alert          Fire an active AlertChannel (type=webhook) notification
log_only            No-op; just records the run step (useful for testing)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend import models
from backend.tenant_access import LEGACY_GLOBAL_ORG_ID, scope_query_to_org

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Condition evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _get_entity_field(entity: models.RawEntity, field: str) -> Any:
    """Safely read an entity field; also looks inside attributes_json."""
    if hasattr(entity, field):
        return getattr(entity, field)
    try:
        attrs = json.loads(entity.attributes_json or "{}")
        return attrs.get(field)
    except (ValueError, TypeError):
        return None


def _evaluate_condition(entity: models.RawEntity, condition: dict) -> bool:
    ctype = condition.get("type", "")
    field = condition.get("field", "")
    value = condition.get("value", "")

    raw = _get_entity_field(entity, field)

    if ctype == "field_equals":
        return str(raw).strip().lower() == str(value).strip().lower()
    elif ctype == "field_contains":
        return value.lower() in str(raw or "").lower()
    elif ctype == "field_empty":
        return raw is None or str(raw).strip() == ""
    elif ctype == "enrichment_status_is":
        return (entity.enrichment_status or "") == value
    else:
        logger.warning("workflow_engine: unknown condition type=%s", ctype)
        return False


def _evaluate_conditions(entity: models.RawEntity, conditions: list[dict]) -> bool:
    """All conditions must pass (AND semantics). Empty list = always True."""
    return all(_evaluate_condition(entity, c) for c in conditions)


# ─────────────────────────────────────────────────────────────────────────────
# Action dispatch
# ─────────────────────────────────────────────────────────────────────────────

def _action_send_webhook(entity: models.RawEntity, config: dict) -> dict:
    url = config.get("url", "")
    if not url:
        return {"ok": False, "error": "No URL configured"}
    payload = {
        "event": "workflow.action",
        "entity_id": entity.id,
        "primary_label": entity.primary_label,
        "domain": entity.domain,
        **(config.get("extra_payload") or {}),
    }
    try:
        resp = httpx.post(url, json=payload, timeout=10)
        return {"ok": resp.is_success, "status_code": resp.status_code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _action_tag_entity(entity: models.RawEntity, config: dict, db: Session) -> dict:
    tag = config.get("tag", "").strip()
    if not tag:
        return {"ok": False, "error": "No tag specified"}
    current = entity.enrichment_concepts or ""
    tags = [t.strip() for t in current.split(",") if t.strip()]
    if tag not in tags:
        tags.append(tag)
        entity.enrichment_concepts = ", ".join(tags)
        db.commit()
    return {"ok": True, "tag": tag}


def _action_send_alert(entity: models.RawEntity, config: dict, db: Session) -> dict:
    channel_id = config.get("channel_id")
    if not channel_id:
        return {"ok": False, "error": "No channel_id specified"}
    channel = db.query(models.AlertChannel).filter(
        models.AlertChannel.id == channel_id,
        models.AlertChannel.is_active == True,  # noqa: E712
    ).first()
    if not channel:
        return {"ok": False, "error": f"AlertChannel {channel_id} not found or inactive"}

    from backend.encryption import decrypt_value
    try:
        url = decrypt_value(channel.webhook_url)
    except Exception:
        url = channel.webhook_url  # fallback if not encrypted

    message = config.get("message", f"Workflow triggered for entity: {entity.primary_label}")
    payload = {"text": message, "entity_id": entity.id}
    try:
        resp = httpx.post(url, json=payload, timeout=10)
        channel.last_fired_at = datetime.now(timezone.utc)
        channel.last_fire_status = "ok" if resp.is_success else "error"
        channel.total_fired = (channel.total_fired or 0) + 1
        db.commit()
        return {"ok": resp.is_success, "status_code": resp.status_code}
    except Exception as exc:
        channel.last_fire_status = "error"
        db.commit()
        return {"ok": False, "error": str(exc)}


def _action_log_only(entity: models.RawEntity, config: dict) -> dict:
    return {"ok": True, "logged": True, "entity_id": entity.id}


def _dispatch_action(
    entity: models.RawEntity, action: dict, db: Session
) -> dict:
    atype = action.get("type", "")
    cfg = action.get("config", {})
    try:
        if atype == "send_webhook":
            return _action_send_webhook(entity, cfg)
        elif atype == "tag_entity":
            return _action_tag_entity(entity, cfg, db)
        elif atype == "send_alert":
            return _action_send_alert(entity, cfg, db)
        elif atype == "log_only":
            return _action_log_only(entity, cfg)
        else:
            return {"ok": False, "error": f"Unknown action type: {atype}"}
    except Exception as exc:
        logger.exception("workflow_engine: action %s failed: %s", atype, exc)
        return {"ok": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def run_workflow(
    workflow: models.Workflow,
    entity: models.RawEntity,
    db: Session,
    trigger_data: dict | None = None,
) -> models.WorkflowRun:
    """
    Execute *workflow* for *entity*.  Persists a WorkflowRun and returns it.
    """
    run = models.WorkflowRun(
        workflow_id=workflow.id,
        org_id=getattr(workflow, "org_id", None),
        status="running",
        trigger_data=json.dumps(trigger_data or {}),
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    # NOTE: no db.refresh(run) here. The instance is already persistent after
    # commit and expired attributes reload lazily on access. An eager refresh
    # is also a flake trap on the shared StaticPool SQLite test connection: a
    # concurrent session rollback (e.g. a webhook dispatch thread) can discard
    # the row between COMMIT and the refresh SELECT.

    try:
        conditions = json.loads(workflow.conditions or "[]")
        actions = json.loads(workflow.actions or "[]")

        if not _evaluate_conditions(entity, conditions):
            run.status = "skipped"
            run.steps_log = json.dumps([{"skipped": "conditions not met"}])
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            _update_workflow_stats(workflow, "skipped", db)
            return run

        steps_log: list[dict] = []
        all_ok = True
        for action in actions:
            result = _dispatch_action(entity, action, db)
            steps_log.append({"action": action.get("type"), "result": result})
            if not result.get("ok"):
                all_ok = False

        run.status = "success" if all_ok else "error"
        run.steps_log = json.dumps(steps_log)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        _update_workflow_stats(workflow, run.status, db)

    except Exception as exc:
        logger.exception("workflow_engine: run failed for workflow=%s: %s", workflow.id, exc)
        run.status = "error"
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        _update_workflow_stats(workflow, "error", db)

    return run


def _update_workflow_stats(workflow: models.Workflow, status: str, db: Session) -> None:
    workflow.last_run_at = datetime.now(timezone.utc)
    workflow.run_count = (workflow.run_count or 0) + 1
    workflow.last_run_status = status
    db.commit()


def fire_trigger(trigger_type: str, entity: models.RawEntity, db: Session) -> list[models.WorkflowRun]:
    """
    Find active workflows matching *trigger_type* and run them against *entity*.
    Called by enrichment_worker or router events.
    Returns list of WorkflowRun records created.
    """
    workflows = db.query(models.Workflow).filter(
        models.Workflow.trigger_type == trigger_type,
        models.Workflow.is_active == True,  # noqa: E712
    )
    scope_org_id = getattr(entity, "org_id", None)
    if scope_org_id is None:
        scope_org_id = LEGACY_GLOBAL_ORG_ID
    workflows = scope_query_to_org(workflows, models.Workflow, scope_org_id).all()

    runs: list[models.WorkflowRun] = []
    for wf in workflows:
        try:
            run = run_workflow(wf, entity, db, trigger_data={"trigger": trigger_type, "entity_id": entity.id})
            runs.append(run)
        except Exception as exc:
            logger.exception("fire_trigger: workflow=%s failed: %s", wf.id, exc)
    return runs
