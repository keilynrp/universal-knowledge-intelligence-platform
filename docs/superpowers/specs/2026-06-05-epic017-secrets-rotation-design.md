# EPIC-017: Secrets & Credential Rotation Program — Design

**Date:** 2026-06-05
**Status:** Approved (design); pending implementation
**Closes:** `secrets_rotation` (last open P0 in the enterprise readiness register)
**Related:** [[epic016-data-lifecycle]], [[epic012-tenant-isolation]]

---

## 1. Problem & Goal

The enterprise readiness register lists `secrets_rotation` as the sole remaining
**P0** gap (`status: partial`). Today:

- `backend/encryption.py` holds a single global `_fernet` built from one
  `ENCRYPTION_KEY` (Fernet, AES-128-CBC + HMAC-SHA256). Rotating it would orphan
  every encrypted DB value, because nothing can decrypt ciphertext produced by a
  retired key.
- `backend/auth.py` signs/verifies JWTs with a single `SECRET_KEY` (HS256).
  Rotating it logs out every active session immediately.
- There is **no documented rotation cadence, ownership, staged rollover, or
  evidence** that a rotation ever happened.

**Goal:** deliver a complete rotation program — code that supports **zero-downtime
staged dual-key rollover**, a **verifiable evidence trail**, an **ops health
check**, and an **operational runbook with ownership** — so all P0 readiness gaps
are closed.

### Non-goals (YAGNI)

- No external KMS/Vault integration. Secrets stay env-var driven (matches current
  deployment model: Dokploy + env). KMS can be a later EPIC.
- No automatic/scheduled rotation. Rotation is a deliberate, operator-triggered
  action (mirrors the `ukip-migrate` ops pattern).
- No rotation of infra-managed secrets (`DATABASE_URL`, Redis credentials) — those
  are owned by the platform layer, not the app.

---

## 2. Scope

Full scope: **code + operational program** (chosen during brainstorming).

In scope for app-managed secrets:

| Secret | Rotation mechanism |
|--------|--------------------|
| `ENCRYPTION_KEY` | MultiFernet dual-key + eager re-encrypt of DB ciphertext, then retire old key |
| `JWT_SECRET_KEY` | Multi-key verify (sign with primary, verify against primary + retiring) with a grace window |
| `ADMIN_PASSWORD` | Runbook-only (already hashed in `users` table; rotation = change password) |

Encrypted DB columns the re-encrypt walk must cover (confirmed via code search):

- `AIIntegration.api_key`
- `StoreConnection.api_key`, `StoreConnection.api_secret`, `StoreConnection.access_token`

---

## 3. Design

### A. Multi-key crypto core (`backend/encryption.py`)

Refactor the module to use **`MultiFernet`**:

- `ENCRYPTION_KEY` — **primary** key. Used to encrypt; first in the decrypt list.
- `ENCRYPTION_KEYS_RETIRING` — **new** env var, comma-separated list of retiring
  keys. Decrypt-only. Empty/unset by default.
- `encrypt(value)` encrypts with the primary (via `MultiFernet`, which always
  encrypts with the first key).
- `decrypt(value)` tries the full `MultiFernet` key list (primary + retiring),
  then keeps the existing **legacy-plaintext fallback** on `InvalidToken`.
- `is_encrypted_with_primary(value) -> bool` — returns True iff the value decrypts
  under the **primary key alone** (a single-key `Fernet(primary).decrypt`). Used by
  the re-encrypt walk to skip values already on the primary (see §D) — this is what
  makes re-encryption idempotent, because `MultiFernet.rotate()` itself
  unconditionally re-encrypts every value it is given.
- `key_fingerprint(key) -> str` — SHA-256 of the key, truncated (e.g. first 12 hex
  chars), prefixed `sha256:`. **Never logs or stores the raw key.** Used for
  evidence and the ops check.

