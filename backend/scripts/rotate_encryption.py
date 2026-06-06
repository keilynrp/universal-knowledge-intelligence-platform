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
    """Postgres advisory lock; no-op True on SQLite (tests).

    Use db.get_bind() (robust) rather than db.bind, which can be None on sessions
    that resolve their bind at query time.
    """
    if db.get_bind().dialect.name != "postgresql":
        return True
    return bool(db.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}).scalar())


def _release_advisory_lock(db: Session) -> None:
    if db.get_bind().dialect.name == "postgresql":
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
