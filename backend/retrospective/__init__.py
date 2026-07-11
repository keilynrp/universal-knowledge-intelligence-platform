"""Retrospective Intelligence Layer (ADR-006).

Governed, append-only historical events and point-in-time snapshots. This package
owns the family/schema-version registry and the idempotent writers. Query,
warehouse export, and ML feature generation are added in later phases.
"""

from .registry import (
    MAX_PAYLOAD_BYTES,
    EventFamily,
    SnapshotFamily,
    UnknownFamily,
    SchemaVersionError,
    event_family,
    snapshot_family,
    EVENT_FAMILIES,
    SNAPSHOT_FAMILIES,
)
from .writer import (
    RetrospectiveWriteError,
    PayloadTooLargeError,
    TenantScopeError,
    record_event,
    record_snapshot,
)

__all__ = [
    "MAX_PAYLOAD_BYTES",
    "EventFamily",
    "SnapshotFamily",
    "UnknownFamily",
    "SchemaVersionError",
    "event_family",
    "snapshot_family",
    "EVENT_FAMILIES",
    "SNAPSHOT_FAMILIES",
    "RetrospectiveWriteError",
    "PayloadTooLargeError",
    "TenantScopeError",
    "record_event",
    "record_snapshot",
]
