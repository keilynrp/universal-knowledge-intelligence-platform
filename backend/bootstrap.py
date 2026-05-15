import logging
import os

from sqlalchemy.orm import Session

from backend import models
from backend.auth import hash_password, verify_password

logger = logging.getLogger(__name__)


def resolve_bootstrap_password_hash() -> str | None:
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if password:
        return hash_password(password)

    password_hash = os.environ.get("ADMIN_PASSWORD_HASH", "").strip()
    if password_hash:
        # Allow docker-compose escaped bcrypt hashes (`$$2b$$...`) to work in local
        # Python processes as well as in Compose-expanded environments.
        return password_hash.replace("$$", "$")

    return None


def ensure_bootstrap_super_admin(db: Session) -> None:
    bootstrap_username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
    bootstrap_hash = resolve_bootstrap_password_hash()

    if not bootstrap_hash:
        logger.warning(
            "Bootstrap skipped: neither ADMIN_PASSWORD nor ADMIN_PASSWORD_HASH is configured for '%s'",
            bootstrap_username,
        )
        return

    existing_super_admin = (
        db.query(models.User)
        .filter(models.User.role == "super_admin", models.User.is_active == True)  # noqa: E712
        .first()
    )
    bootstrap_user = (
        db.query(models.User)
        .filter(models.User.username == bootstrap_username)
        .first()
    )

    if bootstrap_user:
        # Always sync: role, active status, password hash, and unlock account
        changed = False
        if bootstrap_user.role != "super_admin":
            bootstrap_user.role = "super_admin"
            changed = True
        if not bootstrap_user.is_active:
            bootstrap_user.is_active = True
            changed = True
        if bootstrap_user.failed_attempts:
            bootstrap_user.failed_attempts = 0
            changed = True
        if bootstrap_user.locked_until:
            bootstrap_user.locked_until = None
            changed = True

        # Sync password from env var on every startup
        plain_password = os.environ.get("ADMIN_PASSWORD", "").strip()
        if plain_password and not verify_password(plain_password, bootstrap_user.password_hash):
            bootstrap_user.password_hash = bootstrap_hash
            changed = True
            logger.info("Bootstrap: password synced from env for '%s'", bootstrap_username)
        elif not plain_password and os.environ.get("ADMIN_PASSWORD_HASH", "").strip():
            # Using ADMIN_PASSWORD_HASH directly — always overwrite
            bootstrap_user.password_hash = bootstrap_hash
            changed = True
            logger.info("Bootstrap: password hash synced from env for '%s'", bootstrap_username)

        if changed:
            db.commit()
            logger.info("Bootstrap: super_admin '%s' synced", bootstrap_username)
        return

    if existing_super_admin is None:
        db.add(models.User(
            username=bootstrap_username,
            password_hash=bootstrap_hash,
            role="super_admin",
            is_active=True,
        ))
        db.commit()
        logger.info("Bootstrap: super_admin '%s' created", bootstrap_username)
