# EPIC-017: Secrets & Credential Rotation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add zero-downtime staged dual-key rotation for `ENCRYPTION_KEY` and `JWT_SECRET_KEY`, a verifiable rotation-evidence trail, an ops health check, and an operational runbook — closing the last open P0 readiness gap (`secrets_rotation`).

**Architecture:** `encryption.py` becomes `MultiFernet`-backed (encrypt with primary, decrypt with primary + retiring keys). `auth.py` gains a shared `_decode_token` that verifies against primary + retiring JWT keys. An eager, advisory-locked ops script re-encrypts DB ciphertext onto the primary key and writes a `secret_rotation_events` row. An `_secrets_check()` surfaces insecure defaults and stale rotations through the existing `/ops/checks` fan-out. Each slice is independently mergeable and **inert** until an operator configures retiring keys.

**Tech Stack:** Python 3.11/3.12, FastAPI, SQLAlchemy, Alembic, `cryptography` (Fernet/MultiFernet), `python-jose` (JWT HS256), pytest.

**Spec:** `docs/superpowers/specs/2026-06-05-epic017-secrets-rotation-design.md`

**Conventions for every task:**
- Run tests with `.venv/Scripts/python -m pytest` (Windows venv).
- Tests live in `backend/tests/`. The suite sets `UKIP_SKIP_STARTUP_SIDE_EFFECTS=1` and uses an in-memory SQLite `StaticPool` (`backend/tests/conftest.py`).
- Commit after each green step. Conventional-commit messages, no attribution footer.
- DRY, YAGNI, TDD (RED → GREEN → refactor).

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/encryption.py` (modify) | MultiFernet crypto: `encrypt`, `decrypt`, `is_encrypted_with_primary`, `key_fingerprint`, fail-soft key parsing, `has_primary_key()` |
| `backend/auth.py` (modify) | `_decode_token` multi-key JWT verify; retiring-key parsing; route all decode sites through it |
| `backend/audit.py`, `backend/routers/auth_users.py`, `backend/routers/ws.py` (modify) | Replace local `jwt.decode` calls with `auth._decode_token` |
| `backend/secret_rotation.py` (create) | Canonical constant `SECRET_ROTATION_MAX_AGE_DAYS`, encrypted-column registry, `record_rotation_event`, `last_rotation_at`, retiring-key presence helpers |
| `backend/models.py` (modify) | `SecretRotationEvent` model |
| `alembic/versions/e5f6a7b8c0d1_secret_rotation_events.py` (create) | Evidence table migration (idempotent create + documented destructive downgrade) |
| `backend/scripts/__init__.py`, `backend/scripts/rotate_encryption.py` (create) | Advisory-locked eager re-encrypt CLI (`python -m backend.scripts.rotate_encryption`) |
| `backend/ops_checks.py` (modify) | `_secrets_check()` + wiring + recommended actions |
| `docs/operating/SECRETS_ROTATION_RUNBOOK.md` (create) | Cadence, ownership, per-secret staged rollover, evidence verification |
| `backend/enterprise_readiness.py` (modify) | Move `secrets_rotation` → `RESOLVED_GAPS` |
| `backend/tests/test_epic017_*.py` (create) | One test module per slice |

---

## Slice 1 — MultiFernet crypto core

Branch: `feat/epic017-slice1-multifernet`

### Task 1: Fail-soft multi-key parsing + MultiFernet build

**Files:**
- Modify: `backend/encryption.py`
- Test: `backend/tests/test_epic017_encryption.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_epic017_encryption.py
import importlib

from cryptography.fernet import Fernet


def _reload_encryption(monkeypatch, primary=None, retiring=None):
    if primary is None:
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    else:
        monkeypatch.setenv("ENCRYPTION_KEY", primary)
    if retiring is None:
        monkeypatch.delenv("ENCRYPTION_KEYS_RETIRING", raising=False)
    else:
        monkeypatch.setenv("ENCRYPTION_KEYS_RETIRING", retiring)
    import backend.encryption as enc
    return importlib.reload(enc)


def test_decrypts_value_from_retiring_key(monkeypatch):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    enc_old = _reload_encryption(monkeypatch, primary=old)
    token = enc_old.encrypt("secret-value")
    # Rotate: new primary, old becomes retiring
    enc_new = _reload_encryption(monkeypatch, primary=new, retiring=old)
    assert enc_new.decrypt(token) == "secret-value"