**Key-parsing contract (fail-soft):** retiring keys are parsed by splitting on
comma, stripping whitespace, and dropping empty entries (tolerates trailing
commas). Each candidate is validated by constructing a `Fernet(key)`; a malformed
entry is **skipped with a warning**, never raised — constructing `MultiFernet`
with a bad key would otherwise raise at import and take down app boot, a
regression from today's fail-soft behavior (a bad primary key still degrades to
the plaintext-no-op warning path). The `MultiFernet` is built only from the
validated keys.

**Inert on deploy:** with `ENCRYPTION_KEYS_RETIRING` unset, behavior is identical
to today (single-key encrypt/decrypt + plaintext fallback).

> Refactor note: the module currently builds a module-level singleton at import.
> Preserve that ergonomics (callers use `encrypt`/`decrypt` free functions) but
> build a `MultiFernet` from the parsed key list. Keep the "no key configured →
> plaintext no-op + warning" path intact for local dev.

### B. JWT multi-key verify (`backend/auth.py`)

- `JWT_SECRET_KEY` — **primary** signing key (unchanged).
- `JWT_SECRET_KEYS_RETIRING` — **new** env var, comma-separated, verify-only.
  Same fail-soft parsing contract as §A (split, strip, drop empties; malformed
  entries skipped — though a bad HS256 key only fails at verify, not construction).
- `create_access_token` / refresh token creation sign with the primary only.
- A shared `_decode_token(token)` helper tries the primary first, then each
  retiring key, until one verifies or all fail. **All** JWT decode sites route
  through it: `get_current_user`, `optional`/`get_current_user_optional`, and the
  refresh-token endpoint (implementation must grep for every `jwt.decode` call and
  confirm none is left on the single-key path). This keeps in-flight tokens valid
  through a grace window (no mass logout on rotation).
- The multi-key loop applies **only to the JWT branch**. `get_current_user` has an
  earlier `ukip_`-prefixed **API-key** branch (auth.py) that does not use the JWT
  secret and must be left untouched.
- Preserve the existing insecure-default detection (`_INSECURE_DEFAULT_KEY`
  critical log).

**Inert on deploy:** with `JWT_SECRET_KEYS_RETIRING` unset, behavior is identical.

### C. Evidence table `secret_rotation_events`

New SQLAlchemy model + Alembic migration. Columns:

| Column | Type | Notes |
|--------|------|-------|
| `id` | int PK | |
| `secret_name` | str, indexed | e.g. `ENCRYPTION_KEY`, `JWT_SECRET_KEY` |
| `rotated_at` | datetime (tz-aware) | |
| `operator` | str | who/what triggered (username or `ops-script`) |
| `rows_reencrypted` | int, nullable | populated for `ENCRYPTION_KEY`; null otherwise |
| `old_key_fingerprint` | str, nullable | `sha256:...` truncated |
| `new_key_fingerprint` | str, nullable | `sha256:...` truncated |
| `notes` | str, nullable | |

`rows_reencrypted` is defined precisely as **the count of non-null values that
were NOT already on the primary key and were therefore re-encrypted** (i.e. rows
where `is_encrypted_with_primary` was false before the run). This is the
load-bearing value operators verify before retiring a key (§F), so its meaning is
fixed here.

Source of truth for "when was each secret last rotated", consumed by the ops check.

**Migration:** `upgrade()` creates the table. `downgrade()` drops it — and because
the table is **append-only rotation evidence**, the migration docstring must warn
that downgrading destroys rotation history; downgrade is provided for schema
reversibility only and is not part of any routine rollback.

### D. Eager re-encrypt ops script (`backend/scripts/rotate_encryption.py`)

Run as `python -m backend.scripts.rotate_encryption` from the ops container
(same pattern/profile as `ukip-migrate`; kept **off HTTP** because it is a
sensitive bulk operation).

Behavior:

1. Require both a primary `ENCRYPTION_KEY` and at least one
   `ENCRYPTION_KEYS_RETIRING` entry (otherwise nothing to rotate → exit with a
   clear message).
