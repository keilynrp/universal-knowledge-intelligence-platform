"""Union-Find (disjoint-set) for transitive grouping (Phase 2, Task 5).

Used by blocking-based clustering to merge pairwise matches into connected
components: if A≈B and B≈C then {A, B, C} form one group regardless of input
order. Path compression + union-by-rank keep operations near O(α(n)).
"""
from __future__ import annotations

from typing import Hashable, Iterable


class UnionFind:
    def __init__(self, elements: Iterable[Hashable] | None = None) -> None:
        self._parent: dict[Hashable, Hashable] = {}
        self._rank: dict[Hashable, int] = {}
        if elements:
            for e in elements:
                self.add(e)

    def __contains__(self, x: Hashable) -> bool:
        return x in self._parent

    def add(self, x: Hashable) -> None:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0

    def find(self, x: Hashable) -> Hashable:
        self.add(x)
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        # Path compression
        while self._parent[x] != root:
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: Hashable, b: Hashable) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # Union by rank
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1

    def connected(self, a: Hashable, b: Hashable) -> bool:
        return self.find(a) == self.find(b)

    def components(self) -> list[list[Hashable]]:
        groups: dict[Hashable, list[Hashable]] = {}
        for x in self._parent:
            groups.setdefault(self.find(x), []).append(x)
        return list(groups.values())
