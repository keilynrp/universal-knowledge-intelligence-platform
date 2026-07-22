# Security Gates

Introduced: 2026-06-10. Owner: platform/security owner.

This document is the authoritative reference for every automated security gate in the UKIP pipeline. It defines what each gate checks, what blocks it, how to suppress findings, and the exception register that every suppression entry must appear in (§7).

---

## 1. Tool inventory

| Gate | Tool | Workflow file | What blocks | Suppression mechanism |
| --- | --- | --- | --- | --- |
| Secret scan | gitleaks (gitleaks/gitleaks-action@v2) | `.github/workflows/security.yml` | Any detected secret in PR commits | `.gitleaks.toml` allowlist |
| Backend deps (SCA) | pip-audit 2.10.1 (pinned) | `.github/workflows/security.yml` | Any non-ignored vulnerability in `requirements.lock` | `--ignore-vuln` flags on the audit command |
| Frontend deps (SCA) | npm audit via `frontend/scripts/check-npm-audit.mjs` wrapper | `.github/workflows/security.yml` | Non-allowlisted HIGH/CRITICAL in production deps | `frontend/.npm-audit-allowlist.json` (entries expire) |
| SAST | CodeQL (security-and-quality queries, python + javascript-typescript) | `.github/workflows/codeql.yml` | New HIGH/CRITICAL alerts once check is required | Dismiss-with-reason in GitHub code-scanning UI |
| Container scan | Trivy v0.36.0 | `.github/workflows/docker.yml` (all 3 images, pre-push) | CRITICAL with available fix (`ignore-unfixed: true`) | `.trivyignore` |
| SBOM | Syft via anchore/sbom-action@v0.24.0 | `.github/workflows/docker.yml` | n/a (evidence artifact, SPDX JSON, one per image per build, 90-day artifact retention) | n/a |
| Dependency updates | Dependabot weekly (pip, npm, github-actions) | `.github/dependabot.yml` | n/a (hygiene) | n/a |

---

## 2. Ratchet policy

New CRITICAL/HIGH findings block PRs. Pre-existing findings at gate introduction are documented in §7 (exceptions table) and targeted for remediation at the next scheduled dependency-upgrade window.

Inline ignores are banned. The suppression files and flags listed in §1 are the only permitted mechanisms for carrying a known finding past a gate. Any other form of suppression (disabling a job, skipping a step, force-pushing past a required check) requires explicit approval from the security/platform owner and a post-merge retroactive §7 entry within 24 hours.

---

## 3. Exception process

Every suppression entry requires all four of the following before the PR that introduces it is merged:

1. **Justification** — why the finding cannot be fixed now (e.g., no fix available, transitive dep awaiting upstream release).
2. **Owner** — the named role accountable for tracking and remediating.
3. **Expiry date** — the date by which the entry must be re-evaluated or removed.
4. **Register row** — a corresponding entry in §7 of this document.

**npm allowlist expiry semantics**: an entry is active through its expiry date and is enforced (i.e., will block if still present) starting the following day. The `check-npm-audit.mjs` wrapper reads the expiry field and enforces this automatically.

**Monthly review**: §7 is reviewed monthly. Expired entries that have not been renewed or resolved are escalated to the security/platform owner for immediate action.

---

## 4. Remediation SLA

| Severity | SLA from detection |
| --- | --- |
| CRITICAL | 7 calendar days |
| HIGH | 30 calendar days |

**Baseline entries** (pre-existing at gate introduction, 2026-06-10): target the next scheduled dependency-upgrade window. Each entry is tracked in §7.

---

## 5. Enforcement evidence (2026-06-10)

| Evidence | URL |
| --- | --- |
| gitleaks deliberately triggered with a fake AWS key (FAILED run; note: the canonical `AKIAIOSFODNN7EXAMPLE` is excluded by gitleaks default rules — a modified key was required to trigger) | https://github.com/keilynrp/universal-knowledge-intelligence-platform/actions/runs/27312644725 |
| First fully green Security Gates run (3 jobs: gitleaks, pip-audit, npm-audit) | https://github.com/keilynrp/universal-knowledge-intelligence-platform/actions/runs/27323826219 |
| CodeQL both languages green, 0 alerts baseline | https://github.com/keilynrp/universal-knowledge-intelligence-platform/actions/runs/27324118491 |
| Docker Images with Trivy + SBOM green, 3 SBOM artifacts | https://github.com/keilynrp/universal-knowledge-intelligence-platform/actions/runs/27326675433 |

