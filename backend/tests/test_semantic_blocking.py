"""Tests for semantic candidate generation (Phase 2, Task 8).

Semantic blocking surfaces pairs that are *semantically* equivalent but
lexically distant ("IBM" vs "International Business Machines"). It is gated
behind ``UKIP_ENABLE_SEMANTIC_BLOCKING`` and must degrade to lexical-only
clustering whenever embeddings are unavailable (no Chroma, no embedder,
network error) — never raise.
"""
from __future__ import annotations

import pytest

from backend.clustering.blocking import cluster_values
from backend.clustering.semantic import SemanticIndex, semantic_blocking_enabled


def _fake_embed(text: str) -> list[float]:
    """Toy embedder: synonyms map to near-identical unit-ish vectors."""
    table = {
        "IBM": [1.0, 0.0, 0.0],
        "International Business Machines": [0.99, 0.0157, 0.0],
        "Apple Inc": [0.0, 1.0, 0.0],
    }
    return table.get(text, [0.0, 0.0, 1.0])


def test_index_returns_semantic_neighbor():
    idx = SemanticIndex.build(
        ["IBM", "International Business Machines", "Apple Inc"], _fake_embed
    )
    nbrs = idx.neighbors("IBM", k=2, min_similarity=0.9)
    assert "International Business Machines" in nbrs
    assert "Apple Inc" not in nbrs


def test_build_skips_failed_embeddings():
    def flaky(text: str) -> list[float]:
        if text == "boom":
            raise RuntimeError("no embedding")
        return [1.0, 0.0]

    idx = SemanticIndex.build(["ok", "boom"], flaky)
    assert "boom" not in idx.values
    assert "ok" in idx.values


def test_neighbors_unknown_value_returns_empty():
    idx = SemanticIndex.build(["IBM"], _fake_embed)
    assert idx.neighbors("Nonexistent") == []


def test_empty_index_returns_no_neighbors():
    idx = SemanticIndex.build([], _fake_embed)
    assert idx.values == []
    assert idx.neighbors("anything") == []


def test_flag_off_by_default(monkeypatch):
    monkeypatch.delenv("UKIP_ENABLE_SEMANTIC_BLOCKING", raising=False)
    assert semantic_blocking_enabled() is False


def test_flag_on_when_truthy(monkeypatch):
    monkeypatch.setenv("UKIP_ENABLE_SEMANTIC_BLOCKING", "true")
    assert semantic_blocking_enabled() is True


def test_cluster_values_uses_semantic_neighbors_as_candidates():
    # "IBM" and "International Business Machines" share no lexical block key
    # and have a low token_sort_ratio, so lexical-only keeps them apart.
    vals = ["IBM", "International Business Machines"]
    lexical = cluster_values(vals, threshold=80)
    assert all(len(g) == 1 for g in lexical)

    idx = SemanticIndex.build(vals, _fake_embed)
    with_sem = cluster_values(
        vals, threshold=80, semantic_index=idx, semantic_threshold=0.9
    )
    assert any(len(g) == 2 for g in with_sem)


def test_cluster_values_degrades_when_index_none():
    vals = ["IBM", "International Business Machines"]
    out = cluster_values(vals, threshold=80, semantic_index=None)
    assert all(len(g) == 1 for g in out)


def test_cluster_values_semantic_does_not_overmerge():
    # Apple is semantically far from the IBM pair; must stay its own group.
    vals = ["IBM", "International Business Machines", "Apple Inc"]
    idx = SemanticIndex.build(vals, _fake_embed)
    groups = cluster_values(
        vals, threshold=80, semantic_index=idx, semantic_threshold=0.9
    )
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]