def test_malformed_retiring_key_is_skipped_not_raised(monkeypatch):
    primary = Fernet.generate_key().decode()
    # Must not raise on import/reload
    enc = _reload_encryption(monkeypatch, primary=primary, retiring="not-a-valid-key")
    assert enc.encrypt("x") and enc.decrypt(enc.encrypt("x")) == "x"


def test_is_encrypted_with_primary(monkeypatch):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()
    enc_old = _reload_encryption(monkeypatch, primary=old)
    token_old = enc_old.encrypt("v")
    enc_new = _reload_encryption(monkeypatch, primary=new, retiring=old)
    token_new = enc_new.encrypt("v")
    assert enc_new.is_encrypted_with_primary(token_new) is True
    assert enc_new.is_encrypted_with_primary(token_old) is False


def test_key_fingerprint_is_truncated_and_never_raw(monkeypatch):
    key = Fernet.generate_key().decode()
    enc = _reload_encryption(monkeypatch, primary=key)
    fp = enc.key_fingerprint(key)
    assert fp.startswith("sha256:")
    assert key not in fp
    assert len(fp) <= len("sha256:") + 12
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest backend/tests/test_epic017_encryption.py -v`
Expected: FAIL (`is_encrypted_with_primary` / `key_fingerprint` not defined).

- [ ] **Step 3: Rewrite `backend/encryption.py`**

```python
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
    from cryptography.fernet import InvalidToken
    try:
        _primary_fernet.decrypt(value.encode())
        return True
    except (InvalidToken, Exception):
        return False


def key_fingerprint(key: Optional[str]) -> Optional[str]:
    """Return a non-reversible fingerprint of a key for evidence/logging.

    Never returns or logs the raw key.
    """
    if not key:
        return None
    digest = hashlib.sha256(key.encode()).hexdigest()
    return f"sha256:{digest[:12]}"
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_epic017_encryption.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Regression — existing encryption + auth tests stay green**

Run: `.venv/Scripts/python -m pytest backend/tests/test_encryption.py -v`
Expected: PASS (inert behavior preserved with single key).

- [ ] **Step 6: Commit**

```bash
git add backend/encryption.py backend/tests/test_epic017_encryption.py
git commit -m "feat: EPIC-017 Slice 1 — MultiFernet crypto core with staged key rotation"
```

### Task 2: Open Slice 1 PR

- [ ] **Step 1:** Push branch and open PR with `gh pr create`, base `main`. Use the `gh` credential helper for push if Git Credential Manager hangs: `git -c credential.helper='!gh auth git-credential' push -u origin HEAD`.
- [ ] **Step 2:** Confirm CI green, then squash-merge `--delete-branch`.

---

## Slice 2 — JWT multi-key verify

Branch: `feat/epic017-slice2-jwt-multikey` (from fresh `main`)

### Task 3: `_decode_token` helper + retiring keys

**Files:**
- Modify: `backend/auth.py`
- Test: `backend/tests/test_epic017_jwt.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_epic017_jwt.py
import importlib
from datetime import timedelta

import pytest
from jose import jwt


def _reload_auth(monkeypatch, primary, retiring=None):
    monkeypatch.setenv("JWT_SECRET_KEY", primary)
    if retiring is None:
        monkeypatch.delenv("JWT_SECRET_KEYS_RETIRING", raising=False)
    else:
        monkeypatch.setenv("JWT_SECRET_KEYS_RETIRING", retiring)
    import backend.auth as auth
    return importlib.reload(auth)


def test_token_signed_with_retiring_key_still_verifies(monkeypatch):
    old = "old-secret-key-0123456789"
    new = "new-secret-key-9876543210"
    auth_old = _reload_auth(monkeypatch, primary=old)
    token = auth_old.create_access_token("alice", "admin")
    auth_new = _reload_auth(monkeypatch, primary=new, retiring=old)
    payload = auth_new._decode_token(token)
    assert payload["sub"] == "alice"


def test_token_signed_with_unknown_key_is_rejected(monkeypatch):
    auth_new = _reload_auth(monkeypatch, primary="primary-key-aaa", retiring="retiring-key-bbb")
    forged = jwt.encode({"sub": "mallory"}, "unknown-key-zzz", algorithm="HS256")
    with pytest.raises(Exception):
        auth_new._decode_token(forged)


def test_signing_uses_primary_only(monkeypatch):
    new = "new-secret-key-9876543210"
    old = "old-secret-key-0123456789"
    auth_new = _reload_auth(monkeypatch, primary=new, retiring=old)
    token = auth_new.create_access_token("bob", "viewer")
    # Decodes under the primary directly
    assert jwt.decode(token, new, algorithms=["HS256"])["sub"] == "bob"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest backend/tests/test_epic017_jwt.py -v`