The PR/evidence branch used to capture the gitleaks failure was deleted after capture (it contained a test secret pattern).

---

## 6. Operator steps (one-time, repo settings — pending)

The following steps must be completed by the security/platform owner in GitHub repository settings. Until they are done, ER-SDLC-001 remains at `implemented` rather than `operated`.

1. **Enable secret scanning + push protection**: Settings → Code security and analysis → enable Secret scanning and Push protection.
2. **Branch protection on `main`**: mark the following as required status checks:
   - `gitleaks`
   - `pip-audit`
   - `npm-audit`
   - `analyze (python)`
   - `analyze (javascript-typescript)`
   - `build-backend`
   - `build-frontend`
   - `build-engine`
3. After these settings are applied and the gates have operated on at least one real PR, ER-SDLC-001 moves from `implemented` to `operated`.

---

## 7. Exceptions table

### 7a. gitleaks allowlist (`.gitleaks.toml`)

EMPTY — no findings at gate introduction (2026-06-10).

### 7b. npm allowlist (`frontend/.npm-audit-allowlist.json`)

| ID | Package | Severity | Reason | Owner | Expires |
| --- | --- | --- | --- | --- | --- |
| 1124066 (GHSA-f88m-g3jw-g9cj) | sharp (bundled by next 16.x) | HIGH | npm's only "fix" is a semver-major *downgrade* to next 14. Real fix arrives when next bumps its bundled sharp. An npm `override` would force a lockfile regen, prohibited on Windows dev machines (strips linux native binaries — sharp is exactly such a module). | platform owner | 2026-08-21 |

Note (2026-07-22): the gate wrapper now propagates allowlist status through
purely-transitive findings (a package flagged only *via* another package is
allowed exactly when every such package is itself fully allowlisted). Without
this, `next`-via-`sharp` was impossible to allowlist at all: it exposes no
advisory id of its own to key an entry on. Propagation remains fail-closed —
it only flows from explicit entries.

### 7c. Trivy ignore file (`.trivyignore`)

| CVE | Where | Severity | Reason | Owner | Review by |
| --- | --- | --- | --- | --- | --- |
| CVE-2026-59873 | node-tar inside the npm CLI of the node base image (frontend image) | CRITICAL | Not an app dependency: `usr/local/lib/node_modules/npm/...`. The standalone runtime (`node server.js`) never invokes npm or tar, so the gzip-bomb DoS vector is not reachable. Clears when the node base image ships npm with tar ≥7.5.19. | platform owner | 2026-08-21 |

### 7d. CodeQL baseline

0 alerts at gate introduction (2026-06-10).

### 7e. pip-audit baseline (`--ignore-vuln` flags in `.github/workflows/security.yml`)

33 vulnerability IDs ignored at introduction. Owner: platform owner. SLA: next dependency-upgrade window (review by 2026-07-10). The 8 entries added 2026-06-18 (cryptography GHSA-537c-gmf6-5ccf; python-multipart CVE-2026-53538/53539/53540; starlette CVE-2026-48817/48818/54282/54283) are newly-disclosed CVEs in already-pinned deps — fix versions are known (see table) but starlette requires a major 0.52→1.x bump, deferred to the upgrade sprint. The 1 entry added 2026-07-07 (weasyprint CVE-2026-49452) is a newly-disclosed CVE in already-pinned weasyprint==68.1 with no fix version in the advisory DB yet (latest 69.0 not marked as fixed); revisit at the next upgrade window.

