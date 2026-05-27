"""Capability registry and guardrails for UKIP Assistant actions."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, status

from backend import models

Risk = Literal["low", "medium", "high"]
RollbackMode = Literal["none", "manual", "snapshot"]


@dataclass(frozen=True)
class AssistantActionCapability:
    id: str
    label: str
    description: str
    api_path: str | None
    method: str | None
    kind: str
    risk: Risk
    allowed_roles: list[str]
    requires_confirmation: bool
    rollback: RollbackMode
    enabled: bool = True


REGISTRY: dict[str, AssistantActionCapability] = {
    "audit-export": AssistantActionCapability(
        id="audit-export",
        label="Exportar auditoria filtrada",
        description="Descarga eventos de auditoria aplicando los filtros actuales.",
        api_path="/audit-log/export",
        method="GET",
        kind="export",
        risk="medium",
        allowed_roles=["super_admin", "admin"],
        requires_confirmation=True,
        rollback="none",
    ),
    "rag-reindex": AssistantActionCapability(
        id="rag-reindex",
        label="Reindexar catalogo RAG",
        description="Reconstruye el indice semantico con entidades enriquecidas.",
        api_path="/rag/index",
        method="POST",
        kind="mutation",
        risk="high",
        allowed_roles=["super_admin", "admin"],
        requires_confirmation=True,
        rollback="manual",
    ),
    "entity-enrich-current": AssistantActionCapability(
        id="entity-enrich-current",
        label="Enriquecer registro actual",
        description="Ejecuta enriquecimiento sobre una entidad individual.",
        api_path="/enrich/row/{entity_id}",
        method="POST",
        kind="mutation",
        risk="medium",
        allowed_roles=["super_admin", "admin", "editor"],
        requires_confirmation=True,
        rollback="snapshot",
    ),
}


def _config_path() -> Path:
    configured = os.environ.get("ASSISTANT_ACTION_GUARDRAILS_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "assistant_action_guardrails.json"


def _load_overrides() -> dict[str, dict]:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_overrides(overrides: dict[str, dict]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides, indent=2, sort_keys=True), encoding="utf-8")


def list_capabilities() -> list[dict]:
    overrides = _load_overrides()
    capabilities: list[dict] = []
    for action_id, capability in REGISTRY.items():
        item = asdict(capability)
        item.update(overrides.get(action_id, {}))
        item["configured"] = action_id in overrides
        capabilities.append(item)
    return capabilities


def get_capability(action_id: str) -> dict:
    if action_id not in REGISTRY:
        raise HTTPException(status_code=404, detail="Assistant action is not registered")
    overrides = _load_overrides()
    item = asdict(REGISTRY[action_id])
    item.update(overrides.get(action_id, {}))
    item["configured"] = action_id in overrides
    return item


def update_capability(action_id: str, updates: dict) -> dict:
    if action_id not in REGISTRY:
        raise HTTPException(status_code=404, detail="Assistant action is not registered")

    base = asdict(REGISTRY[action_id])
    allowed_keys = {"enabled", "allowed_roles", "requires_confirmation"}
    cleaned = {key: value for key, value in updates.items() if key in allowed_keys}
    if "allowed_roles" in cleaned:
        valid_roles = {"super_admin", "admin", "editor", "viewer"}
        roles = cleaned["allowed_roles"]
        if not isinstance(roles, list) or not roles or any(role not in valid_roles for role in roles):
            raise HTTPException(status_code=400, detail="Invalid role list")
        if base["risk"] == "high" and "viewer" in roles:
            raise HTTPException(status_code=400, detail="Viewer cannot execute high-risk assistant actions")

    overrides = _load_overrides()
    overrides[action_id] = {**overrides.get(action_id, {}), **cleaned}
    _save_overrides(overrides)
    return get_capability(action_id)


def require_assistant_action(user: models.User, action_id: str) -> dict:
    capability = get_capability(action_id)
    if not capability["enabled"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Assistant action '{action_id}' is disabled",
        )
    if user.role not in capability["allowed_roles"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role}' is not allowed to execute assistant action '{action_id}'",
        )
    return capability
