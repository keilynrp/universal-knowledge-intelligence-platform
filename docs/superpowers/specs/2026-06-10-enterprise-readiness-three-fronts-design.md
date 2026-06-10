# Enterprise Readiness — Three Fronts Design

**Date:** 2026-06-10
**Status:** Approved by user (design conversation, 2026-06-10)
**Epics:** EPIC-018 (ER-BCP-001 backups + restore drill), EPIC-019 (ER-SDLC-001 CI security gates), EPIC-020 (minimum privacy pack)

## 1. Goal and context

Close or materially advance three open controls from
`docs/product/ENTERPRISE_CONTROL_REGISTER.md`, now that the three commercial
P0 gaps (tenant isolation, data lifecycle, secrets rotation) are resolved:

| Control | Today | Target after this work |
| --- | --- | --- |
| ER-BCP-001 (backup/restore) | identified | operated (first drill evidenced) |
| ER-SDLC-001 (release security gates) | identified | operated (gates enforce on PRs) |
| ER-PRIV-001 (privacy pack) | identified | specified/implemented, pending external legal review |

Constraints inherited from the control register:

- Status is the lowest maturity supported by **evidence**, not by code existing.
- P0/P1 controls may not be closed by documentation-only PRs.
- No overclaiming: the `/ops/enterprise-readiness` gap register must stay honest.

## 2. Decisions locked with the user

1. **Backup destination:** new S3-compatible bucket, provisioned by the user
   (recommendation: Cloudflare R2 — free egress matters most during restores).
2. **RTO/RPO:** RTO 4h / RPO 24h, formally approved and recorded in the runbook
   with owner and approval date.
3. **Gate policy:** ratchet — new CRITICAL/HIGH findings block PRs; pre-existing
   findings live in visible baselines with documented remediation SLA
   (CRITICAL 7 days, HIGH 30 days). Same ratchet philosophy as the existing
   frontend design-system gate.
4. **Privacy framing:** GDPR-shaped artifacts plus a Mexico annex (LFPDPPP),
   because current pilots are Mexican institutions (UNAM/UDG) but the pack must
   be reusable internationally.
5. **Privacy register status:** conservative. `privacy_legal_pack` moves
   `gap` → `partial` (NOT resolved) until a professional legal review happens.
6. **Delivery:** three independent branches/PRs, order
   EPIC-019 → EPIC-018 → EPIC-020. One spec (this document), one plan with
   independent slices per epic.

## 3. EPIC-019 — CI security gates (ER-SDLC-001)

The repo is **public**, so GitHub-native security features (CodeQL, secret
scanning, push protection, Dependabot) are free and preferred where they fit.
Existing CI: `test.yml` (pytest + postgres smoke + eval gate), `lint.yml`,
`docker.yml` (3 images → GHCR → Dokploy deploy). No security gates exist today.

### New components

| Artifact | Content |
| --- | --- |
| `.github/workflows/codeql.yml` | CodeQL for `python` + `javascript-typescript`; PR, push to main, weekly cron. Blocks via required status check on new HIGH/CRITICAL alerts. |
| `.github/workflows/security.yml` | Jobs: `gitleaks` (blocking secret scan, `.gitleaks.toml` baseline with justification + expiry per entry), `pip-audit` (against `requirements.lock`, blocks new HIGH/CRITICAL, exceptions via `--ignore-vuln` documented in governance doc), `npm-audit` (`npm audit --omit=dev --audit-level=high` in `frontend/`). |
| `docker.yml` additions | Trivy image scan for the 3 images **before** GHCR push (blocks CRITICAL, `.trivyignore` with expiry); Syft SBOM (SPDX) per image uploaded as build artifact. |
| `.github/dependabot.yml` | Weekly updates: pip, npm, github-actions. |
| `docs/operating/SECURITY_GATES.md` | Governance: tool inventory, ratchet policy, exception process (who/why/expiry), remediation SLA. |

### Operator steps (user, documented in SECURITY_GATES.md)

- Enable GitHub secret scanning + push protection in repo settings.
- Mark the new checks as required in branch protection.

### Enforcement verification (evidence the gates are real)

During the epic, deliberately trigger each blocking gate once on a throwaway
branch (e.g., commit a fake secret → gitleaks run fails). Link the failing runs
from `SECURITY_GATES.md` as enforcement evidence.

### Error handling

- Scanners that need network (advisory DBs) must fail-loud, not skip silently.
- Baseline files are the only suppression mechanism; inline ignores are banned
  by the governance doc.

## 4. EPIC-018 — PostgreSQL backups + restore drill (ER-BCP-001)

Production PostgreSQL is a Dokploy-managed database on the VPS, injected via
`DATABASE_URL`. Dokploy natively supports scheduled database backups to
S3-compatible destinations — we use that instead of owning a pg_dump sidecar.

### Components

