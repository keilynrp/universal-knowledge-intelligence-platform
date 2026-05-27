"""
AI integration and RAG (Retrieval-Augmented Generation) endpoints.
  GET/POST/PUT/DELETE /ai-integrations
  POST /ai-integrations/{id}/activate
  POST /rag/index
  POST /rag/query
  GET  /rag/stats
  DELETE /rag/index
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.analytics import rag_engine
from backend.analytics.vector_store import VectorStoreService
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.encryption import encrypt
from backend.routers.deps import _get_active_integration
from backend.routers.limiter import limiter
from backend.services.assistant_actions import require_assistant_action
from backend.tenant_access import get_scoped_record, resolve_request_org_id, scope_query_to_org

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai-rag"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class AIIntegrationPayload(schemas.BaseModel):
    provider_name: str = Field(min_length=1, max_length=100)
    base_url:   str | None = None
    api_key:    str | None = None
    model_name: str | None = None


class AIIntegrationUpdate(schemas.BaseModel):
    base_url:   str | None = Field(default=None, max_length=500)
    api_key:    str | None = None
    model_name: str | None = Field(default=None, max_length=100)


class RAGQueryPayload(BaseModel):
    question:    str          = Field(min_length=1, max_length=5000)
    top_k:       int          = Field(default=5, ge=1, le=20)
    min_similarity: float     = Field(default=rag_engine.MIN_SIMILARITY_SCORE, ge=0.0, le=1.0)
    use_context: bool         = Field(default=False)
    domain_id:   str | None   = Field(default=None, max_length=64)
    session_id:  int | None   = Field(default=None, ge=1)
    use_tools:   bool         = Field(default=False)


# ── AI Integrations ───────────────────────────────────────────────────────────

@router.get("/ai-integrations")
def get_ai_integrations(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    integrations = db.query(models.AIIntegration).all()
    return [
        {
            "id":            i.id,
            "provider_name": i.provider_name,
            "base_url":      i.base_url,
            "model_name":    i.model_name,
            "is_active":     i.is_active,
            "created_at":    str(i.created_at) if i.created_at else None,
            "has_api_key":   bool(i.api_key),
        }
        for i in integrations
    ]


@router.post("/ai-integrations", status_code=201)
def create_ai_integration(
    payload: AIIntegrationPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    existing = db.query(models.AIIntegration).filter(
        models.AIIntegration.provider_name == payload.provider_name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Provider already configured.")
    new_ai = models.AIIntegration(
        provider_name=payload.provider_name,
        base_url=payload.base_url,
        api_key=encrypt(payload.api_key),
        model_name=payload.model_name,
        is_active=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_ai)
    db.commit()
    db.refresh(new_ai)
    return {"message": f"Provider '{new_ai.provider_name}' configured", "id": new_ai.id}


@router.put("/ai-integrations/{integration_id}")
def update_ai_integration(
    integration_id: int = Path(..., ge=1),
    payload: AIIntegrationUpdate = ...,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    integration = db.query(models.AIIntegration).filter(
        models.AIIntegration.id == integration_id
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "base_url" in update_data:
        integration.base_url = update_data["base_url"]
    if "api_key" in update_data and update_data["api_key"] is not None:
        integration.api_key = encrypt(update_data["api_key"])
    if "model_name" in update_data:
        integration.model_name = update_data["model_name"]

    db.commit()
    return {"message": "Updated successfully", "id": integration.id}


@router.post("/ai-integrations/{integration_id}/activate")
def activate_ai_integration(
    integration_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    db.query(models.AIIntegration).update({"is_active": False})
    integration = db.query(models.AIIntegration).filter(
        models.AIIntegration.id == integration_id
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    integration.is_active = True
    db.commit()
    return {"message": f"{integration.provider_name} activated"}


@router.delete("/ai-integrations/{integration_id}")
def delete_ai_integration(
    integration_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    integration = db.query(models.AIIntegration).filter(
        models.AIIntegration.id == integration_id
    ).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    db.delete(integration)
    db.commit()
    return {"message": "Deleted"}


# ── RAG ───────────────────────────────────────────────────────────────────────

@router.post("/rag/index")
@limiter.limit("60/minute")
def rag_index_catalog(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Phase 5: Bulk index all enriched entities into the ChromaDB Vector Store."""
    require_assistant_action(current_user, "rag-reindex")
    integration = _get_active_integration(db)
    if not integration:
        raise HTTPException(
            status_code=400,
            detail="No active AI provider. Configure one in Integrations → AI Language Models.",
        )

    org_id = resolve_request_org_id(db, current_user)
    entities = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id).filter(
        models.RawEntity.enrichment_status.in_(rag_engine.ENRICHED_STATUSES)
    ).all()

    indexed = skipped = errors = 0
    for entity in entities:
        result = rag_engine.index_entity(entity, integration)
        if result["status"] == "indexed":
            indexed += 1
        elif result["status"] == "skipped":
            skipped += 1
        else:
            errors += 1

    return {
        "message":       "Indexing complete.",
        "indexed":       indexed,
        "skipped":       skipped,
        "errors":        errors,
        "provider_used": integration.provider_name,
    }


