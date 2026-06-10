# Enterprise Readiness Three Fronts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close/advance three enterprise controls: ER-SDLC-001 (CI security gates), ER-BCP-001 (PostgreSQL backups + restore drill), ER-PRIV-001 (minimum privacy pack).

**Architecture:** Three independent epics on separate branches/PRs, executed in order EPIC-019 → EPIC-018 → EPIC-020. EPIC-019 adds GitHub Actions security workflows with a ratchet policy (new CRITICAL/HIGH findings block; baselines hold pre-existing findings with expiry). EPIC-018 uses Dokploy-native scheduled backups to a user-provisioned S3-compatible bucket, plus a CI freshness monitor and an evidenced restore drill. EPIC-020 is a documentation pack in `docs/legal/` plus a conservative gap-register status change (`gap` → `partial`).

**Tech Stack:** GitHub Actions (CodeQL, gitleaks/gitleaks-action, pip-audit, npm audit, aquasecurity/trivy-action, anchore/sbom-action, Dependabot), Dokploy scheduled DB backups, AWS CLI against S3-compatible endpoint, Python/pytest (only `backend/enterprise_readiness.py`).

**Spec:** `docs/superpowers/specs/2026-06-10-enterprise-readiness-three-fronts-design.md`

**Conventions for all epics:**
- Branch from latest `main`. Push with `git -c credential.helper='!gh auth git-credential' push -u origin HEAD` (plain `git push` hangs on Git Credential Manager in this repo).
- Conventional commits (`ci:`, `docs:`, `test:`). No attribution footers (disabled globally).
- After pushing a workflow change, verify with `gh run list --branch <branch> --limit 5` then `gh run watch <run-id> --exit-status`.
- The repo is **public**: CodeQL, secret scanning, and push protection are free.

---

## EPIC-019 — CI Security Gates (branch `ci/epic019-security-gates`)

### Task 1: gitleaks secret-scan gate

**Files:**
- Create: `.github/workflows/security.yml`
- Create: `.gitleaks.toml`

- [ ] **Step 1: Create branch**

```bash
git checkout main && git pull
git checkout -b ci/epic019-security-gates
```

- [ ] **Step 2: Create `.gitleaks.toml`**

Start with NO allowlist entries — the baseline gets populated only from actual findings in Step 4 triage:

```toml
# Gitleaks configuration — UKIP secret-scan gate (EPIC-019, ER-SDLC-001).
# Policy: this file is the ONLY suppression mechanism for this gate.
# Every allowlist entry requires: justification, owner, expiry date,
# and a matching row in docs/operating/SECURITY_GATES.md.

[extend]
useDefault = true

[allowlist]
description = "Documented false positives only — see SECURITY_GATES.md"
paths = []
regexes = []
```

- [ ] **Step 3: Create `.github/workflows/security.yml`** with the gitleaks job (pip-audit/npm-audit jobs are added in Tasks 2-3):

```yaml
name: Security Gates

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

jobs:
  # ── Secret scan (blocking) ──────────────────────────────────────────────
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout (full history so gitleaks scans all commits in the PR)
        uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Run gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITLEAKS_CONFIG: .gitleaks.toml
```

- [ ] **Step 4: Commit, push, and triage the first run**

```bash
git add .gitleaks.toml .github/workflows/security.yml
git commit -m "ci: add gitleaks secret-scan gate (EPIC-019)"
git -c credential.helper='!gh auth git-credential' push -u origin HEAD
gh run list --branch ci/epic019-security-gates --limit 3
gh run watch <run-id> --exit-status
```

If gitleaks reports findings: triage each one. Real secret → STOP, rotate it, remove from history strategy decision with the user. False positive (e.g., the published bcrypt test hash in `backend/tests/`) → add a narrowly-scoped allowlist entry (path or regex) and record it in the governance table (Task 6). Re-run until green.

- [ ] **Step 5: Enforcement evidence — prove the gate fires**

```bash
git checkout -b test/gitleaks-enforcement-evidence
# Use a REAL-pattern fake: AWS test key id (AKIA + 16 chars) triggers the aws-access-key-id rule
printf 'aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"\naws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n' > leak-test.txt
git add leak-test.txt && git commit -m "test: gitleaks enforcement evidence (will be reverted)"
git -c credential.helper='!gh auth git-credential' push -u origin HEAD
gh run list --branch test/gitleaks-enforcement-evidence --limit 3
```

