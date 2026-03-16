"""
Authentication and user management endpoints.
  POST /auth/token
  GET/POST/GET{id}/PUT/DELETE /users
  GET/POST /users/me  /users/me/password
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
import os

from backend import models, schemas
from backend.auth import authenticate_user, create_access_token, create_refresh_token, get_current_user, require_role, SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
from backend.database import get_db
from backend.routers.limiter import limiter

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
    token = create_access_token(subject=user.username, role=user.role)
    refresh_token = create_refresh_token(subject=user.username, role=user.role)
    return {"access_token": token, "refresh_token": refresh_token, "token_type": "bearer"}


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="The valid refresh JWT token")


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
        token_payload = jwt.decode(payload.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        username = token_payload.get("sub")
        token_type = token_payload.get("type")
        if not username or token_type != "refresh":
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = db.query(models.User).filter(
        models.User.username == username,
        models.User.is_active == True,
    ).first()
    if not user:
        raise credentials_exc

    new_access = create_access_token(subject=user.username, role=user.role)
    new_refresh = create_refresh_token(subject=user.username, role=user.role)

    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}


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
async def sso_login(request: Request):
    """Initiates the OAuth2 / OIDC login flow."""
    redirect_uri = str(request.url_for('sso_callback'))
    return await oauth.sso.authorize_redirect(request, redirect_uri)

@router.get("/sso/callback", tags=["sso"])
async def sso_callback(request: Request, db: Session = Depends(get_db)):
    """OAuth2 callback handler."""
    try:
        token = await oauth.sso.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SSO authentication failed: {e}")

    user_info = token.get('userinfo')
    if not user_info:
        user_info = await oauth.sso.userinfo(token=token)
        
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to fetch user info from SSO provider")

    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="SSO provider did not return an email address")

    # Find or create user
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        # Auto-provision a viewer account
        import uuid
        from backend.auth import hash_password
        dummy_pass = str(uuid.uuid4())
        
        user = models.User(
            username=email.split("@")[0] + "_" + str(uuid.uuid4())[:6],
            email=email,
            password_hash=hash_password(dummy_pass),
            role="viewer",
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
    access_token = create_access_token(subject=user.username, role=user.role)
    refresh_token = create_refresh_token(subject=user.username, role=user.role)
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
    from backend.auth import hash_password as _hp, verify_password
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
    from sqlalchemy import func
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


@router.get("/users", response_model=List[schemas.UserResponse], tags=["users"])
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin")),
):
    """List all users. Requires super_admin."""
    return db.query(models.User).offset(skip).limit(limit).all()


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
