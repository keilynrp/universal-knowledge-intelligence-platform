"""Tests for the entity-resolution evaluation harness (Phase 2, Task 9).

The harness clusters a small labeled fixture, derives predicted same-cluster
pairs, and scores them against gold matches. It gates the Phase-2 switch:
blocking must not regress below the recorded F1 baseline.
"""
from __future__ import annotations

from backend.eval.entity_resolution_eval import evaluate, evaluate_sweep, load_gold


def test_gold_fixture_loads():
    values, gold = load_gold()
    assert len(values) >= 12
    assert len(gold) >= 5
    # Every gold pair references known values.
    flat = set(values)
    for a, b in gold:
        assert a in flat and b in flat


def test_metrics_have_expected_keys():
    m = evaluate(algorithm="blocking", threshold=80)
    for key in ("precision", "recall", "f1", "tp", "fp", "fn"):
        assert key in m
    assert 0.0 <= m["precision"] <= 1.0
    assert 0.0 <= m["recall"] <= 1.0
    assert 0.0 <= m["f1"] <= 1.0


def test_blocking_does_not_regress_below_baseline():
    metrics = evaluate(algorithm="blocking", threshold=80)
    assert metrics["f1"] >= 0.75  # baseline gate


def test_blocking_matches_or_beats_legacy_recall():
    # Blocking is transitive + order-independent, so it should never have
    # *lower* recall than the legacy greedy grouping on the same fixture.
    blocking = evaluate(algorithm="blocking", threshold=80)
    legacy = evaluate(algorithm="legacy", threshold=80)
    assert blocking["recall"] >= legacy["recall"]


def test_sweep_returns_rows_for_each_combo():
    rows = evaluate_sweep(algorithms=("legacy", "blocking"), thresholds=(75, 85))
    assert len(rows) == 4
    assert {r["algorithm"] for r in rows} == {"legacy", "blocking"}
    assert {r["threshold"] for r in rows} == {75, 85}
