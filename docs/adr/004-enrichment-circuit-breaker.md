# ADR-004: Enrichment Circuit Breaker

## Status

Accepted

## Date

2026-03-06

## Context

The enrichment worker makes HTTP calls to external APIs (Web of Science, OpenAlex, Google Scholar). These APIs occasionally become unavailable or rate-limit aggressively. Without protection, the worker would exhaust retries, block the queue, and potentially trigger IP bans.

## Decision

Implement a circuit breaker pattern (`backend/circuit_breaker.py`) with three states:

- **CLOSED** — Normal operation. Track failure count within a sliding window.
- **OPEN** — After N failures within the window (default: 3 of 5), reject all calls immediately for a recovery period (default: 60s for WoS/OpenAlex, 120s for Scholar).
- **HALF_OPEN** — After recovery period, allow one probe call. Success → CLOSED; failure → OPEN again.

The circuit breaker is thread-safe and integrated into the enrichment worker for each external provider independently.

## Consequences

- **Easier:** System self-heals from transient API failures; queue doesn't block; no manual intervention needed for temporary outages.
- **Harder:** During OPEN state, enrichment for affected provider is skipped (entities remain pending until circuit closes).

## References

- Implementation: `backend/circuit_breaker.py`
- Tests: `tests/test_circuit_breaker.py` (20 tests)
- Sprint 3 implementation notes
