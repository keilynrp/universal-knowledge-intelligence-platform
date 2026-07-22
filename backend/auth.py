"""
JWT Authentication module for UKIP.
Multi-user RBAC model: credentials stored in the 'users' table.
Roles: super_admin | admin | editor | viewer
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.api_key_scopes import READ, satisfies, scope_required
from backend.database import get_db
from backend import models

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────
_INSECURE_DEFAULT_KEY = "INSECURE_DEV_KEY_change_in_production"
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", _INSECURE_DEFAULT_KEY)

if SECRET_KEY == _INSECURE_DEFAULT_KEY:
    logger.critical(
        "JWT_SECRET_KEY is not set — using the insecure default key. "
        "Set JWT_SECRET_KEY in your environment before deploying to production."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))  # 8h
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_REFRESH_MINUTES", "10080")) # 7 days


def _parse_secret_keys(raw):  # raw: str | None
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


# Verify-only retiring JWT keys (decode grace window during rotation).
RETIRING_SECRET_KEYS = _parse_secret_keys(os.environ.get("JWT_SECRET_KEYS_RETIRING"))


def _decode_token(token: str) -> dict:
    """Decode a JWT, verifying against the primary key then each retiring key.

    Raises jose.JWTError if no configured key validates the token. This is the
    single decode path for ALL JWT verification sites.
    """
    keys = [SECRET_KEY, *RETIRING_SECRET_KEYS]
    last_error: Optional[JWTError] = None
    for key in keys:
        try:
            return jwt.decode(token, key, algorithms=[ALGORITHM])
        except JWTError as exc:
            last_error = exc
            continue
    raise last_error if last_error else JWTError("No JWT keys configured")


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


# ── Helpers ─────────────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(
        {"sub": subject, "role": role, "exp": expire, "type": "access"},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_refresh_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(
        {"sub": subject, "role": role, "exp": expire, "type": "refresh"},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    """Return the User if credentials are valid, None otherwise.

    Raises HTTP 423 if the account is currently locked out.
    After _MAX_FAILED_ATTEMPTS consecutive failures the account is locked
    for _LOCKOUT_MINUTES minutes.
    """
    user = (
        db.query(models.User)
        .filter(models.User.username == username, models.User.is_active == True)
        .first()
    )
    if not user:
        return None

    # Check if account is currently locked
    if user.locked_until:
        lock_expiry = datetime.fromisoformat(user.locked_until)
        if datetime.now(timezone.utc) < lock_expiry:
            raise HTTPException(
                status_code=423,
                detail=f"Account locked. Try again after {user.locked_until}",
            )
        # Lock has expired — reset
        user.locked_until = None
        user.failed_attempts = 0
        db.commit()

    if not verify_password(password, user.password_hash):
        user.failed_attempts = (user.failed_attempts or 0) + 1
        if user.failed_attempts >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = (
                datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)
            ).isoformat()
        db.commit()
        return None

    # Successful login — reset counters
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
    return user


# ── API key scopes ───────────────────────────────────────────────────────────

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def api_key_scopes_enforced() -> bool:
    """Whether a scope violation blocks the request or is merely recorded.

    Read at call time rather than at import, so the rollout flag can be flipped
    without rebuilding the image — and so tests can exercise both modes.
    """
    raw = os.environ.get("UKIP_API_KEY_SCOPES_ENFORCED", "0")
    return raw.strip().lower() in _TRUTHY


def _granted_scopes(key_record: models.ApiKey) -> list[str]:
    """Scopes on the key, or an empty list if the column is absent or corrupt.

    Fail-closed: an unreadable scope list grants nothing.
    """
    try:
        parsed = json.loads(key_record.scopes) if key_record.scopes else []
    except (TypeError, ValueError):
        logger.warning("API key %s has an unparseable scope list", key_record.key_prefix)
        return []
    if not isinstance(parsed, list):
        return []
    return [scope for scope in parsed if isinstance(scope, str)]


def _route_template(request: Request) -> str:
    """The matched route template (``/entities/{entity_id}``).

    Matching the template rather than the concrete URL keeps an identifier that
    happens to contain an admin-looking segment from changing the
    classification, and lets parameterized read-overrides match at all.
    """
    route = request.scope.get("route")
    return getattr(route, "path", None) or request.url.path


def _record_scope_violation(
    db: Session,
    key_record: models.ApiKey,
    method: str,
    path: str,
    required: str,
    granted: list[str],
    enforced: bool,
) -> None:
    """Persist a violation for the warn-mode observation window.

    Written to the audit log rather than only the app log so the window can be
    reviewed from the UI. Records the key prefix only — never the key, never
    the hash. Never raises: observability must not break a request.
    """
    try:
        db.add(
            models.AuditLog(
                action="api_key.scope_violation",
                entity_type="api_key",
                entity_id=key_record.id,
                user_id=key_record.user_id,
                endpoint=path,
                method=method,
                status_code=status.HTTP_403_FORBIDDEN if enforced else None,
                details=json.dumps(
                    {
                        "key_prefix": key_record.key_prefix,
                        "method": method,
                        "path": path,
                        "required": required,
                        "granted": granted,
                        "enforced": enforced,
                    }
                ),
            )
        )
        db.commit()
    except Exception:  # pragma: no cover — defensive
        db.rollback()
        logger.exception("Failed to record API key scope violation")


def enforce_api_key_scope(
    db: Session,
    key_record: models.ApiKey,
    method: str,
    path: str,
) -> None:
    """Gate a request authenticated by an API key on the key's scopes.

    Raises 403 when the key is too narrow *and* enforcement is on. In warn mode
    the violation is recorded and the request proceeds, so that a live
    integration is observed before it is broken.

    This restricts; it never elevates. Role-based access control runs afterwards
    unchanged, so the effective permission is scope ∩ role.
    """
    required = scope_required(method, path)
    granted = _granted_scopes(key_record)
    if satisfies(granted, required):
        return

    enforced = api_key_scopes_enforced()
    logger.warning(
        "API key %s lacks scope '%s' for %s %s (grants: %s)%s",
        key_record.key_prefix,
        required,
        method,
        path,
        granted or "none",
        "" if enforced else " — warn mode, allowing",
    )
    _record_scope_violation(db, key_record, method, path, required, granted, enforced)

    if enforced:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"API key scope '{required}' is required for this operation; "
                f"this key grants {granted or 'no scopes'}."
            ),
        )


# ── Dependencies ─────────────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """
    Accepts either:
      - A JWT Bearer token (standard login flow), OR
      - A UKIP API key (starts with 'ukip_') for programmatic access.
    Returns the corresponding active User from the DB.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # ── API Key path ──────────────────────────────────────────────────────────
    if token.startswith("ukip_"):
        from backend.routers.api_keys import verify_api_key
        key_record = verify_api_key(token, db)
        if not key_record:
            raise credentials_exc
        user = db.query(models.User).filter(
            models.User.id == key_record.user_id,
            models.User.is_active == True,  # noqa: E712
        ).first()
        if not user:
            raise credentials_exc
        enforce_api_key_scope(
            db, key_record, request.method, _route_template(request)
        )
        return user

    # ── JWT path ──────────────────────────────────────────────────────────────
    try:
        payload = _decode_token(token)
        username: Optional[str] = payload.get("sub")
        if not username:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = (
        db.query(models.User)
        .filter(models.User.username == username, models.User.is_active == True)
        .first()
    )
    if not user:
        raise credentials_exc
    return user


async def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """
    Best-effort auth resolver for routes that may be publicly readable.
    Invalid, expired, or missing credentials are treated as anonymous access.

    An *insufficient scope* is not treated as anonymous: a caller who presented
    a real credential that is too narrow gets a 403, not a silent downgrade that
    would hide the reason their data looks empty.
    """
    if not token:
        return None

    if token.startswith("ukip_"):
        from backend.routers.api_keys import verify_api_key
        key_record = verify_api_key(token, db)
        if not key_record:
            return None
        user = db.query(models.User).filter(
            models.User.id == key_record.user_id,
            models.User.is_active == True,  # noqa: E712
        ).first()
        if user:
            enforce_api_key_scope(
                db, key_record, request.method, _route_template(request)
            )
        return user

    try:
        payload = _decode_token(token)
        username: Optional[str] = payload.get("sub")
        if not username:
            return None
    except JWTError:
        return None

    return (
        db.query(models.User)
        .filter(models.User.username == username, models.User.is_active == True)
        .first()
    )


def require_role(*roles: str):
    """
    Dependency factory that enforces role-based access.

    Usage:
        _: models.User = Depends(require_role("super_admin", "admin"))
    """
    def _checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' is not authorized for this action",
            )
        return current_user
    return _checker