| ID | Package (pinned) | Fix version if known | Review date |
| --- | --- | --- | --- |
| PYSEC-2026-25 | authlib==1.6.9 | unknown at introduction | 2026-07-10 |
| PYSEC-2026-188 | authlib==1.6.9 | unknown at introduction | 2026-07-10 |
| CVE-2026-45829 | chromadb==1.5.2 | unknown at introduction | 2026-07-10 |
| PYSEC-2026-35 | cryptography==46.0.5 | unknown at introduction | 2026-07-10 |
| PYSEC-2026-36 | cryptography==46.0.5 | unknown at introduction | 2026-07-10 |
| CVE-2024-23342 | ecdsa==0.19.1 | unknown at introduction | 2026-07-10 |
| CVE-2026-33936 | ecdsa==0.19.1 | unknown at introduction | 2026-07-10 |
| CVE-2026-45409 | idna==3.11 | unknown at introduction | 2026-07-10 |
| PYSEC-2026-87 | lxml==6.0.2 | unknown at introduction | 2026-07-10 |
| CVE-2026-44307 | mako==1.3.10 | unknown at introduction | 2026-07-10 |
| PYSEC-2026-165 | pillow==12.1.1 | unknown at introduction | 2026-07-10 |
| CVE-2026-40192 | pillow==12.1.1 | unknown at introduction | 2026-07-10 |
| CVE-2026-42309 | pillow==12.1.1 | unknown at introduction | 2026-07-10 |
| CVE-2026-42310 | pillow==12.1.1 | unknown at introduction | 2026-07-10 |
| CVE-2026-42311 | pillow==12.1.1 | unknown at introduction | 2026-07-10 |
| CVE-2026-30922 | pyasn1==0.6.2 | unknown at introduction | 2026-07-10 |
| CVE-2026-4539 | pygments==2.19.2 | unknown at introduction | 2026-07-10 |
| CVE-2025-71176 | pytest==9.0.2 | unknown at introduction | 2026-07-10 |
| CVE-2026-40347 | python-multipart==0.0.22 | unknown at introduction | 2026-07-10 |
| CVE-2026-42561 | python-multipart==0.0.22 | unknown at introduction | 2026-07-10 |
| CVE-2026-25645 | requests==2.32.5 | unknown at introduction | 2026-07-10 |
| PYSEC-2026-161 | starlette==0.52.1 | unknown at introduction | 2026-07-10 |
| PYSEC-2026-142 | urllib3==2.6.3 | unknown at introduction | 2026-07-10 |
| PYSEC-2026-141 | urllib3==2.6.3 | unknown at introduction | 2026-07-10 |
| GHSA-537c-gmf6-5ccf | cryptography==46.0.5 | 48.0.1 | 2026-07-10 |
| CVE-2026-53540 | python-multipart==0.0.22 | 0.0.31 | 2026-07-10 |
| CVE-2026-53539 | python-multipart==0.0.22 | 0.0.30 | 2026-07-10 |
| CVE-2026-53538 | python-multipart==0.0.22 | 0.0.30 | 2026-07-10 |
| CVE-2026-48818 | starlette==0.52.1 | 1.1.0 | 2026-07-10 |
| CVE-2026-48817 | starlette==0.52.1 | 1.1.0 | 2026-07-10 |
| CVE-2026-54283 | starlette==0.52.1 | 1.3.1 | 2026-07-10 |
| CVE-2026-54282 | starlette==0.52.1 | 1.3.0 | 2026-07-10 |
| CVE-2026-49452 | weasyprint==68.1 | unknown at introduction | 2026-07-10 |

---

## 8. Known follow-ups (from gate reviews, non-blocking)

- Cache the Trivy vulnerability DB (`actions/cache` on `~/.cache/trivy`) to reduce network flakiness; a Trivy CDN outage currently blocks deploys (accepted trade-off for a hard gate).
- Consider registry layer cache (`cache-from`/`cache-to`) to avoid the double image build per job (scan build + push build).
- `gitleaks-action` requires a `GITLEAKS_LICENSE` secret if the repo ever moves to a GitHub organization; free for personal accounts.
- Dependency upgrades to burn down the 32-entry pip-audit baseline (§7e) need their own test pass before landing; plan as a dedicated upgrade sprint. Priority targets: starlette 0.52→1.x (4 CVEs; major bump, verify FastAPI compat), python-multipart →0.0.31 (3 CVEs), cryptography →48.0.1.
