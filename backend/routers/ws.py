"""
Sprint 91 — WebSocket router.

Single endpoint:  GET /ws/{room}?token=<jwt_or_api_key>

Room naming convention:
  entity-{id}      — entity detail page presence
  dashboard-{id}   — dashboard builder presence
  system           — platform-wide broadcasts (admin only)

Auth: Bearer tokens cannot be sent in the WS handshake headers from most
browsers, so we accept the JWT / API key as a ?token= query parameter.
The token is validated with the same logic as the HTTP auth dependency.

Client → Server messages:
  {"type": "ping",             "data": {}}
  {"type": "entity.editing",   "data": {"field": "primary_label", "editing": true}}
  {"type": "entity.saved",     "data": {"entity_id": 42}}
  {"type": "dashboard.updated","data": {"dashboard_id": 3}}

Server → Client messages (in addition to relayed client messages):
  {"type": "pong",             "data": {}}
  {"type": "presence.list",    "data": {"users": [...]}}
  {"type": "presence.join",    "data": {user_info}}
  {"type": "presence.leave",   "data": {user_info}}
  {"type": "system.event",     "data": {"event": "...", "payload": {...}}}
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.ws.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Message types the client is allowed to relay to the room
_RELAY_TYPES = {"entity.editing", "entity.saved", "dashboard.updated", "system.event"}


def _resolve_user(token: str, db: Session) -> models.User | None:
    """
    Validate a JWT or ukip_ API key against *db*.
    Returns the active User on success, None otherwise.
    """
    from jose import JWTError
    from backend.auth import _decode_token

    try:
        if token.startswith("ukip_"):
            from backend.routers.api_keys import verify_api_key
            key_record = verify_api_key(token, db)
            if not key_record:
                return None
            return db.query(models.User).filter(
                models.User.id == key_record.user_id,
                models.User.is_active == True,  # noqa: E712
            ).first()

        payload = _decode_token(token)
        username: str | None = payload.get("sub")
        if not username:
            return None
        return db.query(models.User).filter(
            models.User.username == username,
            models.User.is_active == True,  # noqa: E712
        ).first()

    except JWTError:
        return None


@router.websocket("/ws/{room}")
async def websocket_endpoint(
    websocket: WebSocket,
    room: str,
    token: str = Query(..., description="JWT or ukip_ API key"),
    db: Session = Depends(get_db),
) -> None:
    """
    Presence & collaboration WebSocket.

    Room format:  entity-{id} | dashboard-{id} | system
    """
    # ── Authenticate ──────────────────────────────────────────────────────────
    user = _resolve_user(token, db)
    if user is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    user_info = {
        "user_id": user.id,
        "username": user.username,
        "display_name": getattr(user, "display_name", None) or user.username,
    }

    # ── Join room ─────────────────────────────────────────────────────────────
    await manager.connect(websocket, room, user_info)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type: str = data.get("type", "")
            msg_data: dict = data.get("data", {})

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "data": {}})

            elif msg_type in _RELAY_TYPES:
                # Attach sender identity and relay to the room
                await manager.broadcast(
                    room,
                    {
                        "type": msg_type,
                        "data": {
                            **msg_data,
                            "user_id": user.id,
                            "username": user.username,
                        },
                    },
                )

            else:
                # Unknown message type — silently ignore
                logger.debug("WS unknown type=%s user=%s room=%s", msg_type, user.username, room)

    except WebSocketDisconnect:
        await manager.disconnect(websocket, room, user_info)
    except Exception as exc:
        logger.warning("WS error room=%s user=%s: %s", room, user.username, exc)
        await manager.disconnect(websocket, room, user_info)
