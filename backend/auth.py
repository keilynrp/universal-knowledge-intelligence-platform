"""
JWT Authentication module for UKIP.
Multi-user RBAC model: credentials stored in the 'users' table.
Roles: super_admin | admin | editor | viewer
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

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

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


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


# ── Dependencies ─────────────────────────────────────────────────────────────

async def get_current_user(
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
        return user

    # ── JWT path ──────────────────────────────────────────────────────────────
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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
