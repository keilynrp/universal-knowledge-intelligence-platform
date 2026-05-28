#!/usr/bin/env bash
# Pre-push smoke check that mirrors the CI gates against the local changes.
# Goal: catch CI-breaking warnings BEFORE pushing so the loop stops being
# "push → red CI → fix → push".
#
# Usage:
#   bash scripts/pre-push-check.sh            # check vs. origin/main
#   bash scripts/pre-push-check.sh HEAD~3     # check vs. an explicit base
#
# Install as a git hook to run automatically before every push:
#   ln -sf ../../scripts/pre-push-check.sh .git/hooks/pre-push
#   chmod +x scripts/pre-push-check.sh .git/hooks/pre-push
#
# Exit code 0 = safe to push. Non-zero = CI will likely fail.
set -uo pipefail

BASE="${1:-origin/main}"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

# Collect changed files vs. BASE (added + modified, no deletes)
mapfile -t CHANGED < <(git diff --name-only --diff-filter=AM "$BASE"...HEAD)

PYTHON_CHANGED=()
TS_CHANGED=()
BACKEND_TESTS_CHANGED=()

for f in "${CHANGED[@]}"; do
  case "$f" in
    *.ts|*.tsx|*.js|*.jsx) TS_CHANGED+=("$f");;
    *.py) PYTHON_CHANGED+=("$f");;
  esac
  case "$f" in
    backend/tests/test_*.py) BACKEND_TESTS_CHANGED+=("$f");;
  esac
done

EXIT=0

echo "── Pre-push check vs. $BASE ──"
echo "Changed files: ${#CHANGED[@]} (TS: ${#TS_CHANGED[@]}, Py: ${#PYTHON_CHANGED[@]})"
echo

# 1. Frontend ESLint (BLOCKING gate in CI: --max-warnings=0 on changed files)
if [ ${#TS_CHANGED[@]} -gt 0 ]; then
  echo "▶ ESLint --max-warnings=0 on changed frontend files…"
  REL=()
  for f in "${TS_CHANGED[@]}"; do
    case "$f" in
      frontend/*) REL+=("${f#frontend/}");;
    esac
  done
  if [ ${#REL[@]} -gt 0 ]; then
    (cd frontend && npx eslint --max-warnings=0 "${REL[@]}") || EXIT=1
  fi
  echo
fi

# 2. Frontend TypeScript check
if [ ${#TS_CHANGED[@]} -gt 0 ]; then
  echo "▶ tsc --noEmit (frontend)…"
  (cd frontend && npx tsc --noEmit --pretty false) || EXIT=1
  echo
fi

# 3. Domain-scope contract lint (BLOCKING in CI when backend touched)
if [ ${#PYTHON_CHANGED[@]} -gt 0 ]; then
  echo "▶ scripts/lint_domain_scope.py…"
  python scripts/lint_domain_scope.py || EXIT=1
  echo
  echo "▶ scripts/lint_entity_query.py…"
  python scripts/lint_entity_query.py || EXIT=1
  echo
fi

# 3b. Lock-file integrity (BLOCKING in CI: `npm ci` exits non-zero on drift)
# Always run — even unrelated edits can desync the lockfile if anyone ran
# `npm install` colaterally. Costs ~2s with cached node_modules.
echo "▶ npm ci --dry-run (frontend lockfile integrity)…"
LOCK_LOG="$(mktemp)"
if ! (cd frontend && npm ci --dry-run --no-audit --no-fund) >"$LOCK_LOG" 2>&1; then
  echo "  ✗ Lockfile drift detected. Last lines:"
  tail -15 "$LOCK_LOG"
  echo ""
  echo "  Hint: this often happens after \`npm install\` on Windows strips"
  echo "  Linux-only optional deps (@emnapi/*). Use scripts/refresh-lockfile.py"
  echo "  to merge platform-specific entries from origin/main."
  EXIT=1
fi
rm -f "$LOCK_LOG"
echo

# 3c. Frontend unit tests (vitest) — runs the same suite as the CI `frontend-test` job.
if [ ${#TS_CHANGED[@]} -gt 0 ]; then
  echo "▶ vitest --run (frontend unit tests)…"
  (cd frontend && npm test -- --run --reporter=dot) || EXIT=1
  echo
fi

# 4. Backend tests — scoped to changed test files when possible, full suite otherwise.
if [ ${#BACKEND_TESTS_CHANGED[@]} -gt 0 ]; then
  echo "▶ pytest (scoped to changed tests): ${BACKEND_TESTS_CHANGED[*]}"
  python -m pytest -x -q "${BACKEND_TESTS_CHANGED[@]}" || EXIT=1
  echo
elif [ ${#PYTHON_CHANGED[@]} -gt 0 ]; then
  echo "▶ pytest backend/tests (full suite — backend changed but no test file changed)…"
  python -m pytest -x -q backend/tests/ || EXIT=1
  echo
fi

if [ $EXIT -eq 0 ]; then
  echo "✓ All local gates green — safe to push."
else
  echo "✗ One or more gates failed — fix before pushing."
fi
exit $EXIT
