"""Blocking-based clustering (Phase 2, Task 6).

The legacy greedy disambiguation compares every value against every other (O(n²))
and is order-dependent (first-seen value wins as the group "main"). Blocking
restricts comparisons to candidate pairs that share a *block key* (fingerprint,
phonetic code, or sorted first-token prefix), compares only intra-block pairs
with ``fuzz.token_sort_ratio``, and unions matches via Union-Find so grouping is
transitive and order-independent.
"""
from __future__ import annotations

from itertools import combinations

from thefuzz import fuzz

from backend.clustering.algorithms import cologne_phonetic, fingerprint, metaphone
from backend.clustering.union_find import UnionFind


def blocking_keys(value: str) -> set[str]:
    """Return the set of block keys a value belongs to.

    A value is compared against another only if they share at least one key.
    Multiple key families increase recall (a pair missed by one family may be
    caught by another) while still pruning the vast majority of comparisons.
    """
    keys: set[str] = set()

    fp = fingerprint(value)
    if fp:
        keys.add(f"fp:{fp}")
        tokens = fp.split()
        if tokens:
            # Sorted first-3-token prefix groups long multi-word names sharing a head.
            keys.add("pre:" + " ".join(tokens[:3]))
            # Per-token keys (len>=3) catch shared anchors like a surname even when
            # the rest of the name varies ("John Smith" / "J. Smith" / "Smith, John").
            for tok in tokens:
                if len(tok) >= 3:
                    keys.add(f"tok:{tok}")

    code = cologne_phonetic(value) or metaphone(value)
    if code:
        keys.add(f"ph:{code}")

    return keys


def cluster_values(values: list[str], threshold: int) -> list[list[str]]:
    """Cluster ``values`` into transitive groups using blocking + Union-Find.

    Returns a list of components (each a list of original values). Singletons are
    included as one-element components so callers can see the full partition.
    """
    if not values:
        return []

    # De-duplicate while preserving deterministic iteration.
    unique = list(dict.fromkeys(values))
    uf = UnionFind(unique)

    # Bucket values by block key.
    blocks: dict[str, list[str]] = {}
    for val in unique:
        for key in blocking_keys(val):
            blocks.setdefault(key, []).append(val)

    # Compare only intra-block pairs; union matches.
    compared: set[tuple[str, str]] = set()
    for members in blocks.values():
        if len(members) < 2:
            continue
        for a, b in combinations(members, 2):
            pair = (a, b) if a <= b else (b, a)
            if pair in compared:
                continue
            compared.add(pair)
            if fuzz.token_sort_ratio(a, b) >= threshold:
                uf.union(a, b)

    return uf.components()
