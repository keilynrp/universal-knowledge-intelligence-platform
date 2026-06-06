"""
Symmetric encryption for sensitive credentials stored in the database.
Uses Fernet (AES-128-CBC + HMAC-SHA256), wrapped in MultiFernet to support
staged key rotation.

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Env:
    ENCRYPTION_KEY            — primary key (used to encrypt; first to decrypt).
    ENCRYPTION_KEYS_RETIRING  — optional, comma-separated retiring keys (decrypt-only).

Without ENCRYPTION_KEY, values are stored in plaintext (acceptable for local dev,
NOT for production).
"""
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_primary_fernet = None   # cryptography.fernet.Fernet | None
_multi_fernet = None     # cryptography.fernet.MultiFernet | None


def _parse_keys(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _build_fernets():
    """Build the primary Fernet and the MultiFernet (primary + retiring).

    Fail-soft: a malformed key is skipped with a warning rather than raising,
    so a bad retiring key can never crash app boot.
    """
    from cryptography.fernet import Fernet, MultiFernet

    primary_raw = os.environ.get("ENCRYPTION_KEY")
    retiring_raw = os.environ.get("ENCRYPTION_KEYS_RETIRING")

    if not primary_raw:
        logger.warning(
            "ENCRYPTION_KEY not set — credentials stored in plaintext. "
            "Set ENCRYPTION_KEY in production."
        )
        return None, None

    try:
        primary = Fernet(primary_raw.encode())
    except Exception:
        logger.warning(
            "ENCRYPTION_KEY is set but invalid (must be URL-safe base64 32-byte key). "
            "Credentials will be stored in PLAINTEXT."
        )
        return None, None

    fernets = [primary]
    for key in _parse_keys(retiring_raw):
        try:
            fernets.append(Fernet(key.encode()))
        except Exception:
            logger.warning(
                "Skipping a malformed entry in ENCRYPTION_KEYS_RETIRING "
                "(must be URL-safe base64 32-byte key)."
            )
    return primary, MultiFernet(fernets)


_primary_fernet, _multi_fernet = _build_fernets()


def has_primary_key() -> bool:
    """True iff a valid primary encryption key is configured."""
    return _primary_fernet is not None


def encrypt(value: Optional[str]) -> Optional[str]:
    """Encrypt a plaintext string with the primary key. No-op if no key configured."""
    if not _multi_fernet or not value:
        return value
    return _multi_fernet.encrypt(value.encode()).decode()


def decrypt(value: Optional[str]) -> Optional[str]:
    """Decrypt a token using the primary + retiring keys.

    Falls back to returning the value as-is to handle legacy plaintext during
    migration.
    """
    if not _multi_fernet or not value:
        return value
    from cryptography.fernet import InvalidToken
    try:
        return _multi_fernet.decrypt(value.encode()).decode()
    except InvalidToken:
        logger.warning(
            "decrypt(): InvalidToken — value appears to be plaintext (legacy migration). "
            "Re-save this record to encrypt it."
        )
        return value
    except Exception as e:
        logger.error("decrypt(): unexpected error: %s — returning value as-is", e)
        return value


def is_encrypted_with_primary(value: Optional[str]) -> bool:
    """True iff ``value`` decrypts under the primary key alone.

    Used by the re-encrypt walk to skip values already on the primary key, which
    is what makes re-encryption idempotent (MultiFernet.rotate re-encrypts every
    value unconditionally).
    """
    if not _primary_fernet or not value:
        return False
    try:
        _primary_fernet.decrypt(value.encode())
        return True
    except Exception:
        return False


def key_fingerprint(key: Optional[str]) -> Optional[str]:
    """Return a non-reversible fingerprint of a key for evidence/logging.

    Never returns or logs the raw key.
    """
    if not key:
        return None
    digest = hashlib.sha256(key.encode()).hexdigest()
    return f"sha256:{digest[:12]}"
