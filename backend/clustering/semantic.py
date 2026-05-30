"""Semantic candidate generation (Phase 2, Task 8).

Lexical blocking (fingerprint / phonetic / token prefix) misses pairs that
are semantically equivalent but lexically distant — e.g. ``"IBM"`` vs
``"International Business Machines"`` share no block key and have a low
``token_sort_ratio``. When semantic blocking is enabled and an embedding
backed index is available, each value's nearest semantic neighbors become
extra comparison candidates so the clusterer can union them.

Design goals:
- **Graceful degradation.** Any failure (no Chroma, no embedder, network
  error, a single value that fails to embed) reduces to lexical-only. The
  index is built defensively and never raises on per-value embedding errors.
- **Injectable embedder.** The index is built from an ``embed_fn`` callable
  so it is trivially testable with a toy embedder and decoupled from the
  concrete ChromaDB / LLM adapter used in production.
- **Opt-in.** Gated behind ``UKIP_ENABLE_SEMANTIC_BLOCKING``; default off
  until the evaluation harness (Task 9) validates the switch.
"""
from __future__ import annotations

import logging
import os
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

EmbeddingFn = Callable[[str], "list[float]"]

# Default cosine-similarity floor for treating two values as the same entity.
_DEFAULT_MIN_SIMILARITY = 0.85
_TRUE_VALUES = {"1", "true", "yes", "on"}


def semantic_blocking_enabled() -> bool:
    """Whether semantic blocking is switched on via environment flag."""
    return os.environ.get("UKIP_ENABLE_SEMANTIC_BLOCKING", "").strip().lower() in _TRUE_VALUES


def build_embed_fn(db) -> Optional[EmbeddingFn]:
    """Resolve an embedding callable from the active AI integration, or None.

    Returns ``None`` (so callers degrade to lexical-only) when no integration
    is active, the adapter cannot be built, or it exposes no ``get_embedding``.
    Imports are local to avoid a router/analytics import cycle.
    """
    try:
        from backend.analytics.rag_engine import _build_adapter
        from backend.routers.deps import _get_active_integration

        integration = _get_active_integration(db)
        adapter = _build_adapter(integration)
        if adapter is None or not hasattr(adapter, "get_embedding"):
            return None
        return adapter.get_embedding  # type: ignore[no-any-return]
    except Exception as exc:  # defensive: never block lexical clustering
        logger.debug("build_embed_fn unavailable: %s", exc)
        return None


def maybe_build_index(db, values: list[str]) -> Optional["SemanticIndex"]:
    """Build a SemanticIndex when semantic blocking is enabled and feasible.

    Returns ``None`` when the flag is off, there are too few values to matter,
    or no embedder is available — letting the clusterer stay lexical-only.
    """
    if not semantic_blocking_enabled() or len(values) < 2:
        return None
    embed_fn = build_embed_fn(db)
    if embed_fn is None:
        return None
    try:
        return SemanticIndex.build(values, embed_fn)
    except Exception as exc:  # defensive
        logger.debug("semantic index build failed: %s", exc)
        return None


class SemanticIndex:
    """In-memory cosine-similarity index over a fixed set of string values.

    Vectors are L2-normalized at construction so neighbor lookup is a single
    matrix-vector product. Values whose embedding fails are skipped, so the
    index always reflects only successfully-embedded values.
    """

    def __init__(self, values: list[str], matrix: Optional[np.ndarray]) -> None:
        self._values = values
        # matrix shape: (n_values, dim), L2-normalized rows. None when empty.
        self._matrix = matrix
        self._index = {value: i for i, value in enumerate(values)}

    @property
    def values(self) -> list[str]:
        return list(self._values)

    @classmethod
    def build(cls, values: list[str], embed_fn: EmbeddingFn) -> "SemanticIndex":
        """Embed ``values`` with ``embed_fn``, skipping any that fail.

        De-duplicates while preserving order. Never raises: a value whose
        embedding raises (or returns an unusable vector) is simply omitted.
        """
        unique = list(dict.fromkeys(values))
        kept: list[str] = []
        vectors: list[np.ndarray] = []
        for value in unique:
            try:
                raw = embed_fn(value)
            except Exception as exc:  # defensive: degrade to lexical-only
                logger.debug("semantic embed failed for %r: %s", value, exc)
                continue
            vec = cls._normalize(raw)
            if vec is None:
                continue
            kept.append(value)
            vectors.append(vec)

        matrix = np.vstack(vectors) if vectors else None
        return cls(kept, matrix)

    @staticmethod
    def _normalize(raw: object) -> Optional[np.ndarray]:
        try:
            arr = np.asarray(raw, dtype=float)
        except (TypeError, ValueError):
            return None
        if arr.ndim != 1 or arr.size == 0:
            return None
        norm = float(np.linalg.norm(arr))
        if norm == 0.0 or not np.isfinite(norm):
            return None
        return arr / norm

    def neighbors(
        self,
        value: str,
        k: int = 5,
        min_similarity: float = _DEFAULT_MIN_SIMILARITY,
    ) -> list[str]:
        """Return up to ``k`` values most cosine-similar to ``value``.

        Excludes ``value`` itself and anything below ``min_similarity``.
        Returns ``[]`` for unknown values or an empty index.
        """
        if self._matrix is None or value not in self._index:
            return []
        query = self._matrix[self._index[value]]
        sims = self._matrix @ query  # cosine sim (rows already normalized)
        order = np.argsort(-sims)
        out: list[str] = []
        for i in order:
            candidate = self._values[i]
            if candidate == value:
                continue
            if float(sims[i]) < min_similarity:
                break  # argsort is descending; nothing better remains
            out.append(candidate)
            if len(out) >= k:
                break
        return out
