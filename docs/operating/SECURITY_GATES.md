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

**Registry-outage resilience**: `npm audit` depends on the live npmjs.org advisory endpoint, which occasionally returns a transport error (e.g. a malformed/gzip body npm cannot parse) — a registry outage, not a finding. The wrapper retries a few times and, if the endpoint stays broken, fails **open** with a loud `WARNING` rather than blocking every PR org-wide. This applies **only** to transport errors: a real advisory report still fails closed, and a parseable report with an unrecognized schema still exits non-zero. Re-run the job once the registry recovers; the weekly scheduled scan is the backstop.

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

## 6. Operator steps (one-time, repo settings — configuration complete, observation window running)

The repository-settings steps below are now complete (§6.2 steps 1–2,
activated 2026-08-27). `ER-SDLC-001` remains at `implemented` rather than
`operated` until the resulting 30-day observation window (§6.2 step 4)
completes with reviewed, retained evidence and an accountable-owner
attestation — see
`docs/operating/ER-SDLC-001-RULESET-ACTIVATION-EVIDENCE-2026-08-27.md` §9.

### 6.1 Platform discovery (issue #317, 2026-08-27): rulesets reject a per-job `workflows` rule

An earlier attempt to configure this via a repository ruleset `workflows` rule,
listing individual job contexts directly, was rejected live by the GitHub API
with `HTTP 422: Invalid rule 'workflows'`. The follow-up `GET` on the ruleset
confirmed the rejection made zero live-state change (`UKIP_System` still had
only `deletion` and `non_fast_forward`, no bypass actors). This is recorded
here as a platform-capability finding, not as an `OPERATOR ACTION REQUIRED`
item: GitHub documents "Require workflows to pass before merging" as an
organization/enterprise-level ruleset rule. This repository's ruleset is a
user-owned, repository-level ruleset, and that context does not expose the
`workflows` rule type at all — the rejection is a rule-type/context mismatch,
not a GitHub-plan or permissions gap. The repository-level primitive this
context does expose is `required_status_checks`, which is what the
compatibility layer below targets instead.

The five authoritative workflows (`test.yml`, `lint.yml`, `security.yml`,
`codeql.yml`, `docker.yml`) also emit many individual job/matrix contexts
that would have to be hand-enumerated and re-enumerated every time a shard
count or matrix leg changes — exactly the kind of list that goes stale
unnoticed. Instead, each workflow now carries exactly one stable aggregation
job (`if: always()`, fails unless every blocking job in that workflow
succeeded — see each workflow's `*-required-gate` job and
`scripts/lint_required_gates.py`, which fails closed if a workflow's gate job
and its actual blocking jobs ever drift apart):

- `backend-required-gate` (`test.yml`)
- `lint-required-gate` (`lint.yml`)
- `security-required-gate` (`security.yml`)
- `codeql-required-gate` (`codeql.yml`)
- `docker-required-gate` (`docker.yml`) — covers `build-backend`,
  `build-frontend`, `build-engine` only; deliberately excludes the
  main-only `deploy` job, which must not gate PR merges.

These five contexts are what a future `required_status_checks` payload
(repository-level primitive, not a ruleset `workflows` rule) should target.
Adding this compatibility layer does **not** itself enable branch
protection, does **not** mutate the live `UKIP_System` ruleset, and does
**not** promote `ER-SDLC-001`'s maturity — it only makes the eventual
required-check configuration possible with five fixed names instead of an
enumerated, drift-prone job list. The live ruleset mutation is a separate,
subsequent step: §6.2 records that these five contexts have since been
observed passing on a real PR, but the mutation itself still requires
Product Owner authorization and has not occurred.

### 6.2 Remaining operator steps

1. **Enable secret scanning + push protection**: Settings → Code security and
   analysis → enable Secret scanning and Push protection. **Done.**
   Independently confirmed live (2026-08-27):
   `secret_scanning: enabled`, `secret_scanning_push_protection: enabled`,
   0 open secret-scanning alerts. See
   `docs/operating/ER-SDLC-001-RULESET-ACTIVATION-EVIDENCE-2026-08-27.md` §5.
