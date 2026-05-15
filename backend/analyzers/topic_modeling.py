"""
Topic Modeling analyzer — pure Python + DuckDB + numpy, no sklearn/NLTK.

Works on the `enrichment_concepts` column of RawEntity, which stores
concepts as a comma-separated string: "Machine Learning, Neural Network, ...".
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any

import pandas as pd
from sqlalchemy import text

from backend.database import engine
from backend.schema_registry import registry
from backend.tenant_access import add_org_sql_filter

logger = logging.getLogger(__name__)

try:
    import Levenshtein as _levenshtein
except Exception:  # pragma: no cover - optional acceleration library
    _levenshtein = None

# Concepts stored as "A, B, C" — split on ", " then strip each
_SEPARATORS_RE = re.compile(r"[;,|]")
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_TRAILING_NOISE_RE = re.compile(r"\s*\([^)]*\)\s*$")
_TOKEN_NOISE_RE = re.compile(r"[^a-z0-9\s-]+")


def _validate_domain(domain_id: str, org_id: int | None = None) -> None:
    if domain_id in {"all", "default"}:
        return
    if registry.get_domain(domain_id) is not None:
        return

    where_clauses = ["domain = :domain_id"]
    params: dict[str, object] = {"domain_id": domain_id}
    add_org_sql_filter(where_clauses, params, org_id)
    with engine.connect() as conn:
        exists = conn.execute(
            text(f"SELECT 1 FROM raw_entities WHERE {' AND '.join(where_clauses)} LIMIT 1"),
            params,
        ).first()
    if exists is None:
        raise ValueError(f"Domain '{domain_id}' not found")


def _parse_concepts(raw: str | None) -> list[str]:
    """Split comma-separated concept string into clean list."""
    if not raw:
        return []
    return [c.strip() for c in _SEPARATORS_RE.split(raw) if c.strip()]


def _concept_key(concept: str) -> str:
    """Return a comparison key for fuzzy concept deduplication."""
    cleaned = _TRAILING_NOISE_RE.sub("", concept).casefold()
    cleaned = _TOKEN_NOISE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _jaro_winkler_similarity(a: str, b: str) -> float:
    if _levenshtein is not None and hasattr(_levenshtein, "jaro_winkler"):
        return float(_levenshtein.jaro_winkler(a, b))
    return SequenceMatcher(None, a, b).ratio()


def _levenshtein_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    max_len = max(len(a), len(b), 1)
    if _levenshtein is not None and hasattr(_levenshtein, "distance"):
        distance = int(_levenshtein.distance(a, b))
    else:
        distance = int(round((1.0 - SequenceMatcher(None, a, b).ratio()) * max_len))
    return max(0.0, 1.0 - distance / max_len)


def _concept_similarity(a: str, b: str) -> float:
    """Blend Jaro-Winkler and Levenshtein signals for conservative merges."""
    key_a = _concept_key(a)
    key_b = _concept_key(b)
    if not key_a or not key_b:
        return 0.0
    if key_a == key_b:
        return 1.0
    jaro = _jaro_winkler_similarity(key_a, key_b)
    levenshtein = _levenshtein_similarity(key_a, key_b)
    return round((jaro * 0.65) + (levenshtein * 0.35), 4)


def _canonicalize_similar_concepts(
    concepts: list[str],
    canonical_counts: Counter,
    min_similarity: float,
) -> tuple[list[str], list[dict[str, Any]]]:
    """
    Merge near-duplicate concepts before pair counting.

    This keeps the most frequent existing label as canonical and only merges
    high-confidence lexical variants, so broad semantic neighbors remain separate.
    """
    canonicalized: list[str] = []
    merges: list[dict[str, Any]] = []
    canonicals = [concept for concept, _ in canonical_counts.most_common()]

    for concept in concepts:
        best: str | None = None
        best_score = 0.0
        for candidate in canonicals:
            score = _concept_similarity(concept, candidate)
            if score > best_score:
                best = candidate
                best_score = score
        if best is not None and best_score >= min_similarity:
            canonical = best
            if _concept_key(concept) != _concept_key(canonical):
                merges.append({
                    "from": concept,
                    "to": canonical,
                    "score": round(best_score, 3),
                    "algorithm": "jaro_winkler+levenshtein",
                })
        else:
            canonical = concept
            canonicals.append(canonical)
        canonical_counts[canonical] += 1
        canonicalized.append(canonical)

    return canonicalized, merges


def _parse_concepts_from_value(value: Any) -> list[str]:
    """Normalize strings/lists/dicts commonly used to store concepts."""
    if value is None:
        return []
    if isinstance(value, str):
        return _parse_concepts(value)
    if isinstance(value, list):
        concepts: list[str] = []
        for item in value:
            if isinstance(item, str):
                concepts.extend(_parse_concepts(item))
            elif isinstance(item, dict):
                label = (
                    item.get("display_name")
                    or item.get("name")
                    or item.get("label")
                    or item.get("concept")
                )
                if label:
                    concepts.extend(_parse_concepts(str(label)))
        return concepts
    if isinstance(value, dict):
        label = (
            value.get("display_name")
            or value.get("name")
            or value.get("label")
            or value.get("concept")
        )
        return _parse_concepts(str(label)) if label else []
    return _parse_concepts(str(value))


def _extract_year(value: Any) -> int | None:
    """Extract a plausible year from ints/strings used in scientific metadata."""
    if value is None:
        return None
    if isinstance(value, int) and 1900 <= value <= 2100:
        return value
    match = _YEAR_RE.search(str(value))
    if not match:
        return None
    year = int(match.group(1))
    return year if 1900 <= year <= 2100 else None


def _extract_record_year(
    attributes_json: str | None,
    primary_label: str | None = None,
    secondary_label: str | None = None,
) -> int | None:
    """Resolve a temporal year from structured attrs first, then text fallback."""
    attrs: dict[str, Any] = {}
    if attributes_json:
        try:
            attrs = json.loads(attributes_json) or {}
        except (ValueError, TypeError):
            attrs = {}

    for key in ("publication_year", "year", "creation_date", "published_at", "date"):
        year = _extract_year(attrs.get(key))
        if year is not None:
            return year

    for fallback in (primary_label, secondary_label):
        year = _extract_year(fallback)
        if year is not None:
            return year

    return None


def _parse_record_concepts(raw: str | None, attributes_json: str | None = None) -> list[str]:
    """Resolve concepts from the normalized enrichment field first, then attrs fallback."""
    direct = _parse_concepts(raw)
    if direct:
        return direct

    attrs: dict[str, Any] = {}
    if attributes_json:
        try:
            attrs = json.loads(attributes_json) or {}
        except (ValueError, TypeError):
            attrs = {}

    concepts: list[str] = []
    for key in ("concepts", "keywords", "topics", "topic", "subjects"):
        concepts.extend(_parse_concepts_from_value(attrs.get(key)))

    deduped: list[str] = []
    seen: set[str] = set()
    for concept in concepts:
        normalized = concept.strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _load_concepts_df(domain_id: str, org_id: int | None = None) -> pd.DataFrame:
    """
    Load rows that have enrichment_concepts for the given domain.
    Returns a DataFrame with columns: id, enrichment_concepts, and domain
    categorical fields.
    """
    where_clauses = [
        "("
        "((enrichment_concepts IS NOT NULL) AND (enrichment_concepts != '')) "
        "OR (attributes_json LIKE '%\"keywords\"%') "
        "OR (attributes_json LIKE '%\"concepts\"%') "
        "OR (attributes_json LIKE '%\"topics\"%') "
        "OR (attributes_json LIKE '%\"subjects\"%')"
        ")"
    ]
    params: dict[str, object] = {}
    if domain_id != "all":
        if domain_id == "default":
            where_clauses.append("(domain = :domain_id OR domain IS NULL)")
        else:
            where_clauses.append("domain = :domain_id")
        params["domain_id"] = domain_id
    add_org_sql_filter(where_clauses, params, org_id)

    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                "SELECT id, enrichment_concepts, attributes_json "
                f"FROM raw_entities WHERE {' AND '.join(where_clauses)}"
            ),
            conn,
            params=params,
        )
    return df


def _load_concepts_timeseries_df(domain_id: str, org_id: int | None = None) -> pd.DataFrame:
    """
    Load concept-bearing rows with enough metadata to derive temporal signals.
    Returns: id, enrichment_concepts, attributes_json, primary_label, secondary_label.
    """
    where_clauses = [
        "("
        "((enrichment_concepts IS NOT NULL) AND (enrichment_concepts != '')) "
        "OR (attributes_json LIKE '%\"keywords\"%') "
        "OR (attributes_json LIKE '%\"concepts\"%') "
        "OR (attributes_json LIKE '%\"topics\"%') "
        "OR (attributes_json LIKE '%\"subjects\"%')"
        ")"
    ]
    params: dict[str, object] = {}
    if domain_id != "all":
        if domain_id == "default":
            where_clauses.append("(domain = :domain_id OR domain IS NULL)")
        else:
            where_clauses.append("domain = :domain_id")
        params["domain_id"] = domain_id
    add_org_sql_filter(where_clauses, params, org_id)

    with engine.connect() as conn:
        df = pd.read_sql(
            text(
                "SELECT id, enrichment_concepts, attributes_json, primary_label, secondary_label "
                f"FROM raw_entities WHERE {' AND '.join(where_clauses)}"
            ),
            conn,
            params=params,
        )
    return df


class TopicAnalyzer:
    """Analyze enrichment_concepts for a given domain."""

    # ── Top topics ──────────────────────────────────────────────────────────

    def top_topics(self, domain_id: str, top_n: int = 30, org_id: int | None = None) -> dict[str, Any]:
        """
        Return concept frequencies across all enriched entities.

        Returns:
            {
              "domain_id": str,
              "total_enriched": int,
              "topics": [{"concept": str, "count": int, "pct": float}, ...]
            }
        """
        _validate_domain(domain_id, org_id=org_id)
        df = _load_concepts_df(domain_id, org_id=org_id)
        total_enriched = len(df)

        counter: Counter = Counter()
        for row in df.itertuples(index=False):
            counter.update(
                _parse_record_concepts(
                    getattr(row, "enrichment_concepts", None),
                    getattr(row, "attributes_json", None),
                )
            )

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
            "total_distinct_concepts": len(counter),
            "topics": topics,
        }

    # ── Co-occurrence ────────────────────────────────────────────────────────

    def cooccurrence(
        self,
        domain_id: str,
        top_n: int = 20,
        org_id: int | None = None,
        normalize_similar: bool = False,
        min_similarity: float = 0.88,
    ) -> dict[str, Any]:
        """
        Return concept pairs that most frequently co-occur in the same entity.

        Returns:
            {
              "domain_id": str,
              "total_enriched": int,
              "pairs": [{"concept_a": str, "concept_b": str, "count": int, "pmi": float}, ...],
              "normalization": {"enabled": bool, "merged_terms": [...]}
            }
        """
        _validate_domain(domain_id, org_id=org_id)
        df = _load_concepts_df(domain_id, org_id=org_id)
        total_enriched = len(df)

        pair_counter: Counter = Counter()
        concept_counter: Counter = Counter()
        canonical_counts: Counter = Counter()
        merged_terms: list[dict[str, Any]] = []

        for row in df.itertuples(index=False):
            concepts = _parse_record_concepts(
                getattr(row, "enrichment_concepts", None),
                getattr(row, "attributes_json", None),
            )
            if normalize_similar:
                concepts, merges = _canonicalize_similar_concepts(
                    concepts,
                    canonical_counts,
                    max(0.0, min(min_similarity, 1.0)),
                )
                merged_terms.extend(merges)
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
                "semantic_score": round(co_count * max(pmi, 0.0), 3),
            })

        # Sort by raw count for UI (most frequent pairs first), cap at top_n
        pairs.sort(key=lambda x: (x["count"], x.get("semantic_score", 0.0)), reverse=True)
        pairs = pairs[:top_n]
        unique_merges = []
        seen_merges: set[tuple[str, str]] = set()
        for merge in merged_terms:
            key = (str(merge["from"]).casefold(), str(merge["to"]).casefold())
            if key in seen_merges:
                continue
            seen_merges.add(key)
            unique_merges.append(merge)

        return {
            "domain_id": domain_id,
            "total_enriched": total_enriched,
            "pairs": pairs,
            "normalization": {
                "enabled": normalize_similar,
                "algorithms": ["jaro_winkler", "levenshtein"],
                "min_similarity": round(max(0.0, min(min_similarity, 1.0)), 3),
                "merged_terms": unique_merges[:25],
                "latent_semantic_indexing": {
                    "enabled": False,
                    "status": "planned",
                    "reason": "Dashboard summary uses lexical normalization plus co-occurrence PMI; full LSI/LSA can be added as a separate vector-space pass.",
                },
            },
        }

    # ── Topic clusters ───────────────────────────────────────────────────────

    def topic_clusters(
        self,
        domain_id: str,
        n_clusters: int = 6,
        org_id: int | None = None,
    ) -> dict[str, Any]:
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
        _validate_domain(domain_id, org_id=org_id)
        df = _load_concepts_df(domain_id, org_id=org_id)

        pair_counter: Counter = Counter()
        concept_counter: Counter = Counter()

        for row in df.itertuples(index=False):
            concepts = _parse_record_concepts(
                getattr(row, "enrichment_concepts", None),
                getattr(row, "attributes_json", None),
            )
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

    def emerging_signals(
        self,
        domain_id: str,
        *,
        recent_window: int = 2,
        baseline_window: int = 3,
        top_n: int = 5,
        org_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Detect conservative early signals by comparing recent concept momentum
        against the immediately preceding time window.
        """
        df = _load_concepts_timeseries_df(domain_id, org_id=org_id)

        year_totals: Counter[int] = Counter()
        concept_year_counts: dict[str, Counter[int]] = defaultdict(Counter)

        for row in df.itertuples(index=False):
            year = _extract_record_year(
                getattr(row, "attributes_json", None),
                getattr(row, "primary_label", None),
                getattr(row, "secondary_label", None),
            )
            if year is None:
                continue

            concepts = sorted(set(_parse_record_concepts(
                getattr(row, "enrichment_concepts", None),
                getattr(row, "attributes_json", None),
            )))
            if not concepts:
                continue

            year_totals[year] += 1
            for concept in concepts:
                concept_year_counts[concept][year] += 1

        years_available = sorted(year_totals)
        if len(years_available) < recent_window + 1:
            return {
                "domain_id": domain_id,
                "is_experimental": True,
                "years_available": years_available,
                "baseline_years": [],
                "recent_years": [],
                "signals": [],
            }

        recent_years = years_available[-recent_window:]
        baseline_years = years_available[max(0, len(years_available) - recent_window - baseline_window): -recent_window]
        if not baseline_years:
            return {
                "domain_id": domain_id,
                "is_experimental": True,
                "years_available": years_available,
                "baseline_years": [],
                "recent_years": recent_years,
                "signals": [],
            }

        baseline_total = sum(year_totals[y] for y in baseline_years)
        recent_total = sum(year_totals[y] for y in recent_years)
        signals: list[dict[str, Any]] = []

        for concept, counts in concept_year_counts.items():
            baseline_count = sum(counts[y] for y in baseline_years)
            recent_count = sum(counts[y] for y in recent_years)
            if recent_count < 2 or recent_count <= baseline_count:
                continue

            baseline_share = (baseline_count / baseline_total) if baseline_total else 0.0
            recent_share = (recent_count / recent_total) if recent_total else 0.0
            acceleration_score = round(recent_share - baseline_share, 4)
            if acceleration_score <= 0 and recent_count < baseline_count + 2:
                continue

            if recent_count >= 4 and acceleration_score >= 0.18:
                confidence = "high"
            elif recent_count >= 3 and acceleration_score >= 0.08:
                confidence = "medium"
            else:
                confidence = "low"

            signals.append({
                "concept": concept,
                "recent_count": recent_count,
                "baseline_count": baseline_count,
                "recent_share": round(recent_share * 100, 1),
                "baseline_share": round(baseline_share * 100, 1),
                "acceleration_score": round(acceleration_score * 100, 1),
                "confidence": confidence,
                "evidence": (
                    f"{concept} appears {recent_count} times in {recent_years[0]}-{recent_years[-1]} "
                    f"vs {baseline_count} in {baseline_years[0]}-{baseline_years[-1]}."
                ),
            })

        signals.sort(
            key=lambda signal: (
                signal["acceleration_score"],
                signal["recent_count"],
                signal["concept"].lower(),
            ),
            reverse=True,
        )

        return {
            "domain_id": domain_id,
            "is_experimental": True,
            "years_available": years_available,
            "baseline_years": baseline_years,
            "recent_years": recent_years,
            "signals": signals[:top_n],
        }