Expected: FAIL (`_decode_token` not defined).

- [ ] **Step 3: Edit `backend/auth.py`**

After the `SECRET_KEY` block (auth.py:24-34), add retiring-key parsing and the helper:

```python
def _parse_secret_keys(raw):  # raw: str | None
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


# Verify-only retiring JWT keys (decrypt grace window during rotation).
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
```

Then replace the two in-file decode sites:
- auth.py:159 `payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])` → `payload = _decode_token(token)`
- auth.py:198 (same) → `payload = _decode_token(token)`

Leave the `ukip_` API-key branches (auth.py:144-155, 187-195) untouched.

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_epic017_jwt.py backend/tests/test_auth.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/auth.py backend/tests/test_epic017_jwt.py
git commit -m "feat: EPIC-017 Slice 2 — JWT multi-key verify (_decode_token)"
```

### Task 4: Route the remaining decode sites through `_decode_token`

**Files:** Modify `backend/audit.py:95`, `backend/routers/auth_users.py:98`, `backend/routers/ws.py:66`.

- [ ] **Step 1:** In each file, replace `jwt.decode(<token>, SECRET_KEY, algorithms=[ALGORITHM])` with `from backend.auth import _decode_token` (top-level import) and `_decode_token(<token>)`. Keep surrounding `try/except JWTError` blocks. Confirm none remain on the single-key path:

Run: `.venv/Scripts/python -m pytest -q` then
`grep -rn "jwt.decode" backend --include=*.py | grep -v tests | grep -v "def _decode_token"`
Expected: only the call **inside** `_decode_token` remains.

- [ ] **Step 2:** Full suite green.

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS (no regressions; inert with no retiring keys).

- [ ] **Step 3: Commit + PR**

```bash
git add backend/audit.py backend/routers/auth_users.py backend/routers/ws.py
git commit -m "refactor: EPIC-017 route all JWT decode sites through _decode_token"
```
Then push + open PR, CI green, squash-merge `--delete-branch`.

---

## Slice 3 — Evidence table + re-encrypt script

Branch: `feat/epic017-slice3-reencrypt` (from fresh `main`)

### Task 5: `SecretRotationEvent` model + migration

**Files:**
- Modify: `backend/models.py` (append model)
- Create: `alembic/versions/e5f6a7b8c0d1_secret_rotation_events.py`
- Test: `backend/tests/test_epic017_rotation_evidence.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_epic017_rotation_evidence.py
from datetime import datetime, timezone

from backend import models


def test_secret_rotation_event_row_roundtrip(db_session):
    ev = models.SecretRotationEvent(
        secret_name="ENCRYPTION_KEY",
        rotated_at=datetime.now(timezone.utc),
        operator="ops-script",
        rows_reencrypted=7,
        old_key_fingerprint="sha256:abc123def456",
        new_key_fingerprint="sha256:0011223344ff",
        notes="test",
    )
    db_session.add(ev)
    db_session.commit()
    fetched = db_session.query(models.SecretRotationEvent).filter_by(
        secret_name="ENCRYPTION_KEY"
    ).one()
    assert fetched.rows_reencrypted == 7
    assert fetched.new_key_fingerprint.startswith("sha256:")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/Scripts/python -m pytest backend/tests/test_epic017_rotation_evidence.py -v`
Expected: FAIL (`SecretRotationEvent` undefined).

- [ ] **Step 3: Append model to `backend/models.py`** (end of file)

```python
class SecretRotationEvent(Base):
    """EPIC-017: append-only evidence that a secret was rotated.

    Source of truth for the secrets ops health check ("when was each secret last
    rotated"). Fingerprints are non-reversible SHA-256 truncations — never the
    raw key.
    """
    __tablename__ = "secret_rotation_events"

    id = Column(Integer, primary_key=True, index=True)
    secret_name = Column(String(60), nullable=False, index=True)   # ENCRYPTION_KEY | JWT_SECRET_KEY
    rotated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    operator = Column(String(120), nullable=False)
    rows_reencrypted = Column(Integer, nullable=True)
    old_key_fingerprint = Column(String(40), nullable=True)
    new_key_fingerprint = Column(String(40), nullable=True)
    notes = Column(Text, nullable=True)
