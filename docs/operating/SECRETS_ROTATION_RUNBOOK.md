# Secrets & Credential Rotation Runbook (EPIC-017)

Operational procedures for rotating UKIP's secrets with **zero downtime**. The
supporting code (MultiFernet encryption, JWT multi-key verify, the evidence
table, the re-encrypt script, and the `/ops/checks` `secrets` check) is merged to
`main` and **inert until an operator performs a rotation** following this
runbook.

Run each rollover **in order**. Every rotation must end with a verification step
and leaves an auditable row in `secret_rotation_events`.

---

## Cadence & ownership

| Item | Value |
|------|-------|
| **Rotation cadence** | **90 days** per secret (configurable via `SECRET_ROTATION_MAX_AGE_DAYS`). |
| **Owner** | Platform / Security Operations (the on-call ops engineer executes; the security lead approves). |
| **Trigger** | Scheduled 90-day cadence **or** immediately after any suspected exposure (see [Post-exposure incident rotation](#post-exposure-incident-rotation)). |
| **Where to run** | The off-HTTP ops profile (`docker compose --profile ops run --rm ukip-migrate`-style container) with access to the production DB. Never expose rotation actions over HTTP. |
| **Evidence** | Each `ENCRYPTION_KEY` rotation writes a `secret_rotation_events` row. Verify via `/ops/checks` and the table (see [Evidence verification](#evidence-verification)). |

The `/ops/checks` `secrets` check warns once a tracked secret's last recorded
rotation is older than the cadence, or while any retiring key is still
configured. It returns **critical** when `JWT_SECRET_KEY` is the insecure default
or no `ENCRYPTION_KEY` is configured.

---

## Tracked secrets

| Secret | Used for | Rollover style |
|--------|----------|----------------|
| `ENCRYPTION_KEY` | Fernet encryption of stored credentials (`AIIntegration.api_key`, `StoreConnection.api_key/api_secret/access_token`) | Staged dual-key + eager re-encrypt |
| `JWT_SECRET_KEY` | Signing/verifying access & refresh JWTs | Staged dual-key verify, drop after grace window |
| `ADMIN_PASSWORD` | Bootstrap super-admin credential | Password change / re-bootstrap |

Key generation:

```bash
# Fernet key for ENCRYPTION_KEY (URL-safe base64, 32 bytes)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Strong random for JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 1. Rotate `ENCRYPTION_KEY` (staged dual-key + eager re-encrypt)

Existing ciphertext was encrypted with the old key. MultiFernet decrypts with
primary **+** retiring keys, so the app keeps working while you re-encrypt onto
the new key, then you drop the old one.

1. **Generate a new key** (see above). Keep it secret.
2. **Promote new → primary, demote old → retiring.** Set in the environment:
   - `ENCRYPTION_KEY=<new key>`
   - `ENCRYPTION_KEYS_RETIRING=<old key>`  (comma-separated if more than one is retiring)
3. **Redeploy** so every running process has both keys. The app now **encrypts
   new writes with the new key** and **decrypts existing values with either**.
   No downtime; nothing is broken if a value is still on the old key.
4. **Dry-run the re-encrypt** from the ops profile to see how many rows would change:
   ```bash
   python -m backend.scripts.rotate_encryption --dry-run
   ```
   This reports `rows_reencrypted` and writes **no** evidence and **no** data.
5. **Run the re-encrypt** for real:
   ```bash
   python -m backend.scripts.rotate_encryption --operator "<your-name-or-ticket>"
   ```
   - It walks the encrypted-column registry, re-encrypts **only** rows not already
     on the primary key (idempotent — a second run re-encrypts `0` rows),
   - is guarded by a **Postgres advisory lock** so two runs can't overlap, and
   - writes a `secret_rotation_events` row for `ENCRYPTION_KEY` with the old/new
     key fingerprints and `rows_reencrypted`.
6. **Verify** (see [Evidence verification](#evidence-verification)): `rows_reencrypted`
   matches expectation and `/ops/checks` `secrets` is no longer warning about a
   stale `ENCRYPTION_KEY`.
7. **Drop the retiring key.** Once re-encryption succeeded, remove
   `ENCRYPTION_KEYS_RETIRING` from the environment and **redeploy**. The old key
   is now unused and can be destroyed. The `secrets` check stops warning about
   lingering retiring keys.

> **Do not drop the retiring key before step 5 completes.** Any value still on the
> old key becomes undecryptable once the old key is gone.

---

## 2. Rotate `JWT_SECRET_KEY` (staged verify, drop after grace)

JWTs are signed with the primary key only and verified against primary **+**
retiring keys. Already-issued tokens stay valid until they expire.

1. **Generate a new key** (see above).
2. **Promote new → primary, demote old → retiring.** Set:
   - `JWT_SECRET_KEY=<new key>`
   - `JWT_SECRET_KEYS_RETIRING=<old key>`
3. **Redeploy.** New tokens are signed with the new key; tokens signed with the
   old key still verify during the grace window. No user is logged out.
4. **Wait out the grace window.** Keep the old key in `JWT_SECRET_KEYS_RETIRING`
   for at least the **refresh-token lifetime** (`JWT_REFRESH_MINUTES`, default
   7 days) so every outstanding refresh token has been exchanged or expired.
5. **Drop the retiring key.** Remove `JWT_SECRET_KEYS_RETIRING` and **redeploy**.
   Tokens signed with the old key now fail verification (expected — they're past
   the grace window). The `secrets` check stops warning.
6. *(Optional)* Record the rotation for evidence parity:
   ```python
   from backend.database import SessionLocal
   from backend import secret_rotation as sr
   db = SessionLocal()
   sr.record_rotation_event(db, secret_name="JWT_SECRET_KEY", operator="<your-name>",
                            notes="primary swap + retiring drop")
   db.close()
   ```
   This keeps the `secrets` staleness check green for `JWT_SECRET_KEY`.

---

## 3. Rotate `ADMIN_PASSWORD` (bootstrap super-admin)

`ADMIN_PASSWORD` only seeds the first super-admin on an empty users table; after
bootstrap, credentials live (bcrypt-hashed) in the `users` table.

- **Normal rotation (account exists):** the admin changes their own password via
  the authenticated password-change endpoint (`POST /users/me/password`), or a
  super-admin resets another user via the `/users` admin endpoints. Update the
  `ADMIN_PASSWORD` env var to the new value so a future re-bootstrap stays
  consistent, then redeploy.
- **Re-bootstrap (lost access / empty users table):** set a new `ADMIN_PASSWORD`
  (and `ADMIN_USERNAME`) in the environment and restart; the lifespan bootstrap
  recreates the super-admin from those vars when the users table is empty.

---

## Evidence verification

After an `ENCRYPTION_KEY` rotation:

```bash
# 1. Ops health — `secrets` should be `ok` (or only warn about an intentionally
#    still-present retiring key). Critical means an insecure default is in use.
curl -s -H "Authorization: Bearer <token>" https://<host>/ops/checks \
  | python -c "import sys,json; c=[x for x in json.load(sys.stdin)['checks'] if x['id']=='secrets']; print(c)"
```

```python
# 2. Inspect the evidence trail directly.
from backend.database import SessionLocal
from backend import models, secret_rotation as sr
db = SessionLocal()
last = sr.last_rotation_at(db, "ENCRYPTION_KEY")
rows = (db.query(models.SecretRotationEvent)
          .filter_by(secret_name="ENCRYPTION_KEY")
          .order_by(models.SecretRotationEvent.rotated_at.desc())
          .limit(5).all())
for r in rows:
    print(r.rotated_at, r.operator, r.rows_reencrypted,
          r.old_key_fingerprint, "→", r.new_key_fingerprint)
db.close()
```

Fingerprints are non-reversible `sha256:<12 hex>` truncations — they identify
which key was active **without** ever storing the raw key.

---

## Post-exposure incident rotation

If a secret may have leaked (committed to VCS, exposed in logs, shared in an
incident, compromised host), rotate **immediately** — do not wait for the cadence:

1. **Triage:** identify which secret(s) are exposed and the blast radius.
2. **`ENCRYPTION_KEY` exposed:** perform [section 1](#1-rotate-encryption_key-staged-dual-key--eager-re-encrypt)
   end-to-end **now**, then destroy the old key once re-encryption completes.
   Treat any data the old key could decrypt as potentially compromised.
3. **`JWT_SECRET_KEY` exposed:** perform [section 2](#2-rotate-jwt_secret_key-staged-verify-drop-after-grace),
   but **shorten or skip the grace window** and drop the retiring key
   aggressively to invalidate forged/old tokens. Expect some users to re-login.
4. **`ADMIN_PASSWORD` / user credentials exposed:** reset affected passwords via
   the `/users` endpoints; force re-login by rotating `JWT_SECRET_KEY`.
5. **Record evidence** for every rotation (the re-encrypt script does this
   automatically for `ENCRYPTION_KEY`; use `record_rotation_event` for others)
   and file the incident with the security lead.
6. **Confirm** `/ops/checks` `secrets` returns `ok` and no retiring keys linger.