Expected: the Security Gates run FAILS on gitleaks. Save the failing run URL (goes into `SECURITY_GATES.md` as enforcement evidence). Then delete the branch:

```bash
git checkout ci/epic019-security-gates
git -c credential.helper='!gh auth git-credential' push origin --delete test/gitleaks-enforcement-evidence
git branch -D test/gitleaks-enforcement-evidence
```

### Task 2: pip-audit dependency gate (backend)

**Files:**
- Modify: `.github/workflows/security.yml` (add job)

- [ ] **Step 1: Run pip-audit locally first to know the baseline**

```bash
.venv/Scripts/python -m pip install pip-audit
.venv/Scripts/python -m pip_audit -r requirements.lock --disable-pip 2>&1 | tee /tmp/pip-audit-baseline.txt
```

Note: `requirements.lock` is the fully-pinned resolution (used as `-c` in CI install). If pip-audit rejects its format (e.g., hash/marker lines), fall back to `-r requirements.txt`; record which file the gate audits.

- [ ] **Step 2: Add the job to `security.yml`**

```yaml
  # ── Backend dependency audit (blocking; exceptions via --ignore-vuln) ───
  pip-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Install pip-audit
        run: pip install pip-audit

      - name: Audit pinned backend dependencies
        # Ratchet baseline: every --ignore-vuln entry must have a row in
        # docs/operating/SECURITY_GATES.md with justification + expiry.
        run: pip-audit -r requirements.lock --disable-pip
```

If Step 1 found existing vulnerabilities: append one `--ignore-vuln <GHSA-or-CVE-id>` per finding to that command (e.g. `pip-audit -r requirements.lock --disable-pip --ignore-vuln GHSA-xxxx-xxxx-xxxx`) — keep them on ONE line, no `\` continuations — and add a row each in the governance table with remediation SLA. Do NOT silently upgrade dependencies in this epic — file follow-up work instead (upgrades need their own test pass).

- [ ] **Step 3: Commit, push, verify green**

```bash
git add .github/workflows/security.yml
git commit -m "ci: add pip-audit dependency gate (EPIC-019)"
git -c credential.helper='!gh auth git-credential' push
gh run watch <run-id> --exit-status
```

### Task 3: npm audit gate (frontend) with allowlist wrapper

**Files:**
- Create: `frontend/scripts/check-npm-audit.mjs`
- Create: `frontend/.npm-audit-allowlist.json`
- Modify: `.github/workflows/security.yml` (add job)
- Modify: `frontend/package.json` (add script entry)

- [ ] **Step 1: Create `frontend/.npm-audit-allowlist.json`** (empty baseline; populated only from real findings)

```json
{
  "_comment": "Allowlisted npm advisories. Every entry: {\"id\": <advisory id or GHSA>, \"reason\": \"...\", \"owner\": \"...\", \"expires\": \"YYYY-MM-DD\"}. Must match a row in docs/operating/SECURITY_GATES.md.",
  "allowlist": []
}
```

- [ ] **Step 2: Create `frontend/scripts/check-npm-audit.mjs`**

```js
#!/usr/bin/env node
/**
 * npm-audit gate with allowlist (EPIC-019, ER-SDLC-001).
 * Fails on HIGH/CRITICAL advisories in production deps unless allowlisted
 * (and not expired). npm audit has no native baseline, hence this wrapper.
 */
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

const SEVERITIES = new Set(["high", "critical"]);

const allowlistFile = new URL("../.npm-audit-allowlist.json", import.meta.url);
const { allowlist } = JSON.parse(readFileSync(allowlistFile, "utf8"));
const today = new Date().toISOString().slice(0, 10);

const active = new Map();
for (const entry of allowlist) {
  if (!entry.expires || entry.expires >= today) {
    active.set(String(entry.id), entry);
  } else {
    console.warn(`[npm-audit-gate] allowlist entry EXPIRED (now enforced): ${entry.id}`);
  }
}

