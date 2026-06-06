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
- `key_fingerprint(key) -> str` — SHA-256 of the key, truncated (e.g. first 12 hex
  chars), prefixed `sha256:`. **Never logs or stores the raw key.** Used for
  evidence and the ops check.

**Inert on deploy:** with `ENCRYPTION_KEYS_RETIRING` unset, behavior is identical
to today (single-key encrypt/decrypt + plaintext fallback).

> Refactor note: the module currently builds a module-level singleton at import.
> Preserve that ergonomics (callers use `encrypt`/`decrypt` free functions) but
> build a `MultiFernet` from the parsed key list. Keep the "no key configured →
> plaintext no-op + warning" path intact for local dev.

### B. JWT multi-key verify (`backend/auth.py`)

- `JWT_SECRET_KEY` — **primary** signing key (unchanged).
- `JWT_SECRET_KEYS_RETIRING` — **new** env var, comma-separated, verify-only.
- `create_access_token` / refresh token creation sign with the primary only.
- The decode path (`get_current_user` and refresh verification) tries the primary
  first, then each retiring key, until one verifies or all fail. This keeps
  in-flight tokens valid through a grace window (no mass logout on rotation).
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

Source of truth for "when was each secret last rotated", consumed by the ops check.

### D. Eager re-encrypt ops script (`backend/scripts/rotate_encryption.py`)

Run as `python -m backend.scripts.rotate_encryption` from the ops container
(same pattern/profile as `ukip-migrate`; kept **off HTTP** because it is a
sensitive bulk operation).

Behavior:

1. Require both a primary `ENCRYPTION_KEY` and at least one
   `ENCRYPTION_KEYS_RETIRING` entry (otherwise nothing to rotate → exit with a
   clear message).
2. Walk a **registry of encrypted columns** (declared once, reused by tests):
   `[(AIIntegration, "api_key"), (StoreConnection, "api_key"), (StoreConnection,
   "api_secret"), (StoreConnection, "access_token")]`.
3. For each non-null value, `MultiFernet.rotate()` it onto the primary key (this
   decrypts with whichever key works and re-encrypts with the primary), count
   rows actually changed.
4. Write one `secret_rotation_events` row (`secret_name="ENCRYPTION_KEY"`,
   `rows_reencrypted`, fingerprints, `operator="ops-script"`).
5. Flags: `--dry-run` (report counts, write nothing) and idempotency (running
   again after a completed rotation re-encrypts 0 rows because everything already
   uses the primary key).

After a successful run, the operator removes the retired key from
`ENCRYPTION_KEYS_RETIRING`.

### E. Ops health check (`_secrets_check()` in `backend/ops_checks.py`)

Follows the existing `_make_check` / `_migrations_check` pattern; auto-joins the
`/ops/checks` aggregate and the `ops.check_failed` alert fan-out.

- **critical:** JWT using the insecure default key, **or** `ENCRYPTION_KEY` unset
  (credentials stored in plaintext).
- **warning:** newest `secret_rotation_events.rotated_at` for a tracked secret is
  older than the cadence (default **90 days**, env `SECRET_ROTATION_MAX_AGE_DAYS`),
  **or** retiring keys are still configured (reminder to run the re-encrypt script
  and retire them).
- **ok:** keys are non-default and rotations are within cadence.
- Add matching `recommended_actions` entries.
- Skipped under `UKIP_SKIP_STARTUP_SIDE_EFFECTS=1` where appropriate (consistent
  with other checks; the default-key portion can still run since it reads env).

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
   `ENCRYPTION_KEYS_RETIRING` parsing. Tests: round-trip across a simulated
   rotation (encrypt with old, decrypt with primary+retiring), plaintext-legacy
   fallback preserved, fingerprint stability/secrecy.
2. **Slice 2 — JWT multi-key verify.** `auth.py` decode tries primary + retiring.
   Tests: token signed with a retiring key still verifies; token signed with an
   unknown key is rejected; primary-only signing.
3. **Slice 3 — Evidence + re-encrypt script.** `secret_rotation_events` model +
   Alembic migration + `rotate_encryption.py`. Tests: rows re-encrypted count,
   event row written with fingerprints, `--dry-run` writes nothing, idempotent
   second run re-encrypts 0 rows.
4. **Slice 4 — Ops check + runbook + register.** `_secrets_check()` + runbook doc
   + move `secrets_rotation` from `ENTERPRISE_READINESS_GAPS` to `RESOLVED_GAPS`
   with evidence. Tests: critical on default/unset keys, warning on stale
   rotation + retiring-keys-present, ok on healthy state.

**TDD throughout** (RED → GREEN → refactor), 80%+ coverage on new code.

---

## 5. Risks & Mitigations

- **Re-encrypt mid-write race:** the script runs as a one-shot ops task, but a
  store/integration could be updated concurrently. Mitigation: `MultiFernet`
  decrypts both old and new ciphertext, so a row written with the primary during
  the run is simply skipped/no-op; idempotency makes a re-run safe.
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
