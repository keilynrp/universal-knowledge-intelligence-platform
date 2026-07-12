"""Event-family and schema-version registry for the retrospective layer.

Pure, in-memory governance metadata (no DB). Each family declares the current
``schema_version`` for its ``event_type`` / ``snapshot_type``. History is
immutable: a schema change is a **new version**, never an in-place rewrite, and
readers must tolerate multiple versions of the same family coexisting.

Rules enforced here and by the writer (see ADR-006 companion inventory):
- Writers may only emit a *registered* family at its *current* schema version
  (an explicitly supplied version must match the registry).
- Payloads are bounded to ``MAX_PAYLOAD_BYTES`` (32 KB) serialized JSON.
"""
from __future__ import annotations

from dataclasses import dataclass


# Hard cap on serialized JSON payload size per event/snapshot (task 1.4).
MAX_PAYLOAD_BYTES = 32 * 1024


class UnknownFamily(KeyError):
    """Raised when an event_type / snapshot_type is not in the registry."""


class SchemaVersionError(ValueError):
    """Raised when a supplied schema_version does not match the registry."""


@dataclass(frozen=True)
class EventFamily:
    """Governed retrospective event family."""

    event_type: str
    current_version: int
    description: str


@dataclass(frozen=True)
class SnapshotFamily:
    """Governed retrospective snapshot family."""

    snapshot_type: str
    current_version: int
    description: str


# ── Initial event families (design.md; Phase 3 emits the first slice) ────────
# Only the high-value initial slice is registered now; more families are added
# as their writers ship. Registering a family is a governance act — do not emit
# an unregistered type.
_EVENT_FAMILY_LIST = (
    EventFamily("journal_metric.computed", 1, "Journal NIF/APC metric first computed."),
    EventFamily("journal_metric.recomputed", 1, "Journal metric recomputed/backfilled."),
    EventFamily("enrichment.requested", 1, "Enrichment requested for an entity."),
    EventFamily("enrichment.completed", 1, "Enrichment completed."),
    EventFamily("enrichment.failed", 1, "Enrichment failed."),
    EventFamily("authority.candidate_created", 1, "Authority candidate created."),
    EventFamily("authority.accepted", 1, "Authority candidate accepted by reviewer."),
    EventFamily("authority.rejected", 1, "Authority candidate rejected by reviewer."),
    EventFamily("authority.nil_marked", 1, "Authority marked NIL (not in list)."),
)

# ── Initial snapshot families (design.md; Phase 3.4 materializes first) ──────
_SNAPSHOT_FAMILY_LIST = (
    SnapshotFamily("journal_metric", 1, "Point-in-time journal metric state."),
    SnapshotFamily("enrichment_coverage", 1, "Point-in-time enrichment coverage."),
    SnapshotFamily("authority_readiness", 1, "Point-in-time authority readiness."),
)


EVENT_FAMILIES: dict[str, EventFamily] = {f.event_type: f for f in _EVENT_FAMILY_LIST}
SNAPSHOT_FAMILIES: dict[str, SnapshotFamily] = {
    f.snapshot_type: f for f in _SNAPSHOT_FAMILY_LIST
}


def event_family(event_type: str) -> EventFamily:
    """Return the registered event family or raise ``UnknownFamily``."""
    try:
        return EVENT_FAMILIES[event_type]
    except KeyError as exc:
        raise UnknownFamily(f"unregistered retrospective event_type: {event_type!r}") from exc


def snapshot_family(snapshot_type: str) -> SnapshotFamily:
    """Return the registered snapshot family or raise ``UnknownFamily``."""
    try:
        return SNAPSHOT_FAMILIES[snapshot_type]
    except KeyError as exc:
        raise UnknownFamily(
            f"unregistered retrospective snapshot_type: {snapshot_type!r}"
        ) from exc


def resolve_event_version(event_type: str, schema_version: int | None) -> int:
    """Resolve/validate the schema version for an event family.

    ``None`` resolves to the registry's current version. A supplied value must
    match the current version (writers may not emit an arbitrary version).
    """
    family = event_family(event_type)
    return _resolve(family.current_version, schema_version, event_type)


def resolve_snapshot_version(snapshot_type: str, schema_version: int | None) -> int:
    """Resolve/validate the schema version for a snapshot family."""
    family = snapshot_family(snapshot_type)
    return _resolve(family.current_version, schema_version, snapshot_type)


def _resolve(current: int, supplied: int | None, family_name: str) -> int:
    if supplied is None:
        return current
    if supplied != current:
        raise SchemaVersionError(
            f"{family_name}: schema_version {supplied} does not match current "
            f"registered version {current}"
        )
    return supplied
