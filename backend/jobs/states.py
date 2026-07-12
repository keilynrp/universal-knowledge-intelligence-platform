"""Finite state machine for durable background jobs (ADR-007, task 2.1).

    queued -> running -> succeeded
    running -> retry_wait -> queued        (transient failure / expired lease)
    running -> failed                      (terminal failure / attempts exhausted)
    {pending, queued, retry_wait} -> cancelled

``pending`` is reserved for producers that persist then publish separately; the
PostgreSQL queue enqueues transactionally straight to ``queued``. Transitions are
compare-and-set; an invalid transition fails closed (``InvalidTransition``).
"""
from __future__ import annotations


class JobStatus:
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRY_WAIT = "retry_wait"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES: frozenset[str] = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    JobStatus.PENDING: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
    JobStatus.QUEUED: frozenset({JobStatus.RUNNING, JobStatus.CANCELLED}),
    JobStatus.RUNNING: frozenset(
        {JobStatus.SUCCEEDED, JobStatus.RETRY_WAIT, JobStatus.FAILED}
    ),
    JobStatus.RETRY_WAIT: frozenset({JobStatus.QUEUED, JobStatus.CANCELLED}),
    JobStatus.SUCCEEDED: frozenset(),
    JobStatus.FAILED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


class InvalidTransition(Exception):
    """Raised when a job status transition is not permitted by the FSM."""


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATES


def assert_transition(current: str, target: str) -> None:
    """Raise ``InvalidTransition`` unless ``current -> target`` is allowed."""
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransition(f"illegal job transition: {current} -> {target}")