let raw;
try {
  raw = execSync("npm audit --omit=dev --json", { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
} catch (err) {
  // npm audit exits non-zero when vulnerabilities exist; the JSON is still on stdout.
  if (!err.stdout) {
    console.error("[npm-audit-gate] npm audit produced no output — failing loud.");
    console.error(err.message);
    process.exit(2);
  }
  raw = err.stdout;
}

const report = JSON.parse(raw);
const vulns = report.vulnerabilities ?? {};
const blocking = [];

for (const [name, vuln] of Object.entries(vulns)) {
  if (!SEVERITIES.has(vuln.severity)) continue;
  // Advisory ids live in vuln.via entries that are objects (not strings).
  const ids = (vuln.via ?? [])
    .filter((v) => typeof v === "object")
    .map((v) => String(v.source ?? v.url?.split("/").pop() ?? ""));
  const allAllowed = ids.length > 0 && ids.every((id) => active.has(id));
  if (!allAllowed) {
    blocking.push({ name, severity: vuln.severity, ids });
  }
}

if (blocking.length > 0) {
  console.error(`[npm-audit-gate] BLOCKING: ${blocking.length} non-allowlisted high/critical advisories:`);
  for (const b of blocking) {
    console.error(`  - ${b.name} (${b.severity}) advisories: ${b.ids.join(", ") || "n/a"}`);
  }
  console.error("Fix the dependency or add a documented allowlist entry (see docs/operating/SECURITY_GATES.md).");
  process.exit(1);
}

console.log("[npm-audit-gate] OK — no non-allowlisted high/critical production advisories.");
```

- [ ] **Step 3: Add script entry to `frontend/package.json`** (in `"scripts"`):

```json
"audit:gate": "node scripts/check-npm-audit.mjs"
```

- [ ] **Step 4: Run locally, triage baseline**

```bash
cd frontend && npm run audit:gate
```

Expected: PASS, or a list of HIGH/CRITICAL advisories. For each finding: prefer `npm audit fix` if it is a semver-compatible bump (then re-run `npm test`); otherwise add a documented allowlist entry with expiry.

Note on transitive-only findings: when a vulnerable package's `via` contains only strings (pure transitive chain), the wrapper has no advisory id to match and blocks regardless of the allowlist — that is fail-closed by design. In that case allowlist the advisory at the direct dependency that surfaces it (the `via` object entry), not the transitive package name.

- [ ] **Step 5: Add the job to `security.yml`**

```yaml
  # ── Frontend dependency audit (blocking; allowlist via wrapper) ─────────
  npm-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-node@v6
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci --prefer-offline

      - name: Run npm-audit gate
        working-directory: frontend
        run: npm run audit:gate
```

- [ ] **Step 6: Commit, push, verify green**

```bash
git add frontend/scripts/check-npm-audit.mjs frontend/.npm-audit-allowlist.json frontend/package.json .github/workflows/security.yml
git commit -m "ci: add npm-audit gate with documented allowlist (EPIC-019)"
git -c credential.helper='!gh auth git-credential' push
gh run watch <run-id> --exit-status
```

### Task 4: CodeQL SAST

**Files:**
- Create: `.github/workflows/codeql.yml`

- [ ] **Step 1: Create `.github/workflows/codeql.yml`**

```yaml
name: CodeQL

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: "30 4 * * 1" # weekly Monday 04:30 UTC

permissions:
  contents: read
  security-events: write

jobs:
  analyze:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        language: [python, javascript-typescript]
    steps:
      - uses: actions/checkout@v6

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v4
        with:
          languages: ${{ matrix.language }}
          queries: security-and-quality

      - name: Analyze
        uses: github/codeql-action/analyze@v4
        with:
          category: "/language:${{ matrix.language }}"
```

- [ ] **Step 2: Commit, push, verify both matrix legs complete**

```bash
git add .github/workflows/codeql.yml
git commit -m "ci: add CodeQL SAST for python and javascript-typescript (EPIC-019)"
git -c credential.helper='!gh auth git-credential' push
gh run watch <run-id> --exit-status
```

- [ ] **Step 3: Triage initial alerts**

```bash
gh api repos/keilynrp/universal-knowledge-intelligence-platform/code-scanning/alerts --jq '.[] | {number, rule: .rule.id, severity: .rule.security_severity_level, path: .most_recent_instance.location.path}'
```

Existing alerts = the ratchet baseline: list counts by severity in `SECURITY_GATES.md` with SLA. New PR-introduced HIGH/CRITICAL alerts block once the user marks the check required (Task 7). Do NOT mass-fix existing alerts in this epic — follow-up work.

### Task 5: Trivy image scan + SBOM in docker.yml

**Files:**
- Modify: `.github/workflows/docker.yml` (all three build jobs)
- Create: `.trivyignore`

- [ ] **Step 1: Create `.trivyignore`** (empty baseline, same documented-exception policy)

```text
# Trivy ignores — every CVE here needs a row in docs/operating/SECURITY_GATES.md
# with justification, owner, expiry. Format: one CVE id per line.
```

- [ ] **Step 2: Modify each build job in `docker.yml`** (backend shown; replicate for frontend and engine with their context/file/image values). Insert between metadata extraction and the existing push build — the existing `Build ... image` step stays as-is and reuses the layer cache:

```yaml
      - name: Build image locally for scanning
        uses: docker/build-push-action@v7
        with:
          context: .
          file: Dockerfile.backend
          push: false
          load: true
          tags: scan-target:${{ github.sha }}
          build-args: |
            APP_VERSION=${{ github.sha }}

      - name: Trivy scan (blocks new CRITICAL)
        uses: aquasecurity/trivy-action@0.33.1
        with:
          image-ref: scan-target:${{ github.sha }}
          format: table
          exit-code: "1"
          severity: CRITICAL
          ignore-unfixed: true
          trivyignores: .trivyignore

      - name: Generate SBOM (SPDX)
        uses: anchore/sbom-action@v0
        with:
          image: scan-target:${{ github.sha }}
          format: spdx-json
          artifact-name: sbom-backend-${{ github.sha }}.spdx.json
```

Notes for the implementer:
- The existing push step uses `no-cache: true`; the scan build does NOT (drop `no-cache` on the scan build so the second build is the only cold one). Keep the push step untouched.
- For the frontend job pass its build-args (`NEXT_PUBLIC_API_URL`, etc.) to the scan build too, or the scanned image diverges from the shipped one.
- `ignore-unfixed: true` is part of the ratchet: unfixable base-image CVEs don't block; they surface in the table output.

- [ ] **Step 3: Commit, push, verify all three image jobs green (scan runs, SBOM artifacts uploaded)**

```bash
git add .github/workflows/docker.yml .trivyignore
git commit -m "ci: add Trivy CRITICAL gate and SPDX SBOM to image builds (EPIC-019)"
git -c credential.helper='!gh auth git-credential' push
gh run watch <run-id> --exit-status
gh run view <run-id> --json artifacts --jq '.artifacts[].name'   # expect 3 sbom-* artifacts
```

If Trivy blocks on existing CRITICALs: add them to `.trivyignore` with governance rows (baseline), or bump the base image if trivial — implementer's triage call, documented either way.

### Task 6: Dependabot + governance doc

**Files:**
- Create: `.github/dependabot.yml`
- Create: `docs/operating/SECURITY_GATES.md`

- [ ] **Step 1: Create `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
  - package-ecosystem: npm
    directory: "/frontend"
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
```

- [ ] **Step 2: Create `docs/operating/SECURITY_GATES.md`** with these sections (write real content from what Tasks 1-5 produced, not placeholders):

1. **Tool inventory** — table: gate, tool, workflow file, what blocks, suppression file.
2. **Ratchet policy** — new CRITICAL/HIGH block; pre-existing findings live in baselines (`.gitleaks.toml`, `--ignore-vuln` flags, `.npm-audit-allowlist.json`, `.trivyignore`, CodeQL alert list).
3. **Exception process** — every suppression needs justification, owner, expiry date, and a row in the exceptions table here. Inline ignores are banned.
4. **Remediation SLA** — CRITICAL 7 days, HIGH 30 days; monthly review of the exceptions table.
5. **Enforcement evidence** — link the failing gitleaks run from Task 1 Step 5; link first green Security Gates run on main.
6. **Operator steps (one-time, repo settings)** — enable secret scanning + push protection; add required status checks: `gitleaks`, `pip-audit`, `npm-audit`, CodeQL legs, and the three image-build jobs.
   Also note: `gitleaks-action@v2` is free for personal-account repos (this one), but requires a `GITLEAKS_LICENSE` secret if the repo ever moves to a GitHub organization — record this as a known migration caveat.
7. **Exceptions table** — the actual baseline entries created during Tasks 1-5 (may legitimately be empty).

- [ ] **Step 3: Update control register** — in `docs/product/ENTERPRISE_CONTROL_REGISTER.md`, ER-SDLC-001 row: `identified` → `implemented`, evidence gap → "Operator: enable push protection + required checks; first month of gate operation". (It becomes `operated` only after the operator steps are done and the gates have run on real PRs.)

- [ ] **Step 4: Commit and push**

```bash
git add .github/dependabot.yml docs/operating/SECURITY_GATES.md docs/product/ENTERPRISE_CONTROL_REGISTER.md
git commit -m "ci: add Dependabot config and security-gates governance doc (EPIC-019)"
git -c credential.helper='!gh auth git-credential' push
```

### Task 7: PR + operator handoff

- [ ] **Step 1: Open PR**

```bash
gh pr create --title "ci: security gates — CodeQL, gitleaks, pip-audit, npm-audit, Trivy, SBOM, Dependabot (EPIC-019 / ER-SDLC-001)" --body "$(cat <<'EOF'
## Summary
- CodeQL SAST (python + javascript-typescript), weekly + per-PR
- gitleaks secret scan (blocking) with documented-allowlist policy
- pip-audit (backend) and npm-audit allowlist wrapper (frontend), blocking HIGH/CRITICAL
- Trivy CRITICAL gate + SPDX SBOM artifacts on all 3 images
- Dependabot weekly (pip, npm, github-actions)
- Governance: docs/operating/SECURITY_GATES.md (ratchet policy, SLA C7/H30, exceptions table, enforcement evidence)
- Control register: ER-SDLC-001 identified → implemented

## Test plan
- [x] All new workflows green on this branch
- [x] Enforcement evidence: gitleaks failed on a deliberate fake AWS key (run linked in SECURITY_GATES.md)
- [ ] Post-merge operator steps (see SECURITY_GATES.md §6): enable push protection, mark checks required

Spec: docs/superpowers/specs/2026-06-10-enterprise-readiness-three-fronts-design.md
EOF
)"
```

- [ ] **Step 2: Wait for CI green, ask user to review/merge.**

- [ ] **Step 3: USER CHECKPOINT — operator steps after merge:** enable secret scanning + push protection (Settings → Code security), mark the new checks required in branch protection. Then update ER-SDLC-001 → `operated` in a follow-up commit.

---

## EPIC-018 — Backups + Restore Drill (branch `ops/epic018-backup-restore`)

### Task 8: Runbook with formal RTO/RPO

**Files:**
- Create: `docs/operating/BACKUP_RESTORE_RUNBOOK.md`

- [ ] **Step 1: Create branch** (from main after EPIC-019 merges, or independently — no code overlap)

```bash
git checkout main && git pull && git checkout -b ops/epic018-backup-restore
```

- [ ] **Step 2: Write `docs/operating/BACKUP_RESTORE_RUNBOOK.md`** with sections:

1. **Objectives (formal declaration)** — RTO 4h / RPO 24h; Approved by: Jose Paul (product/ops owner); Approval date: 2026-06-10; review cadence: on topology change or yearly.
2. **Scope decision** — PostgreSQL is the single source of truth (the Rust engine shares the same database). ChromaDB: regenerable via `scripts/reindex_chromadb_org_scope.py` (EPIC-012). Redis: regenerable cache, fail-open. `ukip_static_data` volume: review contents during first drill; document findings and (if non-regenerable state exists) propose handling in a follow-up.
3. **Backup configuration (Dokploy)** — step-by-step: create S3-compatible destination in Dokploy (endpoint, bucket, scoped write credentials), attach a scheduled backup to the managed PostgreSQL database: daily 03:00 UTC, prefix `pg/`, retention 7 daily + 4 weekly + 3 monthly. NOTE for writer: verify what retention granularity Dokploy's UI actually offers; if it only supports "keep N", set N=14 and document a bucket lifecycle rule for the weekly/monthly tiers (spec §8 fallback).
4. **Continuous verification** — `.github/workflows/backup-freshness.yml` (Task 9): red run = missed backup; triage steps.
5. **Restore drill procedure** — numbered, copy-paste commands (Dokploy terminal attaches INSIDE the container: single-line commands only, no pipes/heredocs — same constraints as SECRETS_ROTATION_RUNBOOK.md):
   1. Download latest dump from bucket.
   2. `createdb ukip_drill && pg_restore` (or `psql <` for plain SQL dumps — match Dokploy's dump format).
   3. Point a throwaway shell at it: `DATABASE_URL=postgresql+psycopg2://...ukip_drill python -c "..."`.
   4. Check `alembic_version` matches expected head.
   5. Row counts on key tables (`users`, `raw_entities`, `authority_records`, `organizations`) vs production.
   6. **Decrypt probe** — reuse the EPIC-017 probe: iterate `AIIntegration.api_key` + `StoreConnection.{api_key,api_secret,access_token}`, `decrypt()` each, expect `Fallidos: 0`.
   7. Record elapsed time vs RTO 4h; drop `ukip_drill`.
6. **Drill report template** — date, operator, backup timestamp used, steps executed, timings, row-count table, decrypt-probe result, pass/fail vs RTO/RPO, follow-ups.
7. **Cadence** — drill quarterly minimum and after any major schema/topology change.

- [ ] **Step 3: Commit**

```bash
git add docs/operating/BACKUP_RESTORE_RUNBOOK.md
git commit -m "docs: backup & restore runbook with formal RTO 4h / RPO 24h (EPIC-018)"
```

### Task 9: Backup freshness monitor workflow

**Files:**
- Create: `.github/workflows/backup-freshness.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: Backup Freshness

on:
  schedule:
    - cron: "0 7 * * *" # daily 07:00 UTC — 4h after the 03:00 backup window
  workflow_dispatch:
    inputs:
      prefix:
        description: "Override bucket prefix (negative test: use empty-prefix/)"
        required: false
        default: "pg/"

permissions:
  contents: read

env:
  MAX_AGE_HOURS: 26

jobs:
  check-freshness:
    runs-on: ubuntu-latest
    steps:
      - name: Check newest backup object age
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.S3_BACKUP_RO_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.S3_BACKUP_RO_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: auto
          S3_ENDPOINT: ${{ secrets.S3_BACKUP_ENDPOINT }}
          S3_BUCKET: ${{ secrets.S3_BACKUP_BUCKET }}
          PREFIX: ${{ inputs.prefix || 'pg/' }}
        run: |
          set -euo pipefail
          if [ -z "${S3_ENDPOINT}" ] || [ -z "${S3_BUCKET}" ]; then
            echo "::error::S3 backup secrets not configured (S3_BACKUP_ENDPOINT / S3_BACKUP_BUCKET)"
            exit 1
          fi
          newest="$(aws s3api list-objects-v2 \
            --endpoint-url "${S3_ENDPOINT}" \
            --bucket "${S3_BUCKET}" \
            --prefix "${PREFIX}" \
            --query 'sort_by(Contents, &LastModified)[-1].{key: Key, ts: LastModified}' \
            --output json)"
          if [ "${newest}" = "null" ] || [ -z "${newest}" ]; then
            echo "::error::No backup objects found under prefix '${PREFIX}' — backups are NOT running"
            exit 1
          fi
          key="$(echo "${newest}" | jq -r .key)"
          ts="$(echo "${newest}" | jq -r .ts)"
          age_hours="$(( ( $(date -u +%s) - $(date -u -d "${ts}" +%s) ) / 3600 ))"
          echo "Newest backup: ${key} (${ts}) — age ${age_hours}h (max ${MAX_AGE_HOURS}h)"
          if [ "${age_hours}" -gt "${MAX_AGE_HOURS}" ]; then
            echo "::error::Newest backup is ${age_hours}h old — exceeds RPO window (${MAX_AGE_HOURS}h)"
            exit 1
          fi
          echo "Backup freshness OK"
```

- [ ] **Step 2: Commit and push branch (workflow can't run successfully until secrets exist — that's Task 10)**

```bash
git add .github/workflows/backup-freshness.yml
git commit -m "ci: daily backup freshness monitor against S3 bucket (EPIC-018)"
git -c credential.helper='!gh auth git-credential' push -u origin HEAD
```

### Task 10: USER CHECKPOINT — provision bucket + configure Dokploy + secrets

- [ ] **Step 1: Present the user this checklist and WAIT:**

1. Create bucket (recommended: Cloudflare R2, e.g. `ukip-backups`).
2. Create TWO credential sets scoped to that bucket: write (for Dokploy) and read-only (for CI).
3. In Dokploy: add the S3 destination (write creds) and schedule the daily 03:00 UTC backup of the managed PostgreSQL database with prefix `pg/`, per runbook §3. Trigger one manual backup now.
4. Add GitHub Actions secrets (repo Settings → Secrets): `S3_BACKUP_ENDPOINT`, `S3_BACKUP_BUCKET`, `S3_BACKUP_RO_ACCESS_KEY_ID`, `S3_BACKUP_RO_SECRET_ACCESS_KEY`.

- [ ] **Step 2: After user confirms — positive test:**

```bash
gh workflow run backup-freshness.yml --ref ops/epic018-backup-restore
gh run watch <run-id> --exit-status
```

Expected: PASS (manual backup from step 3 is fresh).

Caveat: `gh workflow run` may return 404 for a workflow that does not yet exist on the default branch. If so, EITHER merge the workflow file to main first (small standalone PR, then dispatch with `--ref main`), OR temporarily add `push: {branches: [ops/epic018-backup-restore]}` to the workflow's `on:` block for the test and remove it before the final PR.

- [ ] **Step 3: Negative test (fail-loud evidence):**

```bash
gh workflow run backup-freshness.yml --ref ops/epic018-backup-restore -f prefix=empty-prefix/
```

Expected: FAIL with "No backup objects found". Save both run URLs for the drill evidence file.

### Task 11: First restore drill + evidence + register update

**Files:**
- Create: `docs/operating/evidence/2026-06-XX-restore-drill-001.md` (real date)
- Modify: `docs/product/ENTERPRISE_CONTROL_REGISTER.md` (ER-BCP-001 row)

- [ ] **Step 1: Execute the drill per runbook §5, guiding the user through the Dokploy terminal steps** (agent prepares each single-line command; user pastes and reports output — same operating pattern as the EPIC-017 production rotation).

- [ ] **Step 2: Write the evidence report** from the template with real timings, row counts, decrypt-probe output, and the freshness-check run URLs (positive + negative).

- [ ] **Step 3: Update register** — ER-BCP-001: `identified` → `operated`; evidence gap → "quarterly drill cadence; next due +3 months".

- [ ] **Step 4: Commit, push, PR**

```bash
git add docs/operating/evidence/ docs/product/ENTERPRISE_CONTROL_REGISTER.md
git commit -m "docs: first restore drill evidence; ER-BCP-001 to operated (EPIC-018)"
git -c credential.helper='!gh auth git-credential' push
gh pr create --title "ops: PostgreSQL backups + restore drill — RTO 4h / RPO 24h (EPIC-018 / ER-BCP-001)" --body "Runbook + freshness monitor + first drill evidence. Spec: docs/superpowers/specs/2026-06-10-enterprise-readiness-three-fronts-design.md"
```

---

## EPIC-020 — Privacy Pack (branch `docs/epic020-privacy-pack`)

### Task 12: Legal docs pack

**Files:**
- Create: `docs/legal/README.md`, `docs/legal/DPA_BASELINE.md`, `docs/legal/SUBPROCESSOR_REGISTER.md`, `docs/legal/ROPA.md`, `docs/legal/PRIVACY_CONTROLS_OVERVIEW.md`, `docs/legal/MEXICO_ANNEX.md`

- [ ] **Step 1: Create branch**

```bash
git checkout main && git pull && git checkout -b docs/epic020-privacy-pack
```

- [ ] **Step 2: Write the six documents.** EVERY file starts with this exact disclaimer block:

```markdown
> **DISCLAIMER / AVISO:** Base template prepared by the UKIP engineering team.
> NOT legal advice. Requires review by qualified counsel before being signed
> or relied upon in any contract or compliance representation.
```

Content requirements per file (ground every claim in implemented features — no aspirational claims):

- `README.md` — pack index, status (`partial` pending legal review), how to use in a procurement conversation.
- `DPA_BASELINE.md` — parties/roles (customer = controller, UKIP operator = processor); processing scope; **Annex: technical & organizational measures** mapping to real controls: tenant isolation (EPIC-012, org_id enforcement + isolation test suites), encryption at rest of credentials (Fernet/MultiFernet) + TLS in transit, RBAC + account lockout + audit log, retention/erasure/DSAR (EPIC-016, `/admin/data-lifecycle/*`), secrets rotation program (EPIC-017, 90-day cadence + evidence table), backup/restore (EPIC-018 runbook); breach notification placeholder pointing to ER-IR-001 as known open control (honesty requirement); subprocessor change-notice clause referencing the register.
- `SUBPROCESSOR_REGISTER.md` — table: name, purpose, data categories, location, status. Real entries: VPS/Dokploy host (user fills exact provider + region), Cloudflare (DNS/proxy), GitHub/GHCR (code + images, no customer data), S3 backup provider chosen in EPIC-018 (encrypted DB backups), Sentry (error telemetry — flag-gated, default OFF), OpenAI (LLM reformulation — flag-gated, default OFF). Last-reviewed date + review cadence.
- `ROPA.md` — processing activities for what UKIP actually processes: platform user accounts (username/email/role), research/bibliographic entities (authors, affiliations, publications — mostly professional/public data), authority-resolution lookups against public sources (Wikidata/VIAF/ORCID/OpenAlex/DBpedia), operational logs/audit, encrypted third-party credentials. Per activity: purpose, categories, subjects, retention (link EPIC-016 policies), security measures.
- `PRIVACY_CONTROLS_OVERVIEW.md` — one-page procurement table: control → implementation → evidence pointer (PRs, test suites, runbooks, `/ops/checks`). Include open-items row (incident response ER-IR-001, external pentest ER-ASSURE-001) — credibility through honesty.
- `MEXICO_ANNEX.md` — LFPDPPP mapping: derechos ARCO ↔ DSAR export/erasure endpoints (EPIC-016); aviso de privacidad responsibility split (customer as responsable, UKIP operator as encargado); transferencias section pointing to subprocessor register; note that the DPA structure satisfies Art. 36 LFPDPPP encargado requirements (subject to counsel review).

- [ ] **Step 3: Commit**

```bash
git add docs/legal/
git commit -m "docs: minimum privacy pack — DPA baseline, subprocessors, ROPA, controls overview, Mexico annex (EPIC-020)"
```

### Task 13: Gap register status change (TDD)

**Files:**
- Modify: `backend/enterprise_readiness.py` (privacy_legal_pack entry)
- Test: `backend/tests/test_sprint104_enterprise_readiness.py`

- [ ] **Step 1: Write the failing test** (append to the existing test file, reusing its fixtures/style):

```python
def test_privacy_legal_pack_is_partial_with_pack_reference(client, auth_headers):
    response = client.get("/ops/enterprise-readiness", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    privacy = next(g for g in body["gaps"] if g["id"] == "privacy_legal_pack")
    assert privacy["status"] == "partial"
    assert "docs/legal" in privacy["current_state"]
    assert "legal review" in privacy["current_state"].lower()
```

- [ ] **Step 2: Run it — expect FAIL** (`status` is `"gap"`)

```bash
.venv/Scripts/python -m pytest backend/tests/test_sprint104_enterprise_readiness.py -v
```

- [ ] **Step 3: Update `backend/enterprise_readiness.py`** — `privacy_legal_pack` entry: `status` → `"partial"`; rewrite `current_state` to: baseline pack exists in `docs/legal/` (DPA baseline, subprocessor register, ROPA, controls overview, Mexico annex) and remains pending professional legal review before any of it is signed or relied upon; `recommendation` → obtain external legal review, then move to resolved. Keep priority P1. Update `REGISTER_UPDATED_AT` to the real date.

- [ ] **Step 4: Run the full module test file + quick suite sanity — expect PASS**

```bash
.venv/Scripts/python -m pytest backend/tests/test_sprint104_enterprise_readiness.py -v
.venv/Scripts/python -m pytest backend/tests/ -q
```

- [ ] **Step 5: Update `docs/product/ENTERPRISE_CONTROL_REGISTER.md`** — ER-PRIV-001: `identified` → `specified`; evidence gap → "external legal review of docs/legal pack".

- [ ] **Step 6: Commit, push, PR**

```bash
git add backend/enterprise_readiness.py backend/tests/test_sprint104_enterprise_readiness.py docs/product/ENTERPRISE_CONTROL_REGISTER.md
git commit -m "feat: privacy_legal_pack gap -> partial; ER-PRIV-001 to specified (EPIC-020)"
git -c credential.helper='!gh auth git-credential' push -u origin HEAD
gh pr create --title "docs: minimum privacy pack + conservative register update (EPIC-020 / ER-PRIV-001)" --body "GDPR-shaped pack with Mexico annex in docs/legal/. Register stays partial pending professional legal review. Spec: docs/superpowers/specs/2026-06-10-enterprise-readiness-three-fronts-design.md"
```

---

## Completion checklist

- [ ] EPIC-019 PR merged; operator steps done (push protection + required checks); ER-SDLC-001 → `operated` follow-up commit.
- [ ] EPIC-018 PR merged; freshness monitor green daily; first drill evidence filed; ER-BCP-001 `operated`; calendar reminder for quarterly drill.
- [ ] EPIC-020 PR merged; backend suite green; ER-PRIV-001 `specified`; follow-up: engage counsel.
- [ ] Update project memory (MEMORY.md + topic file) with outcomes.
