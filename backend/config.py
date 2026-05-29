"""Centralized runtime feature flags.

Flags are read from environment variables at import time. Restart the process
to pick up changes. Keep this module dependency-free so it can be imported
from anywhere (workers, routers, scripts) without import cycles.
"""
from __future__ import annotations

import os


def _flag(name: str, default: str = "false") -> bool:
    """Parse a boolean environment flag. Truthy iff value == 'true' (case-insensitive)."""
    return os.getenv(name, default).strip().lower() == "true"


# ── Coauthorship V2 refactor rollout flags (Sprint 2026-05-28) ──────────────
# COAUTHOR_V2_WRITE  — worker materializes V2 authors/edges on enrichment.
# COAUTHOR_V2_SHADOW — V2 artifacts computed alongside legacy (no read impact).
# COAUTHOR_V2_READ   — network/author endpoints serve from V2 tables.
#
# F5 cutover (2026-05-29): WRITE + READ now default ON — V2 is the live path.
# The legacy code + these flags are KEPT one release as a safety net: set
# COAUTHOR_V2_READ=false (and/or WRITE=false) in the environment to fall back.
# REQUIRED at deploy: run `python -m backend.scripts.migrate_coauthor_graph`
# once to backfill V2 tables, or the graph reads empty until the worker
# re-materializes on the next enrichment pass.
# Tests pin these OFF (see conftest) so suites stay deterministic and opt in
# per-case via the write_on / read_on fixtures.
COAUTHOR_V2_WRITE = _flag("COAUTHOR_V2_WRITE", "true")
COAUTHOR_V2_SHADOW = _flag("COAUTHOR_V2_SHADOW", "true")
COAUTHOR_V2_READ = _flag("COAUTHOR_V2_READ", "true")