2. Acquire a **single-runner guard** so two concurrent invocations cannot thrash
   rows or write duplicate evidence: a Postgres advisory lock
   (`pg_try_advisory_lock`) on a fixed key, falling back to a no-op on SQLite
   (tests). If the lock is held, exit with a clear "rotation already running"
   message.
3. Walk a **registry of encrypted columns** (declared once, reused by tests):
   `[(AIIntegration, "api_key"), (StoreConnection, "api_key"), (StoreConnection,
   "api_secret"), (StoreConnection, "access_token")]`.
4. For each non-null value: **skip if `is_encrypted_with_primary(value)` is True**
   (already rotated). Otherwise `MultiFernet.rotate()` it onto the primary key
   (decrypts with whichever retiring key works, re-encrypts with the primary) and
   write it back. Count only the values actually re-encrypted (the skip-first step
   is what makes this idempotent — `MultiFernet.rotate()` alone would re-encrypt
   even primary-key ciphertext on every call).
5. Write one `secret_rotation_events` row (`secret_name="ENCRYPTION_KEY"`,
   `rows_reencrypted` per the §C definition, fingerprints, `operator="ops-script"`).
6. Flags: `--dry-run` (report counts, write nothing). A re-run after a completed
   rotation re-encrypts **0 rows** because every value is already on the primary
   (verified via the skip-first check, not via `rotate()`'s own behavior).

After a successful run, the operator removes the retired key from
`ENCRYPTION_KEYS_RETIRING`.

### E. Ops health check (`_secrets_check()` in `backend/ops_checks.py`)

Follows the existing `_make_check` / `_migrations_check` pattern; auto-joins the
`/ops/checks` aggregate and the `ops.check_failed` alert fan-out.

- **Authority of inputs:** the default-key/plaintext portion reads the **parsed
  module state** (`auth.SECRET_KEY`, `encryption`'s configured-key flag) rather
  than `os.environ` directly, so the check reflects what the *running app actually
  uses* — both are captured as module-level singletons at import (auth.py:24,
  encryption.py:19), and reading env directly could disagree with live behavior.
- **critical:** JWT using the insecure default key, **or** no encryption key
  configured (credentials stored in plaintext).
- **warning:** newest `secret_rotation_events.rotated_at` for a tracked secret is
  older than the cadence (default **90 days**, single canonical constant
  `SECRET_ROTATION_MAX_AGE_DAYS` read once), **or** retiring keys are still
  configured for **either** `ENCRYPTION_KEYS_RETIRING` (run the re-encrypt script
  and retire) **or** `JWT_SECRET_KEYS_RETIRING` (drop once the refresh-TTL grace
  window has elapsed). Both lingering-retiring-key cases must be surfaced.
- **ok:** keys are non-default and rotations are within cadence.
- Add matching `recommended_actions` entries.
- Skipped under `UKIP_SKIP_STARTUP_SIDE_EFFECTS=1` where appropriate (consistent
  with other checks; the default-key portion can still run since it reads the
  in-process module state, not DB).

### F. Runbook & ownership (`docs/operating/SECRETS_ROTATION_RUNBOOK.md`)

- Rotation cadence (90 days) and the responsible owner/role.
- Step-by-step **staged rollover** per secret:
  - `ENCRYPTION_KEY`: generate new key → set as `ENCRYPTION_KEY`, move old to
    `ENCRYPTION_KEYS_RETIRING` → redeploy → run re-encrypt script → verify via
    `/ops/checks` + `secret_rotation_events` → remove retiring key → redeploy.
  - `JWT_SECRET_KEY`: new key as primary, old to `JWT_SECRET_KEYS_RETIRING` →
    redeploy → after the access-token TTL grace window, drop the retiring key.
  - `ADMIN_PASSWORD`: change via the password endpoint / re-bootstrap.
- Evidence verification steps and incident-response (post-exposure) rotation.

---

## 4. Implementation Slices (PRs)

Mirrors the EPIC-016 style: each slice is independently mergeable and **inert**
(no behavior change) until the operator opts in by configuring retiring keys.

1. **Slice 1 — MultiFernet core.** `encryption.py` refactor + `key_fingerprint` +
   `is_encrypted_with_primary` + fail-soft `ENCRYPTION_KEYS_RETIRING` parsing.
   Tests: round-trip across a simulated rotation (encrypt with old, decrypt with
   primary+retiring); plaintext-legacy fallback preserved; fingerprint
   stability/secrecy; `is_encrypted_with_primary` true only for primary-key
   ciphertext; a malformed retiring key is skipped-with-warning (does not raise).
2. **Slice 2 — JWT multi-key verify.** Shared `_decode_token` used by every
   `jwt.decode` site; primary-only signing. Tests: token signed with a retiring
   key still verifies; token signed with an unknown key is rejected; the
   `ukip_` API-key branch is unaffected.
3. **Slice 3 — Evidence + re-encrypt script.** `secret_rotation_events` model +
   Alembic migration (with documented destructive `downgrade`) + advisory-locked
   `rotate_encryption.py` using skip-first re-encryption. Tests: `rows_reencrypted`
   counts only not-already-primary values; event row written with fingerprints;
   `--dry-run` writes nothing; a second run re-encrypts 0 rows.
4. **Slice 4 — Ops check + runbook + register.** `_secrets_check()` + runbook doc
   + move `secrets_rotation` from `ENTERPRISE_READINESS_GAPS` to `RESOLVED_GAPS`
   with evidence. Tests: critical on default/unset keys, warning on stale
   rotation + retiring-keys-present, ok on healthy state.

**TDD throughout** (RED → GREEN → refactor), 80%+ coverage on new code.

---

## 5. Risks & Mitigations

- **`MultiFernet.rotate()` is not idempotent by itself:** it re-encrypts every
  value handed to it (new IV/timestamp) regardless of which key produced the
  ciphertext, so naive use would report every row as "changed" on a second run.
  Mitigation: the script skips values where `is_encrypted_with_primary` is True
  and only calls `rotate()` on the rest (§D step 4) — this is the source of the
  0-rows-on-re-run guarantee, not `rotate()`'s own behavior.
- **Re-encrypt mid-write race:** the script runs as a one-shot ops task, but a
  store/integration could be updated concurrently, and a double-invocation could
  thrash rows. Mitigations: a single-runner advisory lock (§D step 2); and because
  a row written with the primary during the run passes the skip-first check, it is
  a no-op — a re-run is safe.
- **Ops check vs app divergence:** the check reads parsed module singletons (not
  raw env) so it reports on the keys the app actually loaded; an env change after
  import is invisible to both until restart, which is the desired/consistent
  behavior.
- **Losing a retiring key too early:** if the key is dropped from
  `ENCRYPTION_KEYS_RETIRING` before the re-encrypt script completes, old ciphertext
  becomes undecryptable. Mitigation: runbook ordering (run script + verify
  `rows_reencrypted` and `/ops/checks` ok **before** removing the key) and the
  warning check that flags retiring keys still present.
- **JWT grace window too short/long:** retiring key must stay until the longest
  access/refresh TTL elapses. Mitigation: runbook ties removal to
  `JWT_REFRESH_MINUTES`.
- **Fingerprint leakage:** truncated SHA-256 cannot reconstruct the key; raw keys
  never logged or persisted.

---

## 6. Testing Strategy

- Unit: crypto round-trip across rotation, JWT multi-key verify, fingerprint,
  re-encrypt registry walk, ops-check state matrix.
- Integration: re-encrypt script against an in-memory DB with seeded encrypted
  rows; `/ops/checks` reflecting the secrets check.
- Regression: existing `test_encryption.py` and `test_auth.py` must stay green
  (inert behavior with no retiring keys configured).
