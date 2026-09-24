# Lint Debt Ratchet (issue #294)

## What this is

Backend Ruff and frontend ESLint each have a large amount of legacy,
repo-wide violations. Before this change, both were measured non-blocking
("debt radar") jobs in CI — informational, but unable to stop debt from
growing invisibly.

This mechanism turns that radar into a **monotonic ratchet**:

```
measure existing debt -> persist machine-readable baseline -> fail on
increase -> allow equality -> ratchet baseline downward when cleanup lands
```

It is **not** a lint-cleanup campaign. Legacy debt may remain indefinitely;
it just cannot grow, and its stored budget cannot go stale once real debt is
reduced.

## Components

| Piece | Path |
|---|---|
| Baseline artifact | `.github/quality/lint_baseline.json` |
| Ratchet verifier | `scripts/lint_debt_ratchet.py` |
| Changed/new backend strict gate | `scripts/lint_backend_changed.py` |
| CI wiring | `.github/workflows/lint.yml` (`lint-debt-ratchet`, `backend-lint-changed`) |
| Sentinel tests | `backend/tests/test_lint_debt_ratchet.py`, `backend/tests/test_lint_backend_changed.py` |

## The comparison policy

`scripts/lint_debt_ratchet.py check` requires **exact equality** between the
freshly measured counts and the committed baseline, for each governed
metric (`ruff.violation_count`, `eslint.error_count`, `eslint.warning_count`):

- **current > baseline → REGRESSION → FAIL.** New debt was introduced.
  Baseline increases are prohibited except through an explicit, documented
  governance decision (see Escalation, below) — this is not something a
  normal PR does by editing the JSON.
- **current < baseline → STALE → FAIL.** Real debt went down but the
  committed budget didn't follow. Fix by updating
  `.github/quality/lint_baseline.json` to the new, lower counts in the same
  PR (or an immediately coupled follow-up) that did the cleanup. This is a
  routine required edit, not a governance decision.
- **current == baseline → PASS.**

Choosing exact equality (rather than "current <= baseline") is deliberate:
it is the simplest mechanism that also satisfies "stale baselines... should
be detectable" — a plain ceiling would let a reduced-debt PR merge without
ever touching the baseline file, silently losing the improvement the next
time someone's PR happens to add back a violation elsewhere.

## Changed/new backend code: an independent, baseline-blind gate

The repo-wide ratchet above only proves "no worse in total." It would not
by itself stop a PR that adds five new violations to a file it touches while
an unrelated five were cleaned up elsewhere in the same diff — the total
stays flat, but new debt was introduced.

`scripts/lint_backend_changed.py check --base-sha <ref>` closes this: every
`backend/**.py` file the diff touches must be **fully Ruff-clean**, whole
file, not just the changed lines. This mirrors the existing frontend
changed-file ESLint gate (`frontend-lint` job) exactly, including its
whole-file (not diff-hunk) strictness — the contract calls this "equivalent
enforcement," and reusing an already-shipped pattern is the smallest way to
get there. Critically, this script takes no baseline argument and never
reads `lint_baseline.json`: a single new violation in a touched file fails
it regardless of what the repo-wide count is doing.

## Determinism

- **ESLint** version is already deterministic: `npm ci` installs exactly
  what `frontend/package-lock.json` locks (`10.8.1` as of this baseline).
  No change was needed.
- **Ruff** was previously installed unpinned in CI (`pip install ruff`).
  A ratchet compared against a moving tool version is not deterministic,
  since Ruff's own default rule selection changes across releases. The
  ratchet-related jobs now pin `ruff==0.16.4` (the version this baseline was
  measured with — see `RUFF_VERSION_PIN` in `scripts/lint_debt_ratchet.py`).
  Bump the pin and re-measure the baseline together, deliberately, when
  upgrading Ruff; do not let CI silently drift to a newer Ruff between
  baseline authoring and enforcement.
- Both measurement scripts fail closed on any tool error, non-JSON output,
  or a JSON payload that isn't the expected shape — never silently 0.
  See the sentinel tests for the full list of failure modes covered.

## Suppressions

This PR does not add or need any new `noqa` / `eslint-disable` suppression,
narrow or otherwise — it only measures and compares. If a future PR needs to
suppress a specific rule to keep the ratchet green, that suppression must be
narrowly scoped (single rule, single line/file) and justified in a comment
at the suppression site; it must not become a way to make the baseline
smaller than reality. No suppression registry or exception framework exists
or is proposed here — see Escalation, below, if one is ever judged
necessary.

## Local usage (matches CI exactly)

```bash
# Repo-wide ratchet
pip install ruff==0.16.4
(cd frontend && npm ci)
python scripts/lint_debt_ratchet.py check

# Update the baseline after a real, deliberate cleanup
python scripts/lint_debt_ratchet.py measure
# → hand-edit .github/quality/lint_baseline.json's counts to match, commit both.

# Changed/new backend code (mirrors the frontend-lint job's own BASE_SHA logic)
python scripts/lint_backend_changed.py check --base-sha <merge-base-sha>
```

`scripts/pre-push-check.sh` runs the changed-file gate against the merge base
with the push target, using the venv's ruff. It also checks the committed mode
of touched backend files: Ruff disables its `EXE` rules under WSL, so a `.py`
committed executable without a shebang passes locally and fails `EXE002` in CI.

## Path to full repo-wide blocking

Both counts remain very large today (baseline: Ruff 3,560 violations;
ESLint 0 errors / 3 warnings — frontend is already close to blocking-ready).
Committing to a calendar date now would not be evidence-based, since no
cleanup velocity data exists yet. Instead, convergence is staged on
**absolute-count milestones**, checked whenever this document or the
baseline is touched:

| Milestone | Ruff violation count | Action |
|---|---|---|
| M1 | ≤ 1,800 (~50% of baseline) | Re-evaluate promoting `ruff check backend/` to a second, independently-blocking job (in addition to the ratchet) at CI default severity. |
| M2 | ≤ 500 | Re-evaluate making repo-wide Ruff fully blocking on every PR, not just ratcheted. |
| M3 | 0 | Repo-wide Ruff becomes unconditionally blocking; the ratchet mechanism is retired for Ruff (a plain `ruff check backend/` gate replaces it). |

ESLint is already at 0 errors / 3 warnings against the full frontend tree,
so it is realistically close to being flipped to blocking outright once
those 3 warnings are cleared — no milestone table needed there; clearing the
remaining warnings and flipping `frontend-lint-repo`'s equivalent (now
folded into `lint-debt-ratchet`) to unconditionally blocking is a small,
separate follow-up PR, not part of this ratchet mechanism itself.

This table is deliberately coarse and revisitable — it is a documented,
auditable trigger per the Implementation Contract, not a commitment to a
specific sprint.

## Escalation

Per the #294 Implementation Contract, the following would require a
separate `ARCHITECTURE_DECISION_REQUIRED` review before implementation, and
are explicitly out of scope here: materially changing the canonical Ruff or
ESLint rule sets, introducing a generalized suppression/exception registry,
allowing baseline increases by policy, replacing either tool, adding an
external quality service, or a large-scale cleanup undertaken just to make
the ratchet technically feasible. None of these were needed to implement
this issue.
