"""Tests for ResilientResolver (Phase 1, Task 2).

Wraps a single authority resolver with a circuit breaker + bounded retry.
Contract: never raises; returns [] when the source is unavailable.
"""
from backend.authority.resilience import ResilientResolver
from backend.circuit_breaker import CircuitBreaker


class _Flaky:
    source_name = "flaky"

    def __init__(self, fail_times):
        self.fail_times = fail_times
        self.calls = 0

    def resolve(self, value, entity_type):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient")
        return [{"id": value}]


def test_retries_then_succeeds():
    r = ResilientResolver(
        _Flaky(fail_times=1),
        CircuitBreaker("flaky", failure_threshold=5),
        max_attempts=2,
        base_delay=0,
    )
    assert r.resolve("X", "person") == [{"id": "X"}]


def test_returns_empty_after_exhausting_retries():
    flaky = _Flaky(fail_times=99)
    r = ResilientResolver(
        flaky,
        CircuitBreaker("flaky", failure_threshold=5),
        max_attempts=2,
        base_delay=0,
    )
    assert r.resolve("X", "person") == []  # never raises (contract)


def test_open_circuit_short_circuits_to_empty():
    cb = CircuitBreaker("flaky", failure_threshold=1, recovery_timeout=999)
    flaky = _Flaky(fail_times=99)
    r = ResilientResolver(flaky, cb, max_attempts=1, base_delay=0)
    r.resolve("X", "person")  # trips the breaker
    calls_before = flaky.calls
    r.resolve("Y", "person")  # should NOT call the resolver again
    assert flaky.calls == calls_before


def test_preserves_source_name():
    r = ResilientResolver(_Flaky(fail_times=0), CircuitBreaker("flaky"))
    assert r.source_name == "flaky"
