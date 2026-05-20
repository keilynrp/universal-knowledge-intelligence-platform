#!/usr/bin/env python3
"""
Lint check: enforce the entity_base_q read-model contract.

Two tiers of enforcement:

TIER 1 — HARD FAIL (fully-migrated files)
  Files listed in MIGRATED_FILES must not contain any raw
  ``db.query(models.RawEntity)`` calls.  These files have been fully
  refactored to use entity_base_q and must not regress.

TIER 2 — SOFT WARN (new/unmigrated router and service files)
  Files in backend/routers/ and backend/services/ that use
  ``db.query(models.RawEntity)`` without also importing entity_base_q
  get a WARNING so the author knows to migrate them.  This does not
  fail CI today but establishes the expectation.

Exemptions (never scanned):
  - backend/services/entity_query.py      (the factory itself)
  - backend/tests/                         (tests may query directly)
  - Any line that is a Python comment (``#``)
  - Lines containing ``.delete(`` or ``.update(`` (write operations where
    the guard does not apply — bulk mutations may need to act on ALL rows)

Usage:
    python scripts/lint_entity_query.py

Returns 0 on success (or warnings only), 1 if TIER-1 violations are found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

# Tier-1: files that have been fully migrated — raw RawEntity queries are
# regressions here.  Add a file to this list when its migration is complete.
MIGRATED_FILES: list[Path] = [
    ROOT / "backend" / "services" / "derived_status_service.py",
    ROOT / "backend" / "routers" / "disambiguation.py",
    ROOT / "backend" / "routers" / "deps.py",
]

# Tier-2: directories where new files should follow the contract.
WARN_DIRS: list[Path] = [
    ROOT / "backend" / "routers",
    ROOT / "backend" / "services",
]

# The canonical factory module — always exempt from scanning.
ENTITY_QUERY_MODULE = ROOT / "backend" / "services" / "entity_query.py"

# Test directory — always exempt.
TESTS_DIR = ROOT / "backend" / "tests"

# Patterns that indicate a raw RawEntity base query.
_RAW_QUERY_RE = re.compile(
    r"""db\.query\(\s*(?:models\.)?RawEntity\s*\)"""
    r"""|session\.query\(\s*(?:models\.)?RawEntity\s*\)"""
)

# Pattern indicating the file has already imported entity_base_q.
_IMPORT_RE = re.compile(r"from\s+backend\.services\.entity_query\s+import")

# Lines that are never violations.
_EXEMPT_LINE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*#"),                   # comment line
    re.compile(r"\.delete\s*\("),           # bulk-delete (write operation)
    re.compile(r"\.update\s*\("),           # bulk-update (write operation)
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_exempt_line(line: str) -> bool:
    return any(p.search(line) for p in _EXEMPT_LINE_PATTERNS)


def _raw_query_violations(path: Path) -> list[tuple[int, str]]:
    """Return (lineno, line) pairs for each raw-query violation in *path*."""
    violations: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"  [WARN] Cannot read {path}: {exc}", file=sys.stderr)
        return violations
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _is_exempt_line(line):
            continue
        if _RAW_QUERY_RE.search(line):
            violations.append((lineno, line.rstrip()))
    return violations


def _imports_entity_base_q(path: Path) -> bool:
    try:
        return bool(_IMPORT_RE.search(path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def _collect_warn_files() -> list[Path]:
    """All .py files in WARN_DIRS, excluding exempt paths."""
    files: list[Path] = []
    for d in WARN_DIRS:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if p == ENTITY_QUERY_MODULE:
                continue
            if TESTS_DIR in p.parents:
                continue
            # Migrated files are already checked in tier-1
            if p in MIGRATED_FILES:
                continue
            files.append(p)
    return files


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    exit_code = 0

    # ── Tier 1: hard fail on migrated files ──────────────────────────────────
    tier1_failures = 0
    for path in MIGRATED_FILES:
        if not path.exists():
            print(f"  [WARN] Migrated file not found: {path.relative_to(ROOT)}", file=sys.stderr)
            continue
        violations = _raw_query_violations(path)
        if violations:
            rel = path.relative_to(ROOT)
            print(f"\n[FAIL] Regression in fully-migrated file: {rel}")
            for lineno, line in violations:
                print(f"  line {lineno}: {line.strip()}")
            tier1_failures += len(violations)

    if tier1_failures:
        print(
            f"\n  -> These files are fully migrated to entity_base_q.  "
            "Remove the raw db.query(RawEntity) calls and use "
            "entity_base_q(db, scope, org_id) instead."
        )
        exit_code = 1
    else:
        print(f"[PASS] Tier-1: {len(MIGRATED_FILES)} migrated file(s) — zero regressions.")

    # ── Tier 2: soft warn on unmigrated files with raw queries ────────────────
    warn_files = _collect_warn_files()
    warnings: list[tuple[Path, list[tuple[int, str]]]] = []

    for path in warn_files:
        violations = _raw_query_violations(path)
        if violations and not _imports_entity_base_q(path):
            warnings.append((path, violations))

    if warnings:
        print(
            f"\n[WARN] Tier-2: {len(warnings)} file(s) use db.query(RawEntity) without "
            "importing entity_base_q.  Consider migrating:"
        )
        for path, violations in warnings:
            rel = path.relative_to(ROOT)
            print(f"  {rel} ({len(violations)} raw query line(s))")
        print(
            "  -> Import entity_base_q from backend.services.entity_query and replace "
            "inline query patterns.  See backend/services/entity_query.py for usage."
        )
    else:
        print(
            f"[PASS] Tier-2: scanned {len(warn_files)} file(s) — "
            "all raw-query files already import entity_base_q."
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
