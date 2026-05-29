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
# COAUTHOR_V2_SHADOW — V2 artifacts computed alongside legacy (no read impact);
#                      default ON during the F3 build-out so data accumulates
#                      before the read path is switched over.
# COAUTHOR_V2_READ   — network/author endpoints serve from V2 tables.
COAUTHOR_V2_WRITE = _flag("COAUTHOR_V2_WRITE", "false")
COAUTHOR_V2_SHADOW = _flag("COAUTHOR_V2_SHADOW", "true")
COAUTHOR_V2_READ = _flag("COAUTHOR_V2_READ", "false")
