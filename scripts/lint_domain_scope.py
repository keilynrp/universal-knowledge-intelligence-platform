#!/usr/bin/env python3
"""
Lint check: enforce the domain-scope contract in backend router files.

Fails with exit code 1 if any Python file under backend/routers/ or
backend/enrichment_worker.py contains raw domain scope comparison patterns:
    == "default"
    == "all"
    .domain.is_(None)   (when used for scope purposes, not in tests)

Usage:
    python scripts/lint_domain_scope.py

Returns 0 on success, 1 if violations are found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

# Files / directories to scan
SCAN_TARGETS: list[Path] = [
    ROOT / "backend" / "routers",
    ROOT / "backend" / "enrichment_worker.py",
]

# Patterns that indicate a raw domain scope comparison
_VIOLATION_PATTERNS: list[re.Pattern] = [
    re.compile(r'==\s*"default"'),
    re.compile(r'==\s*"all"'),
    re.compile(r'\.domain\.is_\('),
]

# Lines that are allowed to contain these patterns (e.g. comments, test helpers)
_ALLOWLIST_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*#"),        # comment lines
    re.compile(r"resolve_domain_filter"),  # the resolver itself
]

# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------


def _collect_files() -> list[Path]:
    files: list[Path] = []
    for target in SCAN_TARGETS:
        if target.is_file() and target.suffix == ".py":
            files.append(target)
        elif target.is_dir():
            files.extend(target.rglob("*.py"))
    return sorted(files)


def _is_allowlisted(line: str) -> bool:
    return any(p.search(line) for p in _ALLOWLIST_PATTERNS)


def _scan_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, line_content) for violations."""
    violations: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"  [WARN] Cannot read {path}: {e}", file=sys.stderr)
        return violations
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _is_allowlisted(line):
            continue
        for pattern in _VIOLATION_PATTERNS:
            if pattern.search(line):
                violations.append((lineno, line.rstrip()))
                break  # one violation per line is enough
    return violations


def main() -> int:
    files = _collect_files()
    total_violations = 0

    for path in files:
        violations = _scan_file(path)
        if violations:
            rel = path.relative_to(ROOT)
            print(f"\n{rel}:")
            for lineno, line in violations:
                print(f"  line {lineno}: {line.strip()}")
            total_violations += len(violations)

    if total_violations:
        print(
            f"\n[FAIL] {total_violations} domain-scope violation(s) found. "
            "Use resolve_domain_filter(parse_scope(domain_id), model) instead of "
            'raw == "all" / == "default" / .domain.is_(None) comparisons.'
        )
        return 1

    print(f"[PASS] Scanned {len(files)} file(s) — zero domain-scope violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