@router.post("/rag/index/entities/{entity_id}")
@limiter.limit("60/minute")
def rag_index_entity(
    request: Request,
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Incrementally index one enriched entity into the vector store."""
    integration = _get_active_integration(db)
    if not integration:
        raise HTTPException(status_code=400, detail="No active AI provider configured.")

    org_id = resolve_request_org_id(db, current_user)
    entity = get_scoped_record(db, models.RawEntity, entity_id, org_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    if entity.enrichment_status not in rag_engine.ENRICHED_STATUSES:
        raise HTTPException(status_code=409, detail="Entity is not enriched yet.")

    result = rag_engine.index_entity(entity, integration)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "Indexing failed"))
    return result


@router.post("/rag/query")
def rag_query(
    payload: RAGQueryPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """
    Phase 5 / 11: Natural language question answered using ChromaDB + active LLM.
    When use_context=True, a structured domain context block is prepended to the
    system prompt, grounding the LLM in the current data state.
    """
    integration = _get_active_integration(db)

    # Phase 11 / 69A: inject context into the system prompt (memory recall takes priority)
    extra_system = None

    if payload.session_id is not None:
        # Priority 1: recalled memory session
        session = db.get(models.AnalysisContext, payload.session_id)
        if session:
            try:
                from backend.context_engine import ContextEngine
                extra_system = ContextEngine().build_recall_prompt(
                    label=session.label,
                    context_json=session.context_snapshot,
                    user_query=payload.question,
                )
            except Exception:
                pass  # best-effort; fall back to plain RAG
    elif payload.use_context and payload.domain_id:
        # Priority 2: live domain context
        try:
            from backend.context_engine import ContextEngine
            ctx = ContextEngine().build_domain_context(payload.domain_id, db)
            extra_system = ContextEngine().format_for_llm(ctx)
        except Exception:
            pass

    if payload.use_tools:
        result = rag_engine.query_catalog_agentic(
            user_question=payload.question,
            integration_record=integration,
            db=db,
            top_k=payload.top_k,
            extra_system_context=extra_system,
            min_similarity=payload.min_similarity,
        )
    else:
        result = rag_engine.query_catalog(
            user_question=payload.question,
            integration_record=integration,
            top_k=payload.top_k,
            extra_system_context=extra_system,
            min_similarity=payload.min_similarity,
        )

    result["context_injected"]    = extra_system is not None
    result["memory_session_id"]   = payload.session_id
    return result


@router.get("/rag/stats")
def rag_stats(_: models.User = Depends(get_current_user)):
    """Returns ChromaDB index statistics."""
    return VectorStoreService.get_stats()


@router.delete("/rag/index")
def rag_clear_index(_: models.User = Depends(require_role("super_admin", "admin"))):
    """Clears the entire vector index. Use with caution."""
    VectorStoreService.clear_all()
    return {"message": "Vector index cleared."}
