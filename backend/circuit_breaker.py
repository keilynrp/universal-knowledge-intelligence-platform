"""
Circuit Breaker for external API calls (OpenAlex, Scholar, Web of Science).

States:
  CLOSED    — normal operation, requests pass through.
  OPEN      — too many failures; requests are rejected immediately without
               calling the external service.
  HALF_OPEN — after a cool-down, one probe request is allowed to test if
               the service has recovered.

Usage:
    cb = CircuitBreaker(name="openalex", failure_threshold=3, recovery_timeout=60)

    try:
        result = cb.call(my_adapter.search_by_title, query, limit=1)
    except CircuitOpenError:
        # Service is tripped — skip gracefully
        result = []
"""

import logging
import time
from enum import Enum
from threading import Lock
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitOpenError(RuntimeError):
    """Raised when a call is attempted while the circuit is OPEN."""


class CircuitBreaker:
    """
    Thread-safe circuit breaker implementation.

    Parameters
    ----------
    name:
        Human-readable name used in log messages.
    failure_threshold:
        Number of consecutive failures that trip the circuit to OPEN.
    recovery_timeout:
        Seconds to wait in OPEN state before allowing a probe (HALF_OPEN).
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._last_used_time: float = 0.0
        self._lock = Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._current_state()

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_count(self) -> int:
        return self._success_count

    @property
    def last_failure_time(self) -> float:
        return self._last_failure_time

    @property
    def last_used_time(self) -> float:
        return self._last_used_time

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute *func* if the circuit allows it.
        Raises CircuitOpenError if the circuit is OPEN (and not yet ready for
        a probe attempt).
        """
        with self._lock:
            state = self._current_state()

            if state == CircuitState.OPEN:
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is OPEN — skipping external call."
                )

            if state == CircuitState.HALF_OPEN:
                logger.info(
                    f"Circuit '{self.name}' is HALF_OPEN — sending probe request."
                )
            self._last_used_time = time.time()

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            self._record_failure()
            raise exc

        self._record_success()
        return result

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED (useful in tests / admin ops)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = 0.0
            self._last_used_time = 0.0
        logger.info(f"Circuit '{self.name}' manually reset to CLOSED.")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _current_state(self) -> CircuitState:
        """Must be called while holding self._lock."""
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    f"Circuit '{self.name}' moved to HALF_OPEN after "
                    f"{elapsed:.1f}s cool-down."
                )
        return self._state

    def _record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if (
                self._state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)
                and self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit '{self.name}' tripped to OPEN after "
                    f"{self._failure_count} failure(s)."
                )

    def _record_success(self) -> None:
        with self._lock:
            self._success_count += 1
            if self._state != CircuitState.CLOSED:
                logger.info(
                    f"Circuit '{self.name}' recovered — returning to CLOSED."
                )
            self._state = CircuitState.CLOSED
            self._failure_count = 0
