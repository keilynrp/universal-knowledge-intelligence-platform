"""Resilient wrapper around a single authority resolver (Phase 1, Task 2).

Composes a circuit breaker with bounded exponential backoff retry. The wrapper
preserves the resolver contract used by the orchestrator: ``resolve`` never
raises and returns ``[]`` when the source cannot be reached.
"""
from __future__ import annotations

import logging
import random
import time

from backend.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)


class ResilientResolver:
    """Wrap a resolver with a circuit breaker + bounded retry.

    A single ``resolve`` call retries transient failures up to ``max_attempts``
    times before surfacing one failure to the breaker. When the breaker is OPEN
    the call short-circuits to ``[]`` without touching the underlying resolver.
    """

    def __init__(
        self,
        resolver,
        breaker: CircuitBreaker,
        max_attempts: int = 2,
        base_delay: float = 0.5,
    ):
        self.resolver = resolver
        self.source_name = resolver.source_name
        self.breaker = breaker
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    def resolve(self, value: str, entity_type: str):
        try:
            return self.breaker.call(self._resolve_with_retry, value, entity_type)
        except CircuitOpenError:
            logger.info(
                "Circuit open for '%s' — returning [] for '%s'",
                self.source_name,
                value,
            )
            return []
        except Exception as exc:  # defensive: contract is never-raise
            logger.warning(
                "ResilientResolver '%s' final failure: %s", self.source_name, exc
            )
            return []

    def _resolve_with_retry(self, value: str, entity_type: str):
        last_exc: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self.resolver.resolve(value, entity_type)
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_attempts:
                    delay = self.base_delay * (2 ** (attempt - 1)) + random.uniform(
                        0, self.base_delay
                    )
                    if delay > 0:
                        time.sleep(delay)
        raise last_exc if last_exc else RuntimeError("resolver failed")