| Artifact | Content |
| --- | --- |
| S3 bucket (user op) | R2/B2/S3 bucket, credentials scoped to that bucket only. Two credential sets: write (Dokploy) and read-only (freshness check). |
| Dokploy scheduled backup (user op, runbook-guided) | Daily 03:00 UTC; retention 7 daily + 4 weekly + 3 monthly. |
| `docs/operating/BACKUP_RESTORE_RUNBOOK.md` | Formal RTO 4h / RPO 24h declaration (owner + approval date); Dokploy backup configuration steps; restore drill procedure; scope decision; drill report template. |
| `.github/workflows/backup-freshness.yml` | Daily cron: lists the bucket with read-only credentials (GH secrets), **fails if the newest backup is older than 26h**. Makes the control "operated" with continuous monitoring. |
| `docs/operating/evidence/2026-06-XX-restore-drill-001.md` | First real drill report. |
| `ENTERPRISE_CONTROL_REGISTER.md` update | ER-BCP-001 `identified` → `operated` after the first drill. |

### Scope decision (documented in the runbook)

- **PostgreSQL is the source of truth** — only state that gets backed up.
- ChromaDB vectors are re-indexable via the EPIC-012 re-index script.
- Redis is a regenerable cache (fail-open by design).
- The `ukip_static_data` volume is reviewed during the epic; if it holds
  non-regenerable state, the runbook documents it and proposes handling.

### Restore drill procedure (summary)

1. Restore the latest backup into a temporary database (not the live one).
2. Verify `alembic current` == head revision.
3. Verify row counts on key tables against production counts.
4. **Decrypt probe:** Fernet-encrypted columns must decrypt with the current
   `ENCRYPTION_KEY` (a backup that restores but cannot decrypt is not a
   recovery). Reuses the probe pattern from the secrets-rotation runbook.
5. Record timings vs RTO; file the evidence report.

### Error handling

- Freshness workflow fails loud (red run on schedule) — no silent skips.
- The runbook covers the "backup exists but is corrupt" path: the drill is the
  detection mechanism; cadence quarterly minimum.

## 5. EPIC-020 — Minimum privacy pack (ER-PRIV-001)

All artifacts in a new `docs/legal/` directory. Every document carries an
explicit disclaimer: **base template, requires professional legal review
before signing**. We are not lawyers and the register forbids overclaiming.

| Artifact | Content |
| --- | --- |
| `docs/legal/DPA_BASELINE.md` | Data processing agreement template: controller/processor roles, technical and organizational measures referencing implemented controls (tenant isolation, Fernet encryption, retention/DSAR/erasure, secrets rotation). |
| `docs/legal/SUBPROCESSOR_REGISTER.md` | Real subprocessors: VPS host, Cloudflare, GHCR, chosen S3 provider, Sentry (flag-gated), OpenAI (flag-gated, off by default). Per entry: purpose, data categories, location. |
| `docs/legal/ROPA.md` | Record of processing activities for the data categories UKIP actually processes. |
| `docs/legal/PRIVACY_CONTROLS_OVERVIEW.md` | One-pager for procurement: control → existing technical evidence mapping. |
| `docs/legal/MEXICO_ANNEX.md` | LFPDPPP equivalences; ARCO rights ↔ implemented DSAR endpoints. |

### Register updates (conservative, per user decision)

- `backend/enterprise_readiness.py`: `privacy_legal_pack` status `gap` →
  `partial`; current_state describes the pack and the pending legal review.
  Existing tests for the module updated accordingly.
- `ENTERPRISE_CONTROL_REGISTER.md`: ER-PRIV-001 `identified` → `specified`
  with evidence gap reduced to "external legal review".
- Moves to RESOLVED only after a professional legal review.

## 6. Out of scope

- Data residency claims (ER-DEP-001) — separate control, not addressed here.
- PITR / WAL archiving — overkill for RPO 24h.
- In-app legal surfaces (endpoints/pages) — YAGNI.
- Backing up ChromaDB/Redis — documented as regenerable instead.
- Wiring RetentionPurger automation — unrelated to these controls.

## 7. Testing and verification

- **EPIC-019:** every workflow validated via `workflow_dispatch`; each blocking
  gate deliberately triggered once (enforcement evidence); green main after
  merge with baselines committed.
- **EPIC-018:** freshness workflow run manually first; first restore drill
  executed for real with evidence report; failure path tested by pointing the
  freshness check at an empty prefix (expect red).
- **EPIC-020:** docs-only except `enterprise_readiness.py`; its existing pytest
  suite updated for the status change; backend test suite stays green.

## 8. Risks

| Risk | Mitigation |
| --- | --- |
| Dokploy backup feature limitations (retention granularity) | Verify during EPIC-018 first task; fallback is a documented manual retention policy or a small lifecycle rule on the bucket. |
| Gate noise alienates development flow | Ratchet policy + baselines; SLA review monthly. |
| Privacy templates mistaken for legal advice | Mandatory disclaimer block in every file; register stays `partial`. |
| Secrets for freshness check leak | Read-only, bucket-scoped credentials; stored only in GH Actions secrets. |
