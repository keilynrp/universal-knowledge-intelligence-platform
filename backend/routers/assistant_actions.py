"""Admin endpoints for UKIP Assistant action capabilities."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend import models
from backend.auth import get_current_user, require_role
from backend.services import assistant_actions

router = APIRouter(prefix="/assistant/actions", tags=["assistant-actions"])


class AssistantActionUpdate(BaseModel):
    enabled: bool | None = None
    allowed_roles: list[str] | None = None
    requires_confirmation: bool | None = None


@router.get("")
def list_assistant_actions(
    current_user: models.User = Depends(get_current_user),
):
    items = []
    for item in assistant_actions.list_capabilities():
        items.append({**item, "executable": item["enabled"] and current_user.role in item["allowed_roles"]})
    return {"items": items}


@router.put("/{action_id}")
def update_assistant_action(
    action_id: str,
    payload: AssistantActionUpdate,
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    updates = payload.model_dump(exclude_unset=True)
    return assistant_actions.update_capability(action_id, updates)