```

(Confirm `Column, Integer, String, DateTime, Text` and `datetime, timezone` are already imported at the top of `models.py` — they are used by existing models.)

- [ ] **Step 4: Create migration** `alembic/versions/e5f6a7b8c0d1_secret_rotation_events.py`

```python
"""create secret_rotation_events table

EPIC-017: append-only evidence of secret/credential rotations. Idempotent
create. NOTE: downgrade DROPS the table and therefore DESTROYS all rotation
history — provided for schema reversibility only, never as a routine rollback.

Revision ID: e5f6a7b8c0d1
Revises: d4e5f6a7b8c0
Create Date: 2026-06-05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c0d1"
down_revision = "d4e5f6a7b8c0"
branch_labels = None
depends_on = None

_TABLE = "secret_rotation_events"


def _has_table(bind, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, _TABLE):
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("secret_name", sa.String(length=60), nullable=False),
        sa.Column("rotated_at", sa.DateTime(), nullable=False),
        sa.Column("operator", sa.String(length=120), nullable=False),
        sa.Column("rows_reencrypted", sa.Integer(), nullable=True),
        sa.Column("old_key_fingerprint", sa.String(length=40), nullable=True),
        sa.Column("new_key_fingerprint", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(f"ix_{_TABLE}_id", _TABLE, ["id"], unique=False)
    op.create_index(f"ix_{_TABLE}_secret_name", _TABLE, ["secret_name"], unique=False)


def downgrade() -> None:
    # WARNING: destroys all rotation evidence. Schema reversibility only.
    bind = op.get_bind()
    if not _has_table(bind, _TABLE):
        return
    op.drop_index(f"ix_{_TABLE}_secret_name", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_id", table_name=_TABLE)
    op.drop_table(_TABLE)
```

- [ ] **Step 5: Verify migration chains to head**

Run: `.venv/Scripts/python -m alembic heads`
Expected: `e5f6a7b8c0d1 (head)` (single head — no branch).

- [ ] **Step 6: Run tests + commit**

Run: `.venv/Scripts/python -m pytest backend/tests/test_epic017_rotation_evidence.py -v`
Expected: PASS.

```bash
git add backend/models.py alembic/versions/e5f6a7b8c0d1_secret_rotation_events.py backend/tests/test_epic017_rotation_evidence.py
git commit -m "feat: EPIC-017 Slice 3 — secret_rotation_events evidence table + migration"
```

### Task 6: `secret_rotation.py` helpers (registry, constant, evidence)

**Files:**
- Create: `backend/secret_rotation.py`
- Test: extend `backend/tests/test_epic017_rotation_evidence.py`

- [ ] **Step 1: Write failing tests**

```python
def test_last_rotation_at_returns_newest(db_session):
    from backend import secret_rotation as sr
    from datetime import datetime, timezone, timedelta
    older = models.SecretRotationEvent(secret_name="ENCRYPTION_KEY", operator="x",
        rotated_at=datetime.now(timezone.utc) - timedelta(days=10))
    newer = models.SecretRotationEvent(secret_name="ENCRYPTION_KEY", operator="x",
        rotated_at=datetime.now(timezone.utc))
    db_session.add_all([older, newer]); db_session.commit()
    assert sr.last_rotation_at(db_session, "ENCRYPTION_KEY") == newer.rotated_at


def test_encrypted_columns_registry_is_complete():
    from backend import secret_rotation as sr
    names = {(m.__name__, col) for m, col in sr.ENCRYPTED_COLUMNS}
    assert names == {
        ("AIIntegration", "api_key"),
        ("StoreConnection", "api_key"),
        ("StoreConnection", "api_secret"),
        ("StoreConnection", "access_token"),
    }
```

- [ ] **Step 2: Run to verify failure.** Expected: FAIL (module missing).

- [ ] **Step 3: Create `backend/secret_rotation.py`**

```python
"""EPIC-017 shared helpers for secret rotation: encrypted-column registry,
cadence constant, and evidence read/write. Imported by the re-encrypt ops
script and the secrets ops health check.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend import models

# Single canonical cadence source (days). Read once.
SECRET_ROTATION_MAX_AGE_DAYS = int(os.environ.get("SECRET_ROTATION_MAX_AGE_DAYS", "90"))

# DB columns encrypted with ENCRYPTION_KEY (verified via encrypt() call sites).
ENCRYPTED_COLUMNS = [
    (models.AIIntegration, "api_key"),
    (models.StoreConnection, "api_key"),
    (models.StoreConnection, "api_secret"),
    (models.StoreConnection, "access_token"),
]


