"""
Phase 11 — Context Engineering Layer
  GET  /context/snapshot/{domain_id}   — live domain context (not persisted)
  GET  /context/sessions               — list saved sessions
  POST /context/sessions               — save a new session  (201)
  DELETE /context/sessions/{id}        — delete a session    (204)
  GET  /context/tools                  — list available tools
  POST /context/invoke                 — invoke a tool by name
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.auth import get_current_user, require_role
from backend.context_engine import ContextEngine
from backend.database import get_db
from backend.routers.deps import _get_active_integration
from backend.schema_registry import SchemaRegistry
from backend.tenant_access import (
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/context", tags=["context"])

_engine = ContextEngine()


# ── Helper ─────────────────────────────────────────────────────────────────────

def _validate_domain(domain_id: str) -> None:
    if SchemaRegistry().get_domain(domain_id) is None:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")


# ── Snapshot (live, not persisted) ─────────────────────────────────────────────

@router.get("/snapshot/{domain_id}")
def get_snapshot(
    domain_id: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Return a live domain context snapshot (not saved to DB)."""
    _validate_domain(domain_id)
    return _engine.build_domain_context(domain_id, db)


# ── Saved sessions ─────────────────────────────────────────────────────────────

@router.get("/sessions")
def list_sessions(
    domain_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List saved analysis context sessions for the active org, optionally filtered by domain."""
    org_id = resolve_request_org_id(db, current_user)
    q = scope_query_to_org(
        db.query(models.AnalysisContext), models.AnalysisContext, org_id
    ).order_by(models.AnalysisContext.created_at.desc())
    if domain_id:
        q = q.filter(models.AnalysisContext.domain_id == domain_id)
    return q.limit(100).all()


@router.post("/sessions", status_code=201)
def create_session(
    payload: schemas.AnalysisContextCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Build and persist a domain context snapshot as a named session."""
    _validate_domain(payload.domain_id)
    org_id = resolve_request_org_id(db, current_user)
    ctx = _engine.build_domain_context(payload.domain_id, db)
    record = models.AnalysisContext(
        org_id=persisted_org_id(org_id),
        domain_id=payload.domain_id,
        user_id=current_user.id,
        label=payload.label or f"Snapshot {ctx['generated_at'][:10]}",
        context_snapshot=_engine.snapshot_json(ctx),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/sessions/diff")
def diff_sessions(
    a: int = Query(..., ge=1, description="ID of the older session"),
    b: int = Query(..., ge=1, description="ID of the newer session"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return a structured KPI delta between two saved sessions (A = older, B = newer)."""
    org_id = resolve_request_org_id(db, current_user)
    session_a = get_scoped_record(db, models.AnalysisContext, a, org_id)
    session_b = get_scoped_record(db, models.AnalysisContext, b, org_id)
    if not session_a:
        raise HTTPException(status_code=404, detail=f"Session {a} not found")
    if not session_b:
        raise HTTPException(status_code=404, detail=f"Session {b} not found")
    return _engine.diff_snapshots(session_a.context_snapshot, session_b.context_snapshot)


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return a single saved session; context_snapshot is returned as a parsed dict."""
    org_id = resolve_request_org_id(db, current_user)
    record = get_scoped_record(db, models.AnalysisContext, session_id, org_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id":               record.id,
        "domain_id":        record.domain_id,
        "user_id":          record.user_id,
        "label":            record.label,
        "notes":            record.notes,
        "pinned":           record.pinned,
        "context_snapshot": json.loads(record.context_snapshot),
        "created_at":       record.created_at,
    }


@router.patch("/sessions/{session_id}")
def update_session(
    payload: schemas.AnalysisContextUpdate,
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Update a session's label, notes, or pinned flag."""
    org_id = resolve_request_org_id(db, current_user)
    record = get_scoped_record(db, models.AnalysisContext, session_id, org_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Delete a saved session."""
    org_id = resolve_request_org_id(db, current_user)
    record = get_scoped_record(db, models.AnalysisContext, session_id, org_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(record)
    db.commit()


# ── AI Insights endpoints ──────────────────────────────────────────────────────

_INSIGHTS_SYSTEM = (
    "You are a senior data intelligence analyst specializing in knowledge management platforms. "
    "Respond in clear, structured prose. Be specific, concise, and actionable. "
    "Use the language of the domain provided in the context."
)


def _run_insights(prompt: str, db: Session) -> str:
    """Call the active LLM with the given analysis prompt and return its response."""
    from backend.analytics import rag_engine as _rag
    integration = _get_active_integration(db)
    if not integration:
        raise HTTPException(
            status_code=400,
            detail="No active AI provider. Configure one in Integrations → AI Language Models.",
        )
    adapter = _rag._build_adapter(integration)
    if not adapter:
        raise HTTPException(status_code=400, detail="Could not initialise AI adapter.")
    try:
        return adapter.chat(
            system_prompt=_INSIGHTS_SYSTEM,
            user_query=prompt,
            context_chunks=[],
        )
    except Exception as exc:
        logger.error("Insights LLM call failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}")


@router.post("/sessions/diff/insights")
def diff_insights(
    a: int = Query(..., ge=1, description="ID of the older session"),
    b: int = Query(..., ge=1, description="ID of the newer session"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Generate AI-written analysis of the delta between two saved sessions.
    Requires an active AI provider.
    """
    org_id = resolve_request_org_id(db, current_user)
    session_a = get_scoped_record(db, models.AnalysisContext, a, org_id)
    session_b = get_scoped_record(db, models.AnalysisContext, b, org_id)
    if not session_a:
        raise HTTPException(status_code=404, detail=f"Session {a} not found")
    if not session_b:
        raise HTTPException(status_code=404, detail=f"Session {b} not found")

    diff = _engine.diff_snapshots(session_a.context_snapshot, session_b.context_snapshot)
    prompt = _engine.build_diff_analysis_prompt(diff)
    analysis = _run_insights(prompt, db)

    return {
        "session_a_id": a,
        "session_b_id": b,
        "diff_summary":  diff,
        "analysis":      analysis,
    }


@router.post("/sessions/{session_id}/insights")
def session_insights(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Generate AI-written insights and recommendations for a single saved session.
    Requires an active AI provider.
    """
    org_id = resolve_request_org_id(db, current_user)
    record = get_scoped_record(db, models.AnalysisContext, session_id, org_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    prompt = _engine.build_analysis_prompt(record.context_snapshot)
    analysis = _run_insights(prompt, db)

    return {
        "session_id": session_id,
        "domain_id":  record.domain_id,
        "label":      record.label,
        "analysis":   analysis,
    }


# ── Tool Registry endpoints ─────────────────────────────────────────────────────

@router.get("/tools")
def list_tools(_: models.User = Depends(get_current_user)):
    """Return the list of available context tools."""
    from backend.tool_registry import get_registry
    return get_registry().list_tools()


@router.post("/invoke")
def invoke_tool(
    payload: dict,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Invoke a registered tool by name.
    Body: {"tool": "<name>", "params": {...}}
    """
    from backend.tool_registry import get_registry
    tool_name = payload.get("tool")
    params    = payload.get("params", {})
    if not tool_name:
        raise HTTPException(status_code=422, detail="'tool' field is required")
    registry = get_registry()
    try:
        result = registry.invoke(tool_name, params, db)
        return {"tool": tool_name, "result": result}
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found. Available: {[t['name'] for t in registry.list_tools()]}",
        )
    except Exception as exc:
        logger.error("Tool invocation error [%s]: %s", tool_name, exc)
        raise HTTPException(status_code=500, detail=str(exc))
