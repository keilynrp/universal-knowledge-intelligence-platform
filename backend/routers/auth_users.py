"""
Authentication and user management endpoints.
  POST /auth/token
  GET/POST/GET{id}/PUT/DELETE /users
  GET/POST /users/me  /users/me/password
"""

# ruff: noqa: B008 — every endpoint below uses FastAPI's own recommended
# `Depends(...)`/`Query(...)` dependency-injection idiom in an argument default,
# which is exactly what B008 ("no function call as a default") exists to catch
# in ordinary code. Same justification, and same file-level waiver, as
# backend/routers/backup_ops.py.
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse

from backend import models, schemas
from backend.auth import (
    REFRESH_TOKEN_EXPIRE_MINUTES,
    _decode_token,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    issue_tokens,
    require_role,
)
from backend.database import get_db
from backend.i18n.catalog import translate
from backend.i18n.locale import language_dependency
from backend.notifications.email_sender import send_plain_email
from backend.routers.limiter import limiter
from backend.routers.platform_auth_settings import (
    get_or_create_auth_settings,
    sso_provider_configured,
)

router = APIRouter(tags=["auth"])


# ── Authentication ────────────────────────────────────────────────────────────

@router.post("/auth/token", tags=["auth"])
@limiter.limit("60/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Obtain a Bearer token. Credentials are managed in the users table.
    Rate-limited to 5 attempts per minute per IP.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return issue_tokens(db, user, request)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="The valid refresh JWT token")


class PasswordResetRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., min_length=32, max_length=256)
    new_password: str = Field(..., min_length=8, max_length=128)


def _password_reset_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _reset_link(request: Request, token: str) -> str:
    frontend_url = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if not frontend_url:
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "https")
        if forwarded_host:
            frontend_url = f"{forwarded_proto}://{forwarded_host}"
        else:
            frontend_url = str(request.base_url).rstrip("/")
    return f"{frontend_url}/login?reset_token={token}"


