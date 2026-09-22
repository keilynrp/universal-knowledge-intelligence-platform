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
| `ADMIN_PASSWORD_HASH` / `ADMIN_PASSWORD` | Bootstrap super-admin credential (re-asserted on every startup) | Env update + redeploy — see §3 |

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
7. **Archive the old key before dropping it — do not destroy it.** Backups
   taken before this rotation still hold ciphertext encrypted with the old key,
   and restoring one of them needs that key. Retention today is roughly **120
   days** (Dokploy keeps the latest 30 backups; non-current object versions
   expire after 90 — see #320). Store it where only the operator can read it (a
   password manager), labelled with the secret name and the date it was
   retired. Delete it once no retained backup predates the rotation.
8. **Drop the retiring key.** Remove `ENCRYPTION_KEYS_RETIRING` from the
   environment and **redeploy**. The `secrets` check stops warning about
   lingering retiring keys.
9. **Confirm the container was recreated.** Saving the environment in Dokploy
   does **not** by itself restart anything, and a redeploy that did not happen
   looks exactly like one that did until you check:
   ```bash
   docker inspect -f '{{.State.StartedAt}}' <backend-container>
   docker exec <backend-container> python -c "import os;print(len(os.environ.get('ENCRYPTION_KEYS_RETIRING') or ''))"
   ```
   Expect a start time after the redeploy and a length of `0`. On 2026-09-22
   this step caught a redeploy that never recreated the container: the old key
   was still live while the check reported the rotation as done.

> **Do not drop the retiring key before step 5 completes.** Any value still on the
> old key becomes undecryptable once the old key is gone.

> **Exception — an exposed key is destroyed, not archived.** After a leak
> (see [Post-exposure incident rotation](#post-exposure-incident-rotation)),
> keeping the old key anywhere defeats the rotation. Destroy it, and accept
> that restoring a pre-rotation backup will leave values encrypted with it
> unreadable; record that consequence in the incident evidence.

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

## 3. Rotate the bootstrap super-admin password

> ⚠️ **The bootstrap env var wins on EVERY startup, not just on first bootstrap.**
> `backend/bootstrap.py` re-syncs the super-admin's password hash from the
> environment on each app start. A password changed only through the API is
> therefore **silently reverted by the next redeploy**. Always land the env change
> and the credential change together.

Credentials live bcrypt-hashed in the `users` table; the env vars seed and then
keep re-asserting that row. Two supported vars, and **`ADMIN_PASSWORD` takes
precedence** — `ADMIN_PASSWORD_HASH` is consulted only when `ADMIN_PASSWORD` is
empty (`bootstrap.py`):

| Var | Startup behaviour | Notes |
|-----|-------------------|-------|
| `ADMIN_PASSWORD_HASH` | Overwrites the stored hash on **every** start | **Preferred** — no plaintext in the Dokploy environment. Ignored unless `ADMIN_PASSWORD` is unset/empty. |
| `ADMIN_PASSWORD` | Overwrites the stored hash on every start **when it does not match** the current one | Leaves the password in cleartext in the environment. |

Generate a hash (never commit or paste the plaintext anywhere but the password
manager):

```bash
python -c "import bcrypt,getpass; print(bcrypt.hashpw(getpass.getpass().encode(), bcrypt.gensalt()).decode())"
```

A bcrypt hash contains `$` (`$2b$12$…`), which Docker Compose treats as variable
interpolation. Dokploy feeds its Environment panel to Compose, so **escape every
`$` as `$$`** when pasting the hash there — `$2b$12$…` becomes `$$2b$$12$$…`.
`bootstrap.py` un-escapes it (`resolve_bootstrap_password_hash`), so the escaped
form is what both Compose and the app expect. Same rule as `.env.example`.

- **Normal rotation (account exists) — preferred, hash-based:**
  1. Generate the new password in a password manager and hash it as above.
  2. In the Dokploy Environment, set `ADMIN_PASSWORD_HASH` to the escaped hash
     **and delete `ADMIN_PASSWORD` entirely** — leaving it set makes the hash
     inert.
  3. Redeploy. Bootstrap overwrites the stored hash, clears `failed_attempts` and
     lifts any `locked_until`.
  4. Verify by logging in with the new password; confirm the old one fails. If
     login fails with the new password, suspect a mangled `$` escape first.
- **Normal rotation (plaintext var):** change the password via `POST
  /users/me/password`, then set `ADMIN_PASSWORD` to the same new value and
  redeploy. If you skip the env update the next restart reverts it.
- **Re-bootstrap (lost access / empty users table):** set `ADMIN_USERNAME` plus
  either var and restart; the lifespan bootstrap recreates the super-admin.

Because bootstrap also clears `failed_attempts` and `locked_until`, a redeploy is
the supported way out of an `HTTP 423` lockout — no direct DB edit needed.

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
   end-to-end **now**, then destroy the old key once re-encryption completes —
   this is the one case where it is destroyed rather than archived (section 1,
   step 7). Restoring a backup taken before the rotation will leave values
   encrypted with the destroyed key unreadable; record that in the incident
   evidence rather than keeping the exposed key to avoid it.
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
