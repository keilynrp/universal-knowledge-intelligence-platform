"""Best-effort emission of retrospective events from operational workflows.

Phase 3 wiring layer (ADR-006). Operational code calls these helpers at governed
decision points; they translate operational state into governed retrospective
events via the Phase 2 writer.

Design contract:
- **Non-fatal.** A retrospective emission failure MUST NOT break the operational
  workflow that triggered it. Every helper swallows and logs its own errors.
- **Flag-gated.** Emission is off unless ``UKIP_RETRO_EVENTS`` is truthy, so the
  operational path is unchanged until the layer is deliberately enabled (declare
  the flag in the prod compose file when turning it on — see EPIC lesson on
  env-var/compose parity).
- **Same session.** Helpers reuse the caller's session. The writer validates
  family/schema/payload *before* any DB write and pre-checks existence before
  insert, so in a single-threaded batch it never triggers a session-wide
  rollback that could disturb operational (uncommitted) changes.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import writer

logger = logging.getLogger(__name__)


def retro_events_enabled() -> bool:
    """Feature flag — defaults OFF. Set ``UKIP_RETRO_EVENTS=1`` to enable."""
    return os.environ.get("UKIP_RETRO_EVENTS", "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


def emit_journal_metric_normalized(
    db: Session,
    *,
    org_id: Optional[int],
    issn_l: str,
    new_nif: float,
    prior_nif: Optional[float],
    nif_field: str,
    field_median: Optional[float],
    occurred_at: datetime,
    source_id: Optional[str] = None,
) -> None:
    """Emit a journal-metric NIF (re)computation event (task 3.1).

    ``journal_metric.computed`` on first computation (``prior_nif is None``),
    otherwise ``journal_metric.recomputed``. Idempotent within a single
    normalization run (keyed by ISSN + ``occurred_at``); a later run at a
    different time is a distinct, expected event.
    """
    if not retro_events_enabled():
        return
    event_type = (
        "journal_metric.computed" if prior_nif is None else "journal_metric.recomputed"
    )
    try:
        writer.record_event(
            db,
            event_type=event_type,
            org_id=org_id,
            domain_object_type="journal",
            domain_object_id=f"issn:{issn_l}",
            occurred_at=occurred_at,
            source="journal_normalization",
            actor_type="job",
            idempotency_key=f"{issn_l}:{occurred_at.isoformat()}",
            payload={
                "nif": new_nif,
                "prior_nif": prior_nif,
                "nif_field": nif_field,
                "field_median": field_median,
            },
            lineage={"source_id": source_id} if source_id else None,
        )
    except Exception:  # noqa: BLE001 — non-fatal by contract
        logger.warning(
            "retrospective emit failed for journal %s (%s); continuing",
            issn_l,
            event_type,
            exc_info=True,
        )