@router.post("/auth/refresh", tags=["auth"])
@limiter.limit("20/minute")
def refresh_token(request: Request, payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    """
    Exchange a valid refresh_token for a fresh access_token & refresh_token pair.
    """
    credentials_exc = HTTPException(
        status_code=401,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token_payload = _decode_token(payload.refresh_token)
        username = token_payload.get("sub")
        token_type = token_payload.get("type")
        sid = token_payload.get("sid")
        if not username or token_type != "refresh" or not sid:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.query(models.User).filter(
        models.User.username == username,
        models.User.is_active == True,
    ).first()
    if not user:
        raise credentials_exc

    session = (
        db.query(models.UserSession)
        .filter(
            models.UserSession.sid == sid,
            models.UserSession.user_id == user.id,
            models.UserSession.revoked_at.is_(None),
        )
        .first()
    )
    if not session:
        raise credentials_exc

    # The refreshed pair keeps the same session: a refresh renews credentials,
    # it does not start a new login. A revoked session therefore cannot be
    # renewed back to life.
    session.last_seen_at = datetime.now(timezone.utc)
    session.expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=REFRESH_TOKEN_EXPIRE_MINUTES
    )
    db.commit()

    return {
        "access_token": create_access_token(user.username, user.role, session.sid),
        "refresh_token": create_refresh_token(user.username, user.role, session.sid),
        "token_type": "bearer",
    }


# ── Sessions (#368 phase C.3) ────────────────────────────────────────────────
#
# Revoking a session is the proportionate containment step the 2026-09-22
# tabletop found missing: it stops one stolen token without deactivating the
# account and without rotating the signing key, and it works on the operator's
# own account, which `PUT`/`DELETE /users/{id}` refuse to deactivate.

def _current_sid(request: Request):
    """The session of the caller, so a listing can mark it and a bulk revoke
    can spare it."""
    header = request.headers.get("authorization") or ""
    if not header.startswith("Bearer "):
        return None
    try:
        return _decode_token(header.split(" ", 1)[1]).get("sid")
    except JWTError:
        return None


def _serialize_session(row: models.UserSession, current_sid) -> dict:
    return {
        "id": row.id,
        "sid": row.sid,
        "created_at": row.created_at,
        "last_seen_at": row.last_seen_at,
        "expires_at": row.expires_at,
        "user_agent": row.user_agent,
        "ip_address": row.ip_address,
        "current": row.sid == current_sid,
    }


def _live_sessions(db: Session, user_id: int):
    return (
        db.query(models.UserSession)
        .filter(
            models.UserSession.user_id == user_id,
            models.UserSession.revoked_at.is_(None),
        )
        .order_by(models.UserSession.last_seen_at.desc())
        .all()
    )


def _revoke(db: Session, rows, actor_id: int) -> int:
    now = datetime.now(timezone.utc)
    for row in rows:
        row.revoked_at = now
        row.revoked_by_user_id = actor_id
    db.commit()
    return len(rows)


@router.get("/auth/sessions", tags=["auth"])
def list_my_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The caller's live sessions, most recently seen first."""
    current = _current_sid(request)
    return {
        "items": [
            _serialize_session(row, current)
            for row in _live_sessions(db, current_user.id)
        ]
    }


@router.delete("/auth/sessions/{session_id}", tags=["auth"])
def revoke_my_session(
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Revoke one of the caller's own sessions.

    A session that is not the caller's is reported as not found rather than
    forbidden: whether someone else holds a given session id is not the
    caller's business.
    """
    row = (
        db.query(models.UserSession)
        .filter(
            models.UserSession.id == session_id,
            models.UserSession.user_id == current_user.id,
            models.UserSession.revoked_at.is_(None),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    _revoke(db, [row], current_user.id)
    return {"revoked": 1, "id": session_id}


@router.delete("/auth/sessions", tags=["auth"])
def revoke_my_other_sessions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Revoke every session of the caller except the one making the call."""
    current = _current_sid(request)
    rows = [row for row in _live_sessions(db, current_user.id) if row.sid != current]
    return {"revoked": _revoke(db, rows, current_user.id)}


@router.get("/users/{user_id}/sessions", tags=["users"])
def list_user_sessions(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin")),
):
    """Another user's live sessions. Requires super_admin."""
    if not db.query(models.User).filter(models.User.id == user_id).first():
        raise HTTPException(status_code=404, detail="User not found")
    return {"items": [_serialize_session(row, None) for row in _live_sessions(db, user_id)]}


@router.delete("/users/{user_id}/sessions/{session_id}", tags=["users"])
def revoke_user_session(
    user_id: int = Path(..., ge=1),
    session_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin")),
):
    """Revoke one session belonging to another user. Requires super_admin.

    Unlike deactivation there is no last-super_admin guard, and none is wanted:
    this removes a credential, not a person, and the account keeps working from
    its other sessions.
    """
    row = (
        db.query(models.UserSession)
        .filter(
            models.UserSession.id == session_id,
            models.UserSession.user_id == user_id,
            models.UserSession.revoked_at.is_(None),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    _revoke(db, [row], current_user.id)
    return {"revoked": 1, "id": session_id}


@router.delete("/users/{user_id}/sessions", tags=["users"])
def revoke_all_user_sessions(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin")),
):
    """Revoke every live session of a user, without deactivating the account."""
    return {"revoked": _revoke(db, _live_sessions(db, user_id), current_user.id)}


@router.post("/auth/password-reset/request", tags=["auth"])
@limiter.limit("10/hour")
def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    db: Session = Depends(get_db),
    language: str = Depends(language_dependency),
):
    """Request a password reset email if SMTP and the account are available."""
    neutral_response = {
        "sent": True,
        "detail": "If the account exists and email delivery is configured, a reset link will be sent.",
    }
    email = payload.email.strip().lower()
    smtp_settings = db.get(models.NotificationSettings, 1)
    if not smtp_settings or not smtp_settings.enabled or not smtp_settings.smtp_host:
        return {**neutral_response, "sent": False, "reason": "smtp_not_configured"}

    user = (
        db.query(models.User)
        .filter(func.lower(models.User.email) == email, models.User.is_active == True)
        .first()
    )
    if not user:
        return neutral_response

    raw_token = secrets.token_urlsafe(48)
    token = models.PasswordResetToken(
        user_id=user.id,
        token_hash=_password_reset_token_hash(raw_token),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(token)
    db.commit()

    platform_name = os.environ.get("PLATFORM_NAME", "UKIP")
    link = _reset_link(request, raw_token)
    sent = send_plain_email(
        smtp_settings,
        email,
        subject=translate("email.password_reset.subject", language, platform=platform_name),
        body=translate("email.password_reset.body", language, link=link),
    )
    if not sent:
        return {**neutral_response, "sent": False, "reason": "email_not_sent"}
    return neutral_response


@router.post("/auth/password-reset/confirm", tags=["auth"])
@limiter.limit("20/hour")
def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Consume a valid password reset token and update the user's password."""
    token_hash = _password_reset_token_hash(payload.token)
    reset_token = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.token_hash == token_hash)
        .first()
    )
    now = datetime.now(timezone.utc)
    if not reset_token or reset_token.used_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = db.get(models.User, reset_token.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.password_hash = hash_password(payload.new_password)
    user.failed_attempts = 0
    user.locked_until = None
    reset_token.used_at = now
    db.commit()
    return {"reset": True}


# ── SSO Integration (Sprint 65) ───────────────────────────────────────────────

oauth = OAuth()
oauth.register(
    name='sso',
    client_id=os.environ.get('SSO_CLIENT_ID', ''),
    client_secret=os.environ.get('SSO_CLIENT_SECRET', ''),
    server_metadata_url=os.environ.get('SSO_METADATA_URL', 'https://accounts.google.com/.well-known/openid-configuration'),
    client_kwargs={'scope': 'openid email profile'}
)

@router.get("/sso/login", tags=["sso"])
async def sso_login(request: Request, db: Session = Depends(get_db)):
    """Initiates the OAuth2 / OIDC login flow."""
    settings = get_or_create_auth_settings(db)
    if not settings.sso_enabled:
        raise HTTPException(status_code=404, detail="SSO is disabled")
    if not sso_provider_configured():
        raise HTTPException(status_code=503, detail="SSO provider is not configured")
    redirect_uri = str(request.url_for('sso_callback'))
    return await oauth.sso.authorize_redirect(request, redirect_uri)

@router.get("/sso/callback", tags=["sso"])
async def sso_callback(request: Request, db: Session = Depends(get_db)):
    """OAuth2 callback handler."""
    try:
        token = await oauth.sso.authorize_access_token(request)
    except Exception as e:  # noqa: BLE001 — authlib and its HTTP client raise many types; any of them is a failed SSO login
        raise HTTPException(status_code=400, detail=f"SSO authentication failed: {e}")

    user_info = token.get('userinfo')
    if not user_info:
        user_info = await oauth.sso.userinfo(token=token)
        
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to fetch user info from SSO provider")

    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="SSO provider did not return an email address")

    settings = get_or_create_auth_settings(db)
    if not settings.sso_enabled:
        raise HTTPException(status_code=404, detail="SSO is disabled")

    allowed_domains = [
        domain.strip().lower().lstrip("@")
        for domain in (settings.sso_allowed_domains or "").split(",")
        if domain.strip()
    ]
    email_domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    if allowed_domains and email_domain not in allowed_domains:
        raise HTTPException(status_code=403, detail="Email domain is not allowed for SSO")

    # Find or create user
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        if not settings.sso_auto_provision:
            raise HTTPException(status_code=403, detail="SSO user auto-provisioning is disabled")
        # Auto-provision a viewer account
        import uuid

        from backend.auth import hash_password
        dummy_pass = str(uuid.uuid4())
        
        user = models.User(
            username=email.split("@")[0] + "_" + str(uuid.uuid4())[:6],
            email=email,
            password_hash=hash_password(dummy_pass),
            role=settings.sso_default_role or "viewer",
            display_name=user_info.get("name"),
            avatar_url=user_info.get("picture"),
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Generate JWT
    _sso_tokens = issue_tokens(db, user, request)
    access_token = _sso_tokens["access_token"]
    refresh_token = _sso_tokens["refresh_token"]
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(url=f"{frontend_url}/login?token={access_token}&refresh={refresh_token}")


# ── User Management (RBAC) ────────────────────────────────────────────────────

@router.get("/users/me", response_model=schemas.UserResponse, tags=["users"])
def get_my_profile(current_user: models.User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return current_user


@router.patch("/users/me/profile", response_model=schemas.UserResponse, tags=["users"])
def update_my_profile(
    payload: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update the current user's email, display name, and/or bio."""
    update_data = payload.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"] is not None:
        conflict = db.query(models.User).filter(
            models.User.email == update_data["email"],
            models.User.id != current_user.id,
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Email already in use")
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/users/me/password", tags=["users"])
@limiter.limit("60/minute")
def change_my_password(
    request: Request,
    payload: schemas.PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Change the authenticated user's own password."""
    from backend.auth import hash_password as _hp
    from backend.auth import verify_password
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = _hp(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


# ── Sprint 58: User Avatar ────────────────────────────────────────────────────

class AvatarPayload(BaseModel):
    avatar_url: str = Field(max_length=300_000)  # base64 data URL ~200KB image


@router.post("/users/me/avatar", response_model=schemas.UserResponse, tags=["users"])
def upload_my_avatar(
    payload: AvatarPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Upload or replace the current user's avatar (base64 data URL)."""
    if not payload.avatar_url.startswith("data:image/"):
        raise HTTPException(status_code=422, detail="avatar_url must be a data:image/ URL")
    current_user.avatar_url = payload.avatar_url
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/users/me/avatar", response_model=schemas.UserResponse, tags=["users"])
def delete_my_avatar(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Remove the current user's avatar."""
    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/users/stats", tags=["users"])
def user_stats(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin")),
):
    """Return user count statistics. Requires super_admin."""
    all_users = db.query(models.User).all()
    by_role: dict[str, int] = {}
    for u in all_users:
        by_role[u.role] = by_role.get(u.role, 0) + 1
    active   = sum(1 for u in all_users if u.is_active)
    inactive = sum(1 for u in all_users if not u.is_active)
    return {
        "total":    len(all_users),
        "active":   active,
        "inactive": inactive,
        "by_role":  by_role,
    }


@router.get("/users", response_model=list[schemas.UserResponse], tags=["users"])
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin")),
):
    """List all users. Requires super_admin."""
    # Ordered by id: LIMIT/OFFSET with no ORDER BY has no defined window.
    # PostgreSQL may return rows in physical heap order, which shifts whenever a
    # row is updated or re-inserted, so a client paging through the list can see
    # one user twice and never see another. Kept out of the docstring because
    # FastAPI publishes that as the endpoint description in the OpenAPI contract.
    return db.query(models.User).order_by(models.User.id).offset(skip).limit(limit).all()


@router.post("/users", response_model=schemas.UserResponse, status_code=201, tags=["users"])
@limiter.limit("100/hour")
def create_user(
    request: Request,
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin")),
):
    """Create a new user. Requires super_admin."""
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    from backend.auth import hash_password as _hash_pw
    new_user = models.User(
        username=payload.username,
        email=payload.email,
        password_hash=_hash_pw(payload.password),
        role=payload.role.value,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/users/{user_id}", response_model=schemas.UserResponse, tags=["users"])
def get_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin")),
):
    """Get a user by ID. Requires super_admin."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=schemas.UserResponse, tags=["users"])
def update_user(
    user_id: int = Path(..., ge=1),
    payload: schemas.UserUpdate = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin")),
):
    """Update a user's email, password, role, or active status. Requires super_admin."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Prevent self-role change
    if user.id == current_user.id and payload.role is not None and payload.role.value != current_user.role:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    # Prevent deactivating self
    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    # Ensure at least one super_admin remains active
    if payload.role is not None and user.role == "super_admin" and payload.role.value != "super_admin":
        active_superadmins = db.query(models.User).filter(
            models.User.role == "super_admin", models.User.is_active == True
        ).count()
        if active_superadmins <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last active super_admin")

    update_data = payload.model_dump(exclude_unset=True)
    if "password" in update_data:
        from backend.auth import hash_password as _hash_pw
        update_data["password_hash"] = _hash_pw(update_data.pop("password"))
    if "role" in update_data:
        update_data["role"] = (
            update_data["role"].value
            if hasattr(update_data["role"], "value")
            else update_data["role"]
        )

    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", tags=["users"])
def delete_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin")),
):
    """Soft-delete (deactivate) a user. Requires super_admin."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    # Ensure at least one super_admin remains active
    if user.role == "super_admin":
        active_superadmins = db.query(models.User).filter(
            models.User.role == "super_admin", models.User.is_active == True
        ).count()
        if active_superadmins <= 1:
            raise HTTPException(status_code=400, detail="Cannot deactivate the last active super_admin")
    user.is_active = False
    db.commit()
    return {"message": "User deactivated", "id": user_id}


@router.post("/users/{user_id}/activate", response_model=schemas.UserResponse, tags=["users"])
def activate_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin")),
):
    """Reactivate a deactivated user. Requires super_admin."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user
