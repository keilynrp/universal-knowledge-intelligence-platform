"""
Phase 12 Sprint 51 — Audit Middleware
Intercepts every mutating request (POST/PUT/PATCH/DELETE) and writes an
immutable AuditLog entry after the response is produced.

Design principles:
- Non-blocking: audit failures never break the main request.
- Lightweight: only captures method, path, status code, user, and IP.
- Selective: skips noisy / non-domain paths (auth, docs, health).
"""
import logging
import re
from typing import Optional

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend import models
from backend.database import SessionLocal

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths to skip (auth handshakes, static docs, health probe, read-only)
_SKIP_PREFIXES = (
    "/auth/",
    "/health",
    "/docs",
    "/openapi",
    "/redoc",
)

# Map URL first-segment → human-readable resource type
_RESOURCE_MAP: dict[str, str] = {
    "entities":         "entity",
    "rules":            "rule",
    "reports":          "report",
    "exports":          "export",
    "artifacts":        "artifact",
    "context":          "context",
    "stores":           "store",
    "ai-integrations":  "ai_integration",
    "authority":        "authority",
    "harmonization":    "harmonization",
    "disambiguation":   "disambiguation",
    "domains":          "domain",
    "users":            "user",
    "annotations":      "annotation",
    "rag":              "rag",
    "demo":             "demo",
    "branding":         "branding",
    "cube":             "olap",
    "analyzers":        "analyzer",
    "webhooks":         "webhook",
    "notifications":    "notification",
    "enrich":           "enrichment",
    "upload":           "ingest",
    "import-export":    "ingest",
}

_RESOURCE_ID_RE = re.compile(r"/(\d+)(?:/|$)")
_ACTION_MAP = {
    "POST":   "CREATE",
    "PUT":    "UPDATE",
    "PATCH":  "UPDATE",
    "DELETE": "DELETE",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resource_type(path: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    return _RESOURCE_MAP.get(parts[0], parts[0]) if parts else "unknown"


def _resource_id(path: str) -> Optional[str]:
    m = _RESOURCE_ID_RE.search(path)
    return m.group(1) if m else None


def _decode_username(authorization: Optional[str]) -> Optional[str]:
    """Extract the 'sub' claim from the Bearer JWT without hitting the DB."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        from backend.auth import ALGORITHM, SECRET_KEY
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


# ── Middleware ─────────────────────────────────────────────────────────────────

class AuditMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that writes an AuditLog row for every successful
    mutating request.  Runs *after* the response is produced so it has the
    final HTTP status code.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if request.method not in _MUTATING_METHODS:
            return response

        path = request.url.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return response

        # Best-effort: never raise, never block the response
        try:
            username = _decode_username(request.headers.get("authorization"))
            db = SessionLocal()
            try:
                rid = _resource_id(path)
                db.add(models.AuditLog(
                    username=username,
                    action=_ACTION_MAP.get(request.method, request.method),
                    entity_type=_resource_type(path),
                    entity_id=int(rid) if rid else None,
                    endpoint=path,
                    method=request.method,
                    status_code=response.status_code,
                    ip_address=request.client.host if request.client else None,
                ))
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.debug("AuditMiddleware: failed to persist entry: %s", exc)

        return response