def last_rotation_at(db: Session, secret_name: str) -> Optional[datetime]:
    row = (
        db.query(models.SecretRotationEvent)
        .filter(models.SecretRotationEvent.secret_name == secret_name)
        .order_by(models.SecretRotationEvent.rotated_at.desc())
        .first()
    )
    return row.rotated_at if row else None


def record_rotation_event(
    db: Session,
    *,
    secret_name: str,
    operator: str,
    rows_reencrypted: Optional[int] = None,
    old_key_fingerprint: Optional[str] = None,
    new_key_fingerprint: Optional[str] = None,
    notes: Optional[str] = None,
) -> models.SecretRotationEvent:
    event = models.SecretRotationEvent(
        secret_name=secret_name,
        rotated_at=datetime.now(timezone.utc),
        operator=operator,
        rows_reencrypted=rows_reencrypted,
        old_key_fingerprint=old_key_fingerprint,
        new_key_fingerprint=new_key_fingerprint,
        notes=notes,
    )
    db.add(event)
    db.commit()
    return event


def encryption_retiring_keys_present() -> bool:
    from backend.encryption import _parse_keys
    return bool(_parse_keys(os.environ.get("ENCRYPTION_KEYS_RETIRING")))


def jwt_retiring_keys_present() -> bool:
    raw = os.environ.get("JWT_SECRET_KEYS_RETIRING")
    return bool([p for p in (raw or "").split(",") if p.strip()])
```

- [ ] **Step 4: Run tests + commit**

```bash
git add backend/secret_rotation.py backend/tests/test_epic017_rotation_evidence.py
git commit -m "feat: EPIC-017 secret_rotation helpers — registry, cadence, evidence"
```

### Task 7: Advisory-locked eager re-encrypt script

**Files:**
- Create: `backend/scripts/__init__.py` (empty, if missing)
- Create: `backend/scripts/rotate_encryption.py`
- Test: `backend/tests/test_epic017_reencrypt_script.py`

- [ ] **Step 1: Write failing test** (drives the callable core; the `__main__` is a thin wrapper)

```python
# backend/tests/test_epic017_reencrypt_script.py
import importlib

from cryptography.fernet import Fernet

from backend import models


def test_reencrypts_only_non_primary_rows_and_records_evidence(db_session, monkeypatch):
    old = Fernet.generate_key().decode()
    new = Fernet.generate_key().decode()

    # Seed a row encrypted under the OLD key.
    monkeypatch.setenv("ENCRYPTION_KEY", old)
    monkeypatch.delenv("ENCRYPTION_KEYS_RETIRING", raising=False)
    import backend.encryption as enc
    importlib.reload(enc)
    integ = models.AIIntegration(name="x", provider="openai", api_key=enc.encrypt("sk-secret"))
    db_session.add(integ); db_session.commit()

    # Rotate env: new primary, old retiring.
    monkeypatch.setenv("ENCRYPTION_KEY", new)
    monkeypatch.setenv("ENCRYPTION_KEYS_RETIRING", old)
    importlib.reload(enc)
    import backend.secret_rotation as sr; importlib.reload(sr)
    import backend.scripts.rotate_encryption as script; importlib.reload(script)

    result = script.run_reencryption(db_session, operator="test", dry_run=False)
    assert result["rows_reencrypted"] == 1

    # Value still decrypts and is now on the primary key.
    importlib.reload(enc)
    db_session.refresh(integ)
    assert enc.is_encrypted_with_primary(integ.api_key) is True
    assert enc.decrypt(integ.api_key) == "sk-secret"

    # Evidence row written.
    ev = db_session.query(models.SecretRotationEvent).filter_by(secret_name="ENCRYPTION_KEY").one()
    assert ev.rows_reencrypted == 1

    # Idempotent: second run re-encrypts 0 rows.
    importlib.reload(script)
    again = script.run_reencryption(db_session, operator="test", dry_run=False)
    assert again["rows_reencrypted"] == 0


def test_dry_run_writes_nothing(db_session, monkeypatch):
    old = Fernet.generate_key().decode(); new = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", old)
    import backend.encryption as enc; importlib.reload(enc)
    db_session.add(models.AIIntegration(name="y", provider="openai", api_key=enc.encrypt("v")))
    db_session.commit()
    monkeypatch.setenv("ENCRYPTION_KEY", new); monkeypatch.setenv("ENCRYPTION_KEYS_RETIRING", old)
    importlib.reload(enc)
    import backend.scripts.rotate_encryption as script; importlib.reload(script)
    result = script.run_reencryption(db_session, operator="test", dry_run=True)
    assert result["rows_reencrypted"] == 1  # would re-encrypt 1
    assert db_session.query(models.SecretRotationEvent).count() == 0  # but wrote no evidence
