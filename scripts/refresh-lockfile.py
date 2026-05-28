#!/usr/bin/env python3
"""
Refresh frontend/package-lock.json without losing platform-specific
optional packages that npm-on-Windows tends to strip (e.g. @emnapi/*).

Strategy:
  1. Read the lockfile from `origin/main` (assumed to be CI-green) as the
     base — it has the full Linux + macOS + Windows package set.
  2. Read the working-tree lockfile (post local `npm install`) for the new
     entries the dev actually added.
  3. Merge: take base, layer in new packages + updated root devDeps /
     dependencies, write the result back.

Run this after `npm install --save[-dev] <pkg>` on Windows when the next
`npm ci` would otherwise fail with EUSAGE / missing-package errors.

Usage:
  python scripts/refresh-lockfile.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOCK = REPO / "frontend" / "package-lock.json"
BASE_REF = "origin/main"


def load_git(ref: str, path: str) -> dict:
    try:
        raw = subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True, cwd=REPO)
    except subprocess.CalledProcessError as exc:
        sys.exit(f"Cannot read {path} at {ref}: {exc}")
    return json.loads(raw)


def main() -> int:
    if not LOCK.exists():
        sys.exit(f"Missing {LOCK}")
    head = json.loads(LOCK.read_text(encoding="utf-8"))
    base = load_git(BASE_REF, "frontend/package-lock.json")

    base_pkgs = base.get("packages", {})
    head_pkgs = head.get("packages", {})

    # Add any new entries from working-tree lockfile.
    added: list[str] = []
    for k, v in head_pkgs.items():
        if k not in base_pkgs:
            base_pkgs[k] = v
            added.append(k)

    # Carry over root devDeps / deps from working tree (the dev's intent).
    base_root = base_pkgs.get("", {})
    head_root = head_pkgs.get("", {})
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        if key in head_root:
            merged = dict(base_root.get(key, {}))
            merged.update(head_root[key])
            base_root[key] = merged
    base_pkgs[""] = base_root

    # Sync top-level metadata.
    for key in ("name", "version", "lockfileVersion", "requires"):
        if key in head:
            base[key] = head[key]

    LOCK.write_text(
        json.dumps(base, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Merged {len(added)} new package entries into {LOCK.name}.")
    print("Run `cd frontend && npm ci --dry-run` to verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
