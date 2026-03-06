"""
Topic Modeling analyzer — pure Python + DuckDB + numpy, no sklearn/NLTK.

Works on the `enrichment_concepts` column of RawEntity, which stores
concepts as a comma-separated string: "Machine Learning, Neural Network, ...".
"""
from __future__ import annotations

import logging
import math
from collections import Counter
from itertools import combinations
from typing import Any

import pandas as pd

from backend.database import engine
from backend.schema_registry import registry

logger = logging.getLogger(__name__)

# Concepts stored as "A, B, C" — split on ", " then strip each
_SEP = ","


def _parse_concepts(raw: str | None) -> list[str]:
    """Split comma-separated concept string into clean list."""
    if not raw:
        return []
    return [c.strip() for c in raw.split(_SEP) if c.strip()]


def _load_concepts_df(domain_id: str) -> pd.DataFrame:
    """
    Load rows that have enrichment_concepts for the given domain.
    Returns a DataFrame with columns: id, enrichment_concepts, and domain
    categorical fields.
    """
    domain = registry.get_domain(domain_id)
    if domain is None:
        raise ValueError(f"Domain '{domain_id}' not found")

    with engine.connect() as conn:
        df = pd.read_sql(
            "SELECT id, enrichment_concepts FROM raw_entities "
            "WHERE enrichment_concepts IS NOT NULL AND enrichment_concepts != ''",
            conn,
        )
    return df


class TopicAnalyzer:
    """Analyze enrichment_concepts for a given domain."""

    # ── Top topics ──────────────────────────────────────────────────────────

    def top_topics(self, domain_id: str, top_n: int = 30) -> dict[str, Any]:
        """
        Return concept frequencies across all enriched entities.

        Returns:
            {
              "domain_id": str,
              "total_enriched": int,
              "topics": [{"concept": str, "count": int, "pct": float}, ...]
            }
        """
        df = _load_concepts_df(domain_id)
        total_enriched = len(df)

        counter: Counter = Counter()
        for raw in df["enrichment_concepts"]:
            counter.update(_parse_concepts(raw))

        topics = [
            {
                "concept": concept,
                "count": count,
                "pct": round(count / total_enriched * 100, 2) if total_enriched else 0.0,
            }
            for concept, count in counter.most_common(top_n)
        ]

        return {
            "domain_id": domain_id,
            "total_enriched": total_enriched,
            "topics": topics,
        }

    # ── Co-occurrence ────────────────────────────────────────────────────────

    def cooccurrence(self, domain_id: str, top_n: int = 20) -> dict[str, Any]:
        """
        Return concept pairs that most frequently co-occur in the same entity.

        Returns:
            {
              "domain_id": str,
              "total_enriched": int,
              "pairs": [{"concept_a": str, "concept_b": str, "count": int, "pmi": float}, ...]
            }
        """
        df = _load_concepts_df(domain_id)
        total_enriched = len(df)

        pair_counter: Counter = Counter()
        concept_counter: Counter = Counter()

        for raw in df["enrichment_concepts"]:
            concepts = _parse_concepts(raw)
            concept_counter.update(concepts)
            # Each pair counted once per entity (sorted to canonicalize)
            for a, b in combinations(sorted(set(concepts)), 2):
                pair_counter[(a, b)] += 1

        # Pointwise Mutual Information: log2(P(a,b) / (P(a)*P(b)))
        # P(a) = concept_counter[a] / total_enriched
        pairs = []
        for (a, b), co_count in pair_counter.most_common(top_n * 5):
            if total_enriched == 0:
                pmi = 0.0
            else:
                p_a = concept_counter[a] / total_enriched
                p_b = concept_counter[b] / total_enriched
                p_ab = co_count / total_enriched
                if p_a > 0 and p_b > 0 and p_ab > 0:
                    pmi = round(math.log2(p_ab / (p_a * p_b)), 3)
                else:
                    pmi = 0.0
            pairs.append({
                "concept_a": a,
                "concept_b": b,
                "count": co_count,
                "pmi": pmi,
            })

        # Sort by raw count for UI (most frequent pairs first), cap at top_n
        pairs.sort(key=lambda x: x["count"], reverse=True)
        pairs = pairs[:top_n]

        return {
            "domain_id": domain_id,
            "total_enriched": total_enriched,
            "pairs": pairs,
        }

    # ── Topic clusters ───────────────────────────────────────────────────────

    def topic_clusters(self, domain_id: str, n_clusters: int = 6) -> dict[str, Any]:
        """
        Group concepts into clusters using greedy PMI-based single-linkage.

        Algorithm (pure Python, no sklearn):
        1. Build concept co-occurrence graph (edges weighted by co_count).
        2. Greedy: pick the top-N concepts by frequency as seeds.
        3. Assign each remaining concept to the seed it co-occurs with most.
        4. Return clusters as lists of {concept, count} dicts.

        Returns:
            {
              "domain_id": str,
              "n_clusters": int,
              "clusters": [
                {"id": int, "seed": str, "size": int,
                 "members": [{"concept": str, "count": int}, ...]}
              ]
            }
        """
        df = _load_concepts_df(domain_id)

        pair_counter: Counter = Counter()
        concept_counter: Counter = Counter()

        for raw in df["enrichment_concepts"]:
            concepts = _parse_concepts(raw)
            concept_counter.update(concepts)
            for a, b in combinations(sorted(set(concepts)), 2):
                pair_counter[(a, b)] += 1

        if not concept_counter:
            return {"domain_id": domain_id, "n_clusters": 0, "clusters": []}

        # Seeds = top-n_clusters concepts by frequency
        top_concepts = [c for c, _ in concept_counter.most_common()]
        seeds = top_concepts[:n_clusters]

        # Assign each concept to the seed with highest co-occurrence score
        cluster_map: dict[str, str] = {s: s for s in seeds}

        for concept in top_concepts[n_clusters:]:
            best_seed = None
            best_score = -1
            for seed in seeds:
                key = tuple(sorted([concept, seed]))
                score = pair_counter.get(key, 0)  # type: ignore[arg-type]
                if score > best_score:
                    best_score = score
                    best_seed = seed
            if best_seed is not None:
                cluster_map[concept] = best_seed

        # Build output clusters
        clusters_dict: dict[str, list[dict]] = {s: [] for s in seeds}
        for concept, seed in cluster_map.items():
            clusters_dict[seed].append({
                "concept": concept,
                "count": concept_counter[concept],
            })

        clusters = []
        for idx, seed in enumerate(seeds):
            members = sorted(clusters_dict[seed], key=lambda x: x["count"], reverse=True)
            clusters.append({
                "id": idx,
                "seed": seed,
                "size": len(members),
                "members": members,
            })

        return {
            "domain_id": domain_id,
            "n_clusters": len(clusters),
            "clusters": clusters,
        }