```

> Note: `AIIntegration`/`StoreConnection` constructor field names must match the model. If a NOT NULL column is missing in the test seed, add the minimal required fields (read `backend/models.py`).

- [ ] **Step 2: Run to verify failure.** Expected: FAIL (module missing).

- [ ] **Step 3: Create `backend/scripts/rotate_encryption.py`**

```python
"""EPIC-017 eager re-encryption: rewrite all ENCRYPTION_KEY-encrypted DB values
onto the current primary key so a retiring key can be safely removed.

Run from the ops container (off HTTP):
    python -m backend.scripts.rotate_encryption [--dry-run]

Idempotent: values already on the primary key are skipped. Guarded by a Postgres
advisory lock so two runs cannot overlap.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend import encryption as enc
from backend import secret_rotation as sr

logger = logging.getLogger(__name__)

_ADVISORY_LOCK_KEY = 0x55_4B_49_50_17  # "UKIP" + 0x17 (EPIC-017)


def _try_advisory_lock(db: Session) -> bool:
    """Postgres advisory lock; no-op True on SQLite (tests)."""
    if db.bind.dialect.name != "postgresql":
        return True
    return bool(db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}).scalar())


def _release_advisory_lock(db: Session) -> None:
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _ADVISORY_LOCK_KEY})


def run_reencryption(db: Session, *, operator: str, dry_run: bool) -> dict:
    if not enc.has_primary_key():
        raise SystemExit("ENCRYPTION_KEY is not configured — nothing to rotate.")
    if not sr.encryption_retiring_keys_present():
        logger.info("No ENCRYPTION_KEYS_RETIRING configured — nothing to re-encrypt.")

    if not _try_advisory_lock(db):
        raise SystemExit("Another re-encryption run is in progress (advisory lock held).")

    try:
        rows = 0
        for model, column in sr.ENCRYPTED_COLUMNS:
            for obj in db.query(model).all():
                value = getattr(obj, column)
                if not value or enc.is_encrypted_with_primary(value):
                    continue
                if not dry_run:
                    setattr(obj, column, enc.encrypt(enc.decrypt(value)))
                rows += 1
        if dry_run:
            db.rollback()
            return {"rows_reencrypted": rows, "dry_run": True}

        db.commit()
        primary = os.environ.get("ENCRYPTION_KEY")
        retiring = (os.environ.get("ENCRYPTION_KEYS_RETIRING") or "").split(",")[0].strip() or None
        sr.record_rotation_event(
            db,
            secret_name="ENCRYPTION_KEY",
            operator=operator,
            rows_reencrypted=rows,
            old_key_fingerprint=enc.key_fingerprint(retiring),
            new_key_fingerprint=enc.key_fingerprint(primary),
            notes="eager re-encryption",
        )
        return {"rows_reencrypted": rows, "dry_run": False}
    finally:
        _release_advisory_lock(db)


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Re-encrypt DB ciphertext onto the primary ENCRYPTION_KEY.")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing.")
    parser.add_argument("--operator", default="ops-script")
    args = parser.parse_args(argv)

    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        result = run_reencryption(db, operator=args.operator, dry_run=args.dry_run)
        logger.info("Re-encryption complete: %s", result)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
```

> Note: `enc.encrypt(enc.decrypt(value))` is used (not `MultiFernet.rotate`) so the skip-first idempotency is explicit and testable; `decrypt` already tries primary + retiring keys.

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_epic017_reencrypt_script.py -v`
Expected: PASS (3 tests). If `db.bind` is None under the test session, use `db.get_bind()` in the lock helpers.

- [ ] **Step 5: Commit + PR**

```bash
git add backend/scripts/__init__.py backend/scripts/rotate_encryption.py backend/tests/test_epic017_reencrypt_script.py
git commit -m "feat: EPIC-017 Slice 3 — advisory-locked eager re-encrypt ops script"
```
Push, CI green, squash-merge `--delete-branch`.

---

## Slice 4 — Ops check + runbook + register

Branch: `feat/epic017-slice4-opscheck-runbook` (from fresh `main`)

### Task 8: `_secrets_check()` in `ops_checks.py`

**Files:**
- Modify: `backend/ops_checks.py`
- Test: `backend/tests/test_epic017_secrets_check.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_epic017_secrets_check.py
import importlib
from datetime import datetime, timezone, timedelta

from backend import models


def _check(db):
    import backend.ops_checks as ops
    importlib.reload(ops)
    return ops._secrets_check(db)


def test_critical_when_jwt_default_key(db_session, monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)   # falls back to insecure default
    monkeypatch.setenv("ENCRYPTION_KEY", "x" * 44)
    import backend.auth as auth; importlib.reload(auth)
    result = _check(db_session)
    assert result["status"] == "critical"


def test_warning_when_rotation_stale(db_session, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "real-secret")
    import backend.auth as auth; importlib.reload(auth)
    old = models.SecretRotationEvent(
        secret_name="ENCRYPTION_KEY", operator="x",
        rotated_at=datetime.now(timezone.utc) - timedelta(days=200))
    db_session.add(old); db_session.commit()
    result = _check(db_session)
    assert result["status"] == "warning"


def test_warning_when_retiring_keys_present(db_session, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "real-secret")
    monkeypatch.setenv("JWT_SECRET_KEYS_RETIRING", "old-secret")
    import backend.auth as auth; importlib.reload(auth)
    db_session.add(models.SecretRotationEvent(
        secret_name="ENCRYPTION_KEY", operator="x", rotated_at=datetime.now(timezone.utc)))
    db_session.commit()
    result = _check(db_session)
    assert result["status"] == "warning"
```

- [ ] **Step 2: Run to verify failure.** Expected: FAIL (`_secrets_check` undefined).

- [ ] **Step 3: Add `_secrets_check` to `backend/ops_checks.py`** (before `run_operational_checks`)

```python
def _secrets_check(db: Session) -> dict:
    """Secrets/credential rotation health (EPIC-017).

    critical: JWT using the insecure default key, or no encryption key configured.
    warning:  a tracked secret's last rotation is older than the cadence, or
              retiring keys are still configured (encryption or JWT).
    Reads the in-process module state (what the app actually uses), not os.environ.
    """
    from backend import auth, encryption, secret_rotation as sr

    jwt_default = auth.SECRET_KEY == auth._INSECURE_DEFAULT_KEY
    no_enc_key = not encryption.has_primary_key()
    enc_retiring = sr.encryption_retiring_keys_present()
    jwt_retiring = sr.jwt_retiring_keys_present()

    now = datetime.now(timezone.utc)
    max_age = timedelta(days=sr.SECRET_ROTATION_MAX_AGE_DAYS)
    stale = []
    for secret in ("ENCRYPTION_KEY", "JWT_SECRET_KEY"):
        last = sr.last_rotation_at(db, secret)
        if last is not None and (now - last) > max_age:
            stale.append(secret)

    details = {
        "jwt_insecure_default": jwt_default,
        "encryption_key_configured": not no_enc_key,
        "encryption_retiring_keys_present": enc_retiring,
        "jwt_retiring_keys_present": jwt_retiring,
        "stale_rotations": stale,
        "max_age_days": sr.SECRET_ROTATION_MAX_AGE_DAYS,
    }

    if jwt_default or no_enc_key:
        return _make_check("secrets", "critical",
            "Insecure secret configuration detected.", details)
    if stale or enc_retiring or jwt_retiring:
        return _make_check("secrets", "warning",
            "Secrets need attention (stale rotation or lingering retiring keys).", details)
    return _make_check("secrets", "ok", "Secret keys are non-default and rotations are current.", details)
```

Wire it into `run_operational_checks` (add `_secrets_check(db),` to the `checks` list) and add recommended actions in `_recommended_actions`:

```python
        if check["id"] == "secrets" and check["status"] == "critical":
            actions.append("Set JWT_SECRET_KEY and ENCRYPTION_KEY to strong unique values; see docs/operating/SECRETS_ROTATION_RUNBOOK.md.")
        if check["id"] == "secrets" and check["status"] == "warning":
            actions.append("Rotate stale secrets and/or run the re-encrypt script then drop retiring keys; see the secrets rotation runbook.")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_epic017_secrets_check.py backend/tests/test_sprint104_ops_checks.py -v`
Expected: PASS. (If the existing ops-checks test asserts an exact check count, update it to include `secrets`.)

- [ ] **Step 5: Commit**

```bash
git add backend/ops_checks.py backend/tests/test_epic017_secrets_check.py
git commit -m "feat: EPIC-017 Slice 4 — secrets ops health check"
```

### Task 9: Runbook

**Files:** Create `docs/operating/SECRETS_ROTATION_RUNBOOK.md`.

- [ ] **Step 1:** Write the runbook covering: cadence (90 days) + owner; per-secret staged rollover for `ENCRYPTION_KEY` (new primary → old to `ENCRYPTION_KEYS_RETIRING` → redeploy → `python -m backend.scripts.rotate_encryption` from the `ukip-migrate`-style ops profile → verify `rows_reencrypted` + `/ops/checks` `secrets`=ok → drop retiring key → redeploy), `JWT_SECRET_KEY` (primary swap, old to `JWT_SECRET_KEYS_RETIRING`, drop after `JWT_REFRESH_MINUTES` grace window), and `ADMIN_PASSWORD` (password endpoint / re-bootstrap); evidence verification (`secret_rotation_events`); and post-exposure incident rotation.
- [ ] **Step 2: Commit**

```bash
git add docs/operating/SECRETS_ROTATION_RUNBOOK.md
git commit -m "docs: EPIC-017 secrets rotation runbook + ownership"
```

### Task 10: Close the register gap

**Files:** Modify `backend/enterprise_readiness.py`; update `backend/tests/test_sprint104_enterprise_readiness.py` if needed (count-agnostic, but `secrets_rotation` must no longer be the open P0).

- [ ] **Step 1: Write/adjust test** asserting `secrets_rotation` is in `resolved` and not in open `gaps`, mirroring the existing `data_lifecycle_controls`/`tenant_isolation` resolved assertions.

- [ ] **Step 2:** Remove the `secrets_rotation` dict from `ENTERPRISE_READINESS_GAPS` and append to `RESOLVED_GAPS`:

```python
    {
        "id": "secrets_rotation",
        "area": "security_operations",
        "priority": "P0",
        "status": "resolved",
        "title": "Secrets and credentials have a documented rotation program",
        "current_state": (
            "EPIC-017 delivered zero-downtime staged dual-key rotation for "
            "ENCRYPTION_KEY (MultiFernet + eager re-encrypt) and JWT_SECRET_KEY "
            "(multi-key verify), a secret_rotation_events evidence trail, a secrets "
            "ops health check, and a rotation runbook with ownership and cadence."
        ),
        "impact": (
            "Closes the last open P0 — strengthens enterprise security posture and "
            "speeds incident response after credential exposure."
        ),
        "recommendation": (
            "Follow the 90-day cadence in docs/operating/SECRETS_ROTATION_RUNBOOK.md; "
            "verify each rotation via /ops/checks and the secret_rotation_events table."
        ),
        "related_work": ["EPIC-017", "COMPLIANCE-TBD-SECRETS"],
        "resolved_at": "2026-06-05",
        "evidence": [
            "Slice 1 (MultiFernet core)",
            "Slice 2 (JWT multi-key verify)",
            "Slice 3 (evidence table + re-encrypt script)",
            "Slice 4 (ops check + runbook + register)",
            "Alembic migration e5f6a7b8c0d1 (secret_rotation_events)",
        ],
    },
```

Also drop the now-resolved `COMPLIANCE-TBD-SECRETS` roadmap hook (or retarget it), and verify the `roadmap_hooks` no longer label secrets as the "Top open P0".

- [ ] **Step 3: Run register + full suite**

Run: `.venv/Scripts/python -m pytest backend/tests/test_sprint104_enterprise_readiness.py -v && .venv/Scripts/python -m pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit + PR**

```bash
git add backend/enterprise_readiness.py backend/tests/test_sprint104_enterprise_readiness.py
git commit -m "chore: EPIC-017 mark secrets_rotation resolved — all P0 readiness gaps closed"
```
Push, CI green, squash-merge `--delete-branch`.

---

## Definition of Done

- [ ] All 4 slices merged to `main`, each CI-green.
- [ ] `ENCRYPTION_KEY` and `JWT_SECRET_KEY` support dual-key rollover with no downtime; inert when no retiring keys are set.
- [ ] `python -m backend.scripts.rotate_encryption` re-encrypts only non-primary rows, is idempotent, advisory-locked, and records evidence.
- [ ] `/ops/checks` reports a `secrets` check (critical on insecure defaults, warning on stale/lingering retiring keys).
- [ ] Runbook published; `secrets_rotation` shown as resolved in the readiness register (zero open P0 gaps).
- [ ] Update memory: append EPIC-017 entry to `MEMORY.md` after final merge.

## Post-Deploy (prod)

- Migration `e5f6a7b8c0d1` applies automatically via the fail-open entrypoint (`RUN_DB_MIGRATIONS_ON_START=1`); verify with `alembic current` → `e5f6a7b8c0d1 (head)` or `/ops/checks` `migrations`=ok.
- First rotation is operator-initiated per the runbook; until then the new code is inert.