2. **Branch protection on `main`**: configure `required_status_checks`
   (repository-level primitive) to require exactly:
   - `backend-required-gate`
   - `lint-required-gate`
   - `security-required-gate`
   - `codeql-required-gate`
   - `docker-required-gate`

   **Done.** Activated on the `UKIP_System` ruleset (id `18524885`) at
   `2026-08-27T02:58:08.760-06:00`, with `main` at PR #318's merge commit
   `4979555cd42960622c60092c2812c973eb21fe7e`. All five contexts are pinned
   to `integration_id: 15368` (the GitHub Actions App); `bypass_actors: []`
   and `current_user_can_bypass: never` are unchanged from before
   activation. Full before/after state, independent re-verification, and
   the run/job IDs proving all five contexts are real and green:
   `docs/operating/ER-SDLC-001-RULESET-ACTIVATION-EVIDENCE-2026-08-27.md`.
3. PR #318, at an earlier intermediate head (`772bb381680ca9d2c89cdeddb8e655a670f790c9`,
   not PR #318's final head), observed all five aggregate contexts above
   passing on a real PR, alongside all five authoritative workflows green on
   that same head. That observation validated the compatibility layer only,
   and did not by itself start the 30-day observation window in step 5 — the
   live ruleset activation in step 2 was a separate, subsequent event, now
   completed. The authoritative pre-merge validation evidence is PR #318's
   final head, recorded in
   `docs/operating/ER-SDLC-001-RULESET-ACTIVATION-EVIDENCE-2026-08-27.md` §4.1.
4. The 30-day observation window started at step 2's activation timestamp:
   **2026-08-27T02:58:08.760-06:00**, targeting **2026-09-26T02:58:08.760-06:00**.
   See `docs/operating/ER-SDLC-001-RULESET-ACTIVATION-EVIDENCE-2026-08-27.md`
   §6 for the retained-evidence plan and invalidation conditions for this
   window.
5. Per `docs/product/ENTERPRISE_CONTROL_REGISTER.md`, `ER-SDLC-001` may move
   from `implemented` to `operated` only after **30 days of blocking-gate
   operation and retained SBOM/security artifacts**, with that evidence
   reviewed and attested by the accountable owner — not merely after "at
   least one real PR" observing the checks exist and pass, and not merely
   after activation. `ER-SDLC-001` remains `implemented` as of this
   revision; the window in step 4 has started but not completed.

---

## 7. Exceptions table

### 7a. gitleaks allowlist (`.gitleaks.toml`)

EMPTY — no findings at gate introduction (2026-06-10).

### 7b. npm allowlist (`frontend/.npm-audit-allowlist.json`)

