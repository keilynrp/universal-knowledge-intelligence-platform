"""Durable background job runtime (ADR-007).

Broker-free, at-least-once PostgreSQL lease queue. This package owns the finite
state machine, the producer/claim/lease/retry/cancel/replay/recovery services,
and the sanitized audit trail. Handlers must be idempotent.
"""

from .states import (
    JobStatus,
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    InvalidTransition,
    assert_transition,
    is_terminal,
)

__all__ = [
    "JobStatus",
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATES",
    "InvalidTransition",
    "assert_transition",
    "is_terminal",
]
