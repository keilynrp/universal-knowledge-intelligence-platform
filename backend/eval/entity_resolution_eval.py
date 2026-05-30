"""Entity-resolution quality harness (Phase 2, Task 9).

Clusters a small labeled fixture of surface forms, derives the set of predicted
same-cluster pairs, and scores them against gold same-entity pairs to produce
precision / recall / F1. This is the objective gate for flipping clustering
behavior (e.g. enabling blocking by default): a change must not drop F1 below
the recorded baseline.

Usage:
    from backend.eval.entity_resolution_eval import evaluate, evaluate_sweep
    print(evaluate(algorithm="blocking", threshold=80))
    for row in evaluate_sweep():
        print(row)
"""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Iterable

from thefuzz import fuzz, process

from backend.clustering.blocking import cluster_values

_FIXTURE = Path(__file__).parent / "fixtures" / "gold_pairs.json"

Pair = tuple[str, str]


def _pair(a: str, b: str) -> Pair:
    return (a, b) if a <= b else (b, a)


def load_gold(gold_path: str | Path | None = None) -> tuple[list[str], set[Pair]]:
    """Load fixture values and the gold set of same-entity pairs."""
    path = Path(gold_path) if gold_path else _FIXTURE
    data = json.loads(path.read_text(encoding="utf-8"))
    values: list[str] = list(dict.fromkeys(data["values"]))
    gold = {_pair(a, b) for a, b in data["matches"]}
    return values, gold


def _greedy_clusters(values: list[str], threshold: int) -> list[list[str]]:
    """Replicate the legacy greedy token_sort grouping (the baseline)."""
    ordered = sorted(values, key=len, reverse=True)
    processed: set[str] = set()
    groups: list[list[str]] = []
    for val in ordered:
        if val in processed:
            continue
        matches = process.extract(val, ordered, scorer=fuzz.token_sort_ratio, limit=50)
        members = [m[0] for m in matches if m[1] >= threshold]
        groups.append(members)
        processed.update(members)
    return groups


def _cluster(values: list[str], algorithm: str, threshold: int) -> list[list[str]]:
    if algorithm == "blocking":
        return cluster_values(values, threshold)
    if algorithm in ("legacy", "greedy", "token_sort"):
        return _greedy_clusters(values, threshold)
    raise ValueError(f"Unknown algorithm: {algorithm!r}")


def _predicted_pairs(clusters: list[list[str]]) -> set[Pair]:
    pairs: set[Pair] = set()
    for cluster in clusters:
        for a, b in combinations(sorted(set(cluster)), 2):
            pairs.add(_pair(a, b))
    return pairs


def evaluate(
    algorithm: str = "blocking",
    threshold: int = 80,
    gold_path: str | Path | None = None,
) -> dict:
    """Score one (algorithm, threshold) combination against the gold fixture."""
    values, gold = load_gold(gold_path)
    predicted = _predicted_pairs(_cluster(values, algorithm, threshold))

    tp = len(predicted & gold)
    fp = len(predicted - gold)
    fn = len(gold - predicted)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "algorithm": algorithm,
        "threshold": threshold,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def evaluate_sweep(
    algorithms: Iterable[str] = ("legacy", "blocking"),
    thresholds: Iterable[int] = (70, 75, 80, 85, 90),
    gold_path: str | Path | None = None,
) -> list[dict]:
    """Run `evaluate` across the cartesian product of algorithms × thresholds."""
    return [
        evaluate(algorithm=algo, threshold=t, gold_path=gold_path)
        for algo in algorithms
        for t in thresholds
    ]


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    header = f"{'algorithm':<10} {'thr':>4} {'prec':>6} {'rec':>6} {'f1':>6}  tp/fp/fn"
    print(header)
    print("-" * len(header))
    for row in evaluate_sweep():
        print(
            f"{row['algorithm']:<10} {row['threshold']:>4} "
            f"{row['precision']:>6} {row['recall']:>6} {row['f1']:>6}  "
            f"{row['tp']}/{row['fp']}/{row['fn']}"
        )