EMPTY as of 2026-08-20 — all eleven prior entries removed as part of #290.
See the 2026-08-20 review note below for the verification evidence and the
actual chronology (most of the underlying fixes predate #290 itself); the
pre-upgrade entries are preserved further down for history.

**Review conducted 2026-08-20** (owner: platform owner), landed via #290.
**Chronology matters here — #290 did not fix most of these advisories; it
formalized and reconciled a state that had partly already arrived.** Before
#290, `package.json` still declared `next: ^16.2.10`, but
`frontend/package-lock.json` had *already* drifted to `next@16.3.0` **and**
`postcss@8.5.23` **and** `sharp@0.35.3` via a routine Dependabot lockfile
regen on 2026-08-14 (#283) — all three resolved silently within the existing
`^16.2.10` range (Dependabot runs on GitHub's Linux infra, so this was a
legitimate resolution, just an undocumented one; `package.json` itself was
never touched by #283). #290's actual changes were: (1) bump `package.json`
to declare `next: ^16.3.1` / `eslint-config-next: ^16.3.1` (latest stable
16.3.x at review time) instead of the stale `^16.2.10`, which moved the
*resolved* `next` one further step from `16.3.0` to `16.3.1` — postcss and
sharp were untouched by #290's own diff, already sitting at `8.5.23` /
`0.35.3` beforehand; and (2) reconcile this table and the allowlist against
the resulting (mostly pre-existing) dependency graph. The lockfile refresh
that produced `next@16.3.1` was done in a Linux container (`node:22-alpine`,
matching `frontend/Dockerfile` and `.github/workflows/security.yml`'s
`node-version: 22` — never on the Windows host, per the lockfile-regen
prohibition noted throughout this table). Resolved versions after #290:
`next@16.3.1`, `eslint-config-next@16.3.1`, `postcss@8.5.23`, `sharp@0.35.3`
(react/react-dom left untouched at `19.2.8`, not downgraded).

`npm audit --omit=dev --json` against the resulting lockfile reports **zero
vulnerabilities of any severity** (`"total": 0` across critical/high/
moderate/low/info) — not merely zero HIGH/CRITICAL. `npm run audit:gate`
passes cleanly with an empty allowlist. Per-advisory disposition:

| ID | Package | Prior severity | Disposition |
| --- | --- | --- | --- |
| 1124066 (GHSA-f88m-g3jw-g9cj) | sharp (bundled by next 16.x) | HIGH | **Removed — category B.** Fixed by next 16.3.x bundling a newer sharp (`0.35.3`) — already true pre-#290 via the 2026-08-14 Dependabot regen; #290's own diff does not touch sharp. No longer emitted. |
| 1124170 (GHSA-6gpp-xcg3-4w24) | next 16.2.10 | HIGH | **Removed — category A.** Documented exit condition was "stable 16.3.0", already met pre-#290 (the 2026-08-14 Dependabot regen); #290 moves the *declared* range and resolved version one step further, to `16.3.1`. No longer emitted at either version. |
| 1124171 (GHSA-m99w-x7hq-7vfj) | next 16.2.10 | HIGH | **Removed — category A/E.** No longer emitted at 16.3.1. (Exposure was already assessed not-exposed: zero `use server` directives, re-verified 2026-08-20 — still zero.) |
| 1124184 (GHSA-89xv-2m56-2m9x) | next 16.2.10 | HIGH | **Removed — category A/E.** No longer emitted at 16.3.1. (Re-verified not exposed: no Server Actions, app still runs on `next start`.) |
| 1124186 (GHSA-68g3-v927-f742) | next 16.2.10 | MODERATE | **Removed — category A.** No longer emitted at 16.3.1. |
| 1124188 (GHSA-4633-3j49-mh5q) | next 16.2.10 | MODERATE | **Removed — category A.** No longer emitted at 16.3.1. |
| 1124190 (GHSA-4c39-4ccg-62r3) | next 16.2.10 | MODERATE | **Removed — category A/E.** No longer emitted at 16.3.1. (Re-verified not exposed: no Server Actions.) |
| 1124192 (GHSA-p9j2-gv94-2wf4) | next 16.2.10 | HIGH | **Removed — category A/E.** No longer emitted at 16.3.1. (Re-verified not exposed: `next.config.ts`'s only rewrite, `/api/backend/:path*` → `${BACKEND_INTERNAL}/:path*`, still has a fixed, env-derived destination hostname; only the path is caller-supplied.) |
| 1124194 (GHSA-q8wf-6r8g-63ch) | next 16.2.10 | MODERATE | **Removed — category A.** No longer emitted at 16.3.1. (`next/image` surface unchanged: still the single usage in `app/components/UserAvatar.tsx`.) |
| 1124196 (GHSA-955p-x3mx-jcvp) | next 16.2.10 | MODERATE | **Removed — category A/E.** No longer emitted at 16.3.1. (Re-verified not exposed: no Server Functions or Server Actions.) |
| 1124288 (GHSA-r28c-9q8g-f849) | postcss 8.5.13 | HIGH | **Removed — category A.** Exit condition was "postcss ≥ 8.5.18", already met pre-#290 (`8.5.23`, via the 2026-08-14 Dependabot regen — #290's own diff does not touch postcss). No longer emitted, and `next`'s transitive-via-postcss propagation trigger is gone with it. |

`frontend/middleware.ts` was re-read in full as part of this review: it still
only sets response headers (CSP, `X-Content-Type-Options`, `Referrer-Policy`)
and always returns `NextResponse.next()` — it still performs no
authorization, and `/embed/:token` still relies on the backend validating the
widget token. No `"use server"` directives exist anywhere in `frontend/`
(checked 2026-08-20). No new Server Actions, Server Functions, or custom
servers were introduced. These conclusions do not change the disposition
above (the advisories are gone at the dependency level regardless), but they
are recorded because several rows above previously leaned on them for
"not exposed."

The prior entries (pre-2026-08-20, describing the `next 16.2.10` /
`postcss 8.5.13` baseline) are preserved below for history and are no longer
in force:

| ID | Package | Severity | Reason | Owner | Expires |
| --- | --- | --- | --- | --- | --- |
| 1124066 (GHSA-f88m-g3jw-g9cj) | sharp (bundled by next 16.x) | HIGH | npm's only "fix" is a semver-major *downgrade* to next 14. Real fix arrives when next bumps its bundled sharp. An npm `override` would force a lockfile regen, prohibited on Windows dev machines (strips linux native binaries — sharp is exactly such a module). | platform owner | 2026-08-21 |
| 1124170 (GHSA-6gpp-xcg3-4w24) | next 16.2.10 | HIGH | **APPLIES — priority item.** Middleware/proxy bypass. Precondition confirmed present: prod build logs `Next.js 16.2.10 (Turbopack)` and there is no i18n config. Bounded impact: `frontend/middleware.ts` only sets response headers and always returns `NextResponse.next()` — it performs no authorization. A bypass serves `/embed/:token` without its per-widget CSP `frame-ancestors` (defence-in-depth from PR #167); it grants no data access, since the widget token is the access control and is validated backend-side. | platform owner | 2026-08-21 |
| 1124171 (GHSA-m99w-x7hq-7vfj) | next 16.2.10 | HIGH | **Not exposed.** DoS in App Router Server Actions; the repo contains zero `use server` directives. | platform owner | 2026-08-21 |
| 1124184 (GHSA-89xv-2m56-2m9x) | next 16.2.10 | HIGH | **Not exposed.** SSRF in Server Actions on custom servers; no Server Actions exist and the app runs on `next start`. | platform owner | 2026-08-21 |
| 1124186 (GHSA-68g3-v927-f742) | next 16.2.10 | MODERATE | **Applies.** Cache confusion of response bodies for requests with bodies. Generic to the framework; no stable fixed release exists. | platform owner | 2026-08-21 |
| 1124188 (GHSA-4633-3j49-mh5q) | next 16.2.10 | MODERATE | **Applies.** Cache confusion variant for bodies with invalid UTF-8 sequences. Same posture as 1124186. | platform owner | 2026-08-21 |
| 1124190 (GHSA-4c39-4ccg-62r3) | next 16.2.10 | MODERATE | **Not exposed.** Unbounded Server Action payload in the Edge runtime; no Server Actions exist. | platform owner | 2026-08-21 |
| 1124192 (GHSA-p9j2-gv94-2wf4) | next 16.2.10 | HIGH | **Not exposed.** SSRF in rewrites via an attacker-controlled *destination hostname*. The only rewrite is `/api/backend/:path*` → `${BACKEND_INTERNAL}/:path*`; the hostname is fixed from env and only the path segment is caller-supplied. | platform owner | 2026-08-21 |
| 1124194 (GHSA-q8wf-6r8g-63ch) | next 16.2.10 | MODERATE | **Applies.** DoS in the Image Optimization API via SVGs. Minimal surface: one `next/image` usage (`app/components/UserAvatar.tsx`). | platform owner | 2026-08-21 |
| 1124196 (GHSA-955p-x3mx-jcvp) | next 16.2.10 | MODERATE | **Not exposed.** Unauthenticated disclosure of internal Server Function endpoints; no Server Functions or Server Actions exist. | platform owner | 2026-08-21 |
| 1124288 (GHSA-r28c-9q8g-f849) | postcss 8.5.13 | HIGH | **Not exposed.** Path traversal in previous-source-map auto-loading (`sourceMappingURL` → arbitrary `.map` disclosure). postcss runs at build time over first-party Tailwind/app CSS, never at runtime over untrusted CSS. Also unblocks `next`, which is flagged only transitively *via* postcss (propagation) even though its own nine advisories are already keyed. Real fix is postcss >8.5.17, deferred to Dependabot/CI (a Windows lockfile regen strips linux/native deps). Exit condition: postcss ≥ 8.5.18. | platform owner | 2026-08-21 |

Note (2026-07-23): the nine `next` entries above were added together because
the wrapper requires *every* advisory on a flagged package to be keyed before
that package clears — allowlisting only the ones that apply would not unblock
the gate. Five of the nine were assessed as not exposed and are keyed for that
mechanical reason, not because risk was accepted; the assessment for each is in
its Reason cell and in `frontend/.npm-audit-allowlist.json`.

There is **no stable release to upgrade to**: the vulnerable range is
`14.3.0-canary.0 - 16.3.0-preview.7`, so `16.2.11` (current latest stable) is
still inside it and only `16.3.0-preview.8+` carries the fix. Shipping a
preview build of the framework to production was judged the larger risk. **Exit
condition: stable 16.3.0.** Check for it on the expiry re-check; 1124170 is the
one to clear first.

Note (2026-07-22): the gate wrapper now propagates allowlist status through
purely-transitive findings (a package flagged only *via* another package is
allowed exactly when every such package is itself fully allowlisted). Without
this, `next`-via-`sharp` was impossible to allowlist at all: it exposes no
advisory id of its own to key an entry on. Propagation remains fail-closed —
it only flows from explicit entries.

Note (2026-07-24): advisory `1124288` (postcss, GHSA-r28c-9q8g-f849) was newly
published and blocked the gate on two packages at once — postcss directly, and
`next` transitively (its `via` chain includes `postcss`), even though all nine
of `next`'s own advisories were already keyed. The propagation rule above is why
one postcss entry clears both. The real fix is a postcss bump (>8.5.17); it is
left to Dependabot/CI rather than a Windows-local lockfile regen (which strips
linux/native optional deps). Exit condition: postcss ≥ 8.5.18.

Note (2026-08-20): both exit conditions above were already satisfied before
#290 touched anything. Stable Next.js 16.3.0 released 2026-08-03; a routine
Dependabot lockfile regen on 2026-08-14 (#283) had already picked up both
`next@16.3.0` and `postcss@8.5.23` (clearing the ≥8.5.18 exit condition)
transparently under the existing `^16.2.10` range (Dependabot runs on
GitHub's Linux infra, so this was a sound resolution, just undocumented —
`package.json` itself was not bumped until #290, and postcss is not touched
by #290's diff at all). #290's own contribution is: `package.json` now
declares `next: ^16.3.1` / `eslint-config-next: ^16.3.1` (latest stable
16.3.x), moving the resolved `next` one further step to `16.3.1`; and, with
that graph in hand, reconciling this table — `npm audit --omit=dev --json`
reports zero vulnerabilities of any severity, and all eleven entries in this
section were removed. See the 2026-08-20 review note above the entries table
for the full
per-advisory disposition.

### 7c. Trivy ignore file (`.trivyignore`)

| CVE | Where | Severity | Reason | Owner | Review by |
| --- | --- | --- | --- | --- | --- |
| CVE-2026-59873 | node-tar inside the npm CLI of the node base image (frontend image) | CRITICAL | Not an app dependency: `usr/local/lib/node_modules/npm/...`. The standalone runtime (`node server.js`) never invokes npm or tar, so the gzip-bomb DoS vector is not reachable. Clears when the node base image ships npm with tar ≥7.5.19. | platform owner | 2026-08-21 |

### 7d. CodeQL baseline

0 alerts at gate introduction (2026-06-10).

### 7e. pip-audit baseline (`--ignore-vuln` flags in `.github/workflows/security.yml`)

**6 vulnerability IDs ignored** (down from 33 at gate introduction). Owner:
platform owner. SLA: next dependency-upgrade window (review by 2026-09-30).

The previous baseline deferred most entries to "the upgrade sprint", noting in
particular that the starlette CVEs needed a major 0.52 -> 1.x bump. That bump
landed with #202, which aligned `requirements.lock` to the versions the backend
image actually resolves. The upgrade reached or passed every fix version this
table had recorded — starlette 0.52.1 -> 1.3.1, cryptography 46.0.5 -> 49.0.0,
python-multipart 0.0.22 -> 0.0.32, weasyprint 68.1 -> 69.0 — so 31 entries were
suppressing advisories that no longer apply and have been removed rather than
carried forward.

Verified empirically, not by reading the table: `pip-audit -r requirements.lock
--disable-pip --no-deps` with **no** ignore flags reports exactly the five rows
below, and with all five ignored it reports `No known vulnerabilities found, 5
ignored`.

All five entries are recorded under the canonical IDs pip-audit emits. The old
list used hand-picked CVE aliases, which is why a 34-flag list could still be
doing only two flags' worth of work — an alias that stops matching fails
silently. For the three chromadb entries added 2026-08-24, pip-audit's own
canonical ID *is* the CVE number: the PyPA advisory database (the source
pip-audit prefers) has no PYSEC identifier for these three yet, only GitHub
Security Advisories (aliased to the CVEs below), so pip-audit falls back to
emitting the CVE directly. This is not a reversion to the old alias-matching
practice — it is pip-audit's real, current output for these findings,
re-verified by running the tool rather than assumed.

| ID | Package (pinned) | Fix version if known | Review date |
| --- | --- | --- | --- |
| PYSEC-2026-311 | chromadb==1.5.2 | none published | 2026-09-30 |
| PYSEC-2026-1325 | ecdsa==0.19.2 | none published | 2026-09-30 |
| CVE-2026-45830 | chromadb==1.5.2 | none published | 2026-09-30 |
| CVE-2026-45831 | chromadb==1.5.2 | none published | 2026-09-30 |
| CVE-2026-45833 | chromadb==1.5.2 | none published | 2026-09-30 |
| CVE-2026-49265 | oauthlib==3.3.1 | 4.0.0 (major) | 2026-10-31 |

**2026-09-29 review: oauthlib, CVE-2026-49265 (GHSA-xpv3-w29h-x7cv).** A
timing side channel in `oauthlib`'s PKCE `code_verifier` comparison
(`oauth2/rfc6749/grant_types/authorization_code.py`, CWE-208), fixed in 4.0.0.
It turned every PR red on the day it was published. Ignored, for two
independent reasons:

1. **Not shipped.** `oauthlib` is lock-only, reached only through
   `chromadb` -> `kubernetes` -> `requests-oauthlib`. A `pip install --dry-run
   --report -r requirements.txt -c requirements.lock` on 2026-09-29 resolved 97
   packages without `oauthlib`, `requests-oauthlib`, `kubernetes` or
   `chromadb` (run on Python 3.12; the image uses 3.13).
2. **Not reachable.** The flaw is in the authorization *server* verifying a
   PKCE verifier. UKIP issues no OAuth authorization codes; its SSO is an
   OAuth *client* built on Authlib, and nothing in `backend/` imports
   `oauthlib`.

The fix is a major version under a transitive dependency of a package the
image does not install, so it waits for `requests-oauthlib`/`kubernetes` to
accept 4.x rather than being forced into the lock. Review by 2026-10-31.

Re-verified with pip-audit 2.10.1: without ignores it reports the rows above;
with all six flags, `No known vulnerabilities found, 8 ignored`. It also shows
drift for the next review (2026-09-30): pip-audit now emits the three chromadb
findings as `PYSEC-2026-3813/3814/3815`, not the CVE IDs the flags use. The
flags still hold them, matched through aliases, which is exactly the silent
failure mode described above; switching those three flags to the canonical
IDs belongs to that review.

Note that `chromadb` is a lock-only entry: it constrains dev installs but is not
among the packages the backend image installs (`pip install -r requirements.txt
-c requirements.lock`, re-verified 2026-08-24 via `pip install --dry-run`
against the exact `requirements.txt`/`requirements.lock` pair on this branch —
`chromadb` does not appear in the resulting install set), so none of its four
advisories apply to the shipped artifact.

**2026-08-24 review — three new chromadb advisories.** pip-audit newly reports
three additional `chromadb==1.5.2` findings, all GitHub-reviewed the same day
(2026-08-24) and none previously covered by `PYSEC-2026-311`:

| CVE | GHSA | Summary | Introduced | Distinct from PYSEC-2026-311? |
| --- | --- | --- | --- | --- |
| CVE-2026-45830 | GHSA-2wm9-hf6c-p5cr | Missing authorization lets any authenticated user read/write/update/delete any tenant's collection data | 0.4.17 | Yes — separate GHSA/CVE, own root cause (authZ gap, not code injection) |
| CVE-2026-45831 | GHSA-xph7-9rjv-w5fr | `SimpleRBACAuthorizationProvider` does not scope a permission to the tenant/database/collection it was granted for | 0.5.0 | Yes — separate GHSA/CVE, RBAC scoping defect distinct from both the authZ gap above and the code-injection issue below |
| CVE-2026-45833 | GHSA-36p7-vc44-83pf | Code injection via a malicious model repository + `trust_remote_code=true` on the collection-update endpoint, for a caller with `UPDATE_COLLECTION` | 0.4.17 | Yes — a *post*-auth code-injection path (requires `UPDATE_COLLECTION`); `PYSEC-2026-311`/CVE-2026-45829 is the *pre*-auth code-injection path on the collection-create endpoint. Same vulnerability class, different endpoint and auth precondition — not an alias. |

Confirmed via OSV.dev (`GET/POST api.osv.dev` for package `chromadb`,
ecosystem `PyPI`, version `1.5.2`): all three are independent advisory records
with their own GHSA ID, none aliasing `GHSA-f4j7-r4q5-qw2c`
(`PYSEC-2026-311`/CVE-2026-45829). All four chromadb advisories (the pre-existing
one plus these three) share the same affected range ceiling — `last_affected:
1.5.9`, which is the current latest release on PyPI — so no in-range upgrade
(the disposition-order step B in the correction gate) resolves any of them;
this was checked directly (`pip index versions chromadb` → latest `1.5.9`, and
each advisory's OSV record lists `1.5.9` as still affected). Per the same gate's
disposition order, since removal (step A) is not viable — `chromadb` is a real,
if currently non-shipped, runtime dependency of `backend/analytics/vector_store.py`
(imported lazily, `backend/services/data_lifecycle.py`,
`backend/services/derived_status_service.py`, `backend/routers/ai_rag.py` via
`rag_engine.py`) and removing the pin would break the dev/test contract those
paths and their tests rely on — and no fixed release exists (step B), a governed
exception (step C) is the correct disposition, matching the existing
`PYSEC-2026-311` entry's own history (also "none published"). All three are
added to `security.yml`'s `--ignore-vuln` list and registered above with the
same 2026-09-30 review date as the other two entries so the whole `chromadb`
group is re-evaluated together.

---

## 8. Known follow-ups (from gate reviews, non-blocking)

- Cache the Trivy vulnerability DB (`actions/cache` on `~/.cache/trivy`) to reduce network flakiness; a Trivy CDN outage currently blocks deploys (accepted trade-off for a hard gate).
- Consider registry layer cache (`cache-from`/`cache-to`) to avoid the double image build per job (scan build + push build).
- `gitleaks-action` requires a `GITLEAKS_LICENSE` secret if the repo ever moves to a GitHub organization; free for personal accounts.
- Dependency upgrades to burn down the 32-entry pip-audit baseline (§7e) need their own test pass before landing; plan as a dedicated upgrade sprint. Priority targets: starlette 0.52→1.x (4 CVEs; major bump, verify FastAPI compat), python-multipart →0.0.31 (3 CVEs), cryptography →48.0.1.

---

## 9. GitHub App stateless installation-token compatibility (#299, 2026-08-23)

GitHub began a staged rollout of a new stateless GitHub App installation-token
representation (`ghs_APPID_JWT`, variable-length, roughly 520 characters,
still `ghs_`-prefixed) alongside a temporary per-request override header
(`X-GitHub-Stateless-S2S-Token: enabled|disabled`) scoped to
`POST /app/installations/:installation_id/access_tokens`. This section
records the compatibility audit against that change (EPIC-018).

**Token issuance conclusion**

- UKIP mints GitHub App installation tokens: **NO.**
- A repository-wide inventory (workflows, backend, frontend, scripts,
  SDK, Docker/deployment config, docs) found no GitHub App integration of
  any kind: no app ID, installation ID, private key, `/access_tokens` call,
  `api.github.com` client, or `gh` CLI usage anywhere in repository-owned
  code. GitHub Actions alone owns `GITHUB_TOKEN` issuance and lifecycle for
  this repository.
- Override-header applicability: **NO** — there is no UKIP-owned installation-
  token-minting flow to validate it against. Per the issue's Case B path,
  this is documented as not applicable rather than building token-minting
  infrastructure solely to exercise the header. The header was **not used**.
- Permanent override remains: **NO** (never introduced).

**Inventory method**: repository-wide grep across `.github/workflows/**`,
`backend/`, `frontend/`, `sdk/`, `scripts/`, `alembic/`, `docs/operating/`,
and Docker/deployment configuration for `GITHUB_TOKEN`, `GH_TOKEN`,
`Authorization: Bearer`/`Authorization: token`, `ghs_`/`ghp_`/`ghu_`/`gho_`/
`github_pat_`, installation IDs, `/access_tokens`, `api.github.com`, token
regexes/length checks, `split('.')`/JWT decode, and mask/redact helpers.

**Compatibility matrix**

| Surface | File/location | Token source | Behavior | Assumption | New-format risk | Validation / result |
| --- | --- | --- | --- | --- | --- | --- |
| GHCR login (3 image builds) | `.github/workflows/docker.yml:53,185,271` | Actions `GITHUB_TOKEN` | opaque pass-through | none | none — value flows straight from `secrets.GITHUB_TOKEN` into `docker/login-action@v4.6.0`'s `password` input; never read, split, or length-checked by repository code | Read (no custom code touches the value). Not applicable. |
| gitleaks scan attribution | `.github/workflows/security.yml:26` | Actions `GITHUB_TOKEN` | opaque pass-through | none | none — passed as an env var straight into `gitleaks/gitleaks-action@v3` | Read. Not applicable. |
| Secret-scan detection rules | `.gitleaks.toml` | n/a (detects, doesn't hold, tokens) | validated (via upstream ruleset) | `useDefault = true`, no repo-owned GitHub-token regex | none — gitleaks' built-in GitHub-token rules are upstream-maintained; this repo defines zero custom token regexes | Read. Third-party-owned, not applicable to remediate here. |
| Generic BYOK credential fields (`StoreConnection.api_key/api_secret/access_token`, `AIIntegration.api_key`) | `backend/models.py`, `backend/schemas.py`, `backend/routers/stores.py`, `backend/routers/ai_rag.py` | user-supplied opaque string (GitHub is not a supported `StoreConnection` platform today) | opaque pass-through, encrypted at rest (Fernet) | none — Pydantic fields carry no `max_length`; DB columns are unbounded `sa.String`/Postgres `VARCHAR` | none — already accepts arbitrary-length opaque values | Regression tests added: `backend/tests/test_github_token_opaque_compat.py` posts a 40-char (legacy-shaped) and a 520-char (stateless-shaped) synthetic opaque token to both `/stores` and `/ai-integrations`, asserts `201`, then reads the created row back from the database and decrypts the stored value — proving exact byte-for-byte equality with the original token (not merely a non-error status) for both lengths. |
| UKIP's own JWTs, Fernet keys, webhook secret, password-reset token | `backend/auth.py`, `backend/encryption.py`, `backend/schemas.py` (`WebhookCreate.secret`), `backend/routers/auth_users.py` (`PasswordResetConfirm.token`) | UKIP-generated, unrelated token families | generated / validated | UKIP's own length/format contracts (e.g. reset token 32–256 chars) | none — these are not GitHub tokens and are out of scope per the issue's token-family separation requirement | Read only. Confirmed unrelated; not modified. |

**Length/shape audit**: no repository-owned code contains a fixed
installation-token length check, a `ghs_[A-Za-z0-9]{36}`-style regex, JWT
`split('.')`/decode applied to a GitHub token, or a persistence/transport
field capped below 520 characters that could ever carry one.

**Secret-safety audit**: no logging, exception-reporting, or masking helper
in the repository does fixed-length substring redaction on GitHub-token-like
values; the only masking in this space (gitleaks' own reporting) is
upstream-owned. No live token was generated, logged, or persisted at any
point during this audit — all test values are synthetic and constructed at
runtime (never a single contiguous literal) to avoid resembling a real
credential.

**Remaining risk**: none identified. If UKIP ever adds a GitHub App
integration (installation-token minting, OAuth-via-GitHub, or a supported
`StoreConnection` platform for GitHub), re-run this audit against that new
code path — this section covers only the surfaces that exist today.

**Temporary override header**: `X-GitHub-Stateless-S2S-Token` is not a
runtime or CI dependency anywhere in this repository, before or after this
audit.
