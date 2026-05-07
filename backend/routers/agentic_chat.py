"""
Agentic Research Chat router.

POST /agentic-chat/query
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user
from backend.database import get_db
from backend.routers.limiter import limiter
from backend.services.agentic_research_chat import (
    AgenticChatRequest,
    AgenticResearchChatService,
)
from backend.tenant_access import resolve_request_org_id

router = APIRouter(prefix="/agentic-chat", tags=["ai-rag"])


@router.post("/query")
@limiter.limit("20/minute")
def agentic_chat_query(
    request: Request,
    payload: AgenticChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Answer scoped research questions using RAG, NLQ and tool traces."""
    org_id = resolve_request_org_id(db, current_user)
    return AgenticResearchChatService.ask(
        db=db,
        payload=payload,
        current_user=current_user,
        org_id=org_id,
    )
