"""Tests for the Union-Find clustering primitive (Phase 2, Task 5)."""
from backend.clustering.union_find import UnionFind


def test_transitive_closure():
    uf = UnionFind(["a", "b", "c", "d"])
    uf.union("a", "b")
    uf.union("b", "c")  # a-b-c connected; d alone
    comps = uf.components()
    assert sorted(len(c) for c in comps) == [1, 3]
    assert uf.connected("a", "c") is True
    assert uf.connected("a", "d") is False


def test_add_grows_the_universe():
    uf = UnionFind()
    uf.add("x")
    uf.add("y")
    assert uf.connected("x", "y") is False
    uf.union("x", "y")
    assert uf.connected("x", "y") is True


def test_union_unknown_elements_auto_adds():
    uf = UnionFind()
    uf.union("p", "q")  # neither added beforehand
    assert uf.connected("p", "q") is True
    assert sorted(len(c) for c in uf.components()) == [2]


def test_components_are_disjoint_and_cover_all():
    uf = UnionFind(["1", "2", "3", "4", "5"])
    uf.union("1", "2")
    uf.union("3", "4")
    comps = uf.components()
    flat = sorted(x for c in comps for x in c)
    assert flat == ["1", "2", "3", "4", "5"]
    assert sorted(len(c) for c in comps) == [1, 2, 2]
