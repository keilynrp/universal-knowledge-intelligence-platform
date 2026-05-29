"""Tests for the Louvain-backed recompute job (F3.2).

Performance gate (spec §12.3): a 100k-edge recompute must complete under the
10s hard bound, or the worker can no longer service real dirty-scope traffic.
"""
import time

import pytest

from backend import models
from backend.coauthorship.identity import get_or_create_author
from backend.coauthorship.recompute import recompute_coauthor_stats


def _seed_pair(db, a_name, b_name, *, weight=1, org_id=0, domain="default"):
    a = get_or_create_author(db, a_name)
    b = get_or_create_author(db, b_name)
    lo, hi = sorted([a.id, b.id])
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=org_id,
                               domain_id=domain, weight=weight))
    db.commit()
    return a, b


def test_recompute_empty_scope_is_noop(db):
    out = recompute_coauthor_stats(db, org_id=0, domain_id="default")
    assert out["nodes"] == 0
    assert db.query(models.AuthorStats).count() == 0


def test_recompute_small_graph_uses_connected_components(db):
    _seed_pair(db, "A A", "B B")
    _seed_pair(db, "B B", "C C")
    _seed_pair(db, "X X", "Y Y")
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    rows = db.query(models.AuthorStats).all()
    assert len(rows) == 5
    communities = {r.community_id for r in rows}
    assert len(communities) == 2  # {A,B,C} and {X,Y}


def test_recompute_writes_degree_and_pub_counts(db):
    a, b = _seed_pair(db, "A A", "B B")
    _seed_pair(db, "B B", "C C")
    # B co-authors with A and C -> degree 2; A and C -> degree 1.
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    by_id = {r.author_id: r for r in db.query(models.AuthorStats).all()}
    b_stats = by_id[b.id]
    assert b_stats.degree == 2
    assert by_id[a.id].degree == 1


def _unique_token(i: int) -> str:
    # 'aa'..'zz' — alphabetic so name_key keeps it (digits are stripped).
    import string
    a = string.ascii_lowercase
    return a[i // 26] + a[i % 26]


def test_recompute_uses_louvain_above_threshold(db, monkeypatch):
    # 60 disjoint pairs -> 120 distinct authors (>50) so Louvain is selected.
    # NB: name_key strips digits, so the author tokens must be alphabetic.
    for i in range(60):
        tok = _unique_token(i)
        _seed_pair(db, f"{tok}a Researcher", f"{tok}b Researcher")
    called = {"louvain": False}
    import community.community_louvain as cl
    orig = cl.best_partition

    def spy(graph, *a, **kw):
        called["louvain"] = True
        return orig(graph, *a, **kw)

    monkeypatch.setattr(cl, "best_partition", spy)
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    assert called["louvain"] is True


def test_recompute_clears_dirty_scope(db):
    db.add(models.CoauthorDirtyScope(org_id=0, domain_id="default", reason="test"))
    db.commit()
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    assert db.query(models.CoauthorDirtyScope).filter_by(org_id=0, domain_id="default").count() == 0


def test_recompute_is_idempotent(db):
    _seed_pair(db, "A A", "B B")
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    first = {(r.author_id, r.degree, r.community_id) for r in db.query(models.AuthorStats).all()}
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    second = {(r.author_id, r.degree, r.community_id) for r in db.query(models.AuthorStats).all()}
    assert first == second
    assert db.query(models.AuthorStats).count() == 2


def _bulk_authors(db, prefix: str, count: int) -> list[int]:
    """Bulk-insert `count` authors with distinct name_keys; return their ids in
    node order. Avoids per-author commits in large perf seeds."""
    db.bulk_save_objects(
        [models.Author(name_key=f"{prefix}{i:06d}", display_name="x") for i in range(count)]
    )
    db.commit()
    idmap = {
        a.name_key: a.id
        for a in db.query(models.Author).filter(models.Author.name_key.like(f"{prefix}%")).all()
    }
    return [idmap[f"{prefix}{i:06d}"] for i in range(count)]


@pytest.mark.slow
def test_louvain_realistic_scale_under_5s(db):
    """HARD perf gate at UKIP's realistic per-scope scale: a clustered graph of
    ~2,000 authors / ~14k edges / 50 research groups must recompute under 5s.

    (python-louvain cannot service 100k single-scope edges in pure Python —
    see recompute._LOUVAIN_MAX_* cap and spec §12.3 waiver. Real corpora are
    orders of magnitude smaller and have strong community structure.)
    """
    import networkx as nx

    graph = nx.planted_partition_graph(50, 40, 0.3, 0.001, seed=42)
    n = graph.number_of_nodes()
    ids = _bulk_authors(db, "perf_", n)

    seen = set()
    edge_rows = []
    for u, v in graph.edges():
        lo, hi = sorted([ids[u], ids[v]])
        if (lo, hi) in seen:
            continue
        seen.add((lo, hi))
        edge_rows.append(models.CoauthorEdge(author_a_id=lo, author_b_id=hi,
                                             org_id=0, domain_id="default", weight=1))
    db.bulk_save_objects(edge_rows)
    db.commit()

    t0 = time.perf_counter()
    out = recompute_coauthor_stats(db, org_id=0, domain_id="default")
    elapsed = time.perf_counter() - t0
    print(f"realistic recompute: nodes={out['nodes']} edges={out['edges']} {elapsed * 1000:.0f}ms")
    assert elapsed < 5.0, f"Recompute too slow at realistic scale: {elapsed:.2f}s exceeds 5s gate."
    assert db.query(models.AuthorStats).count() == n


def test_recompute_caps_louvain_for_oversized_scope(db, monkeypatch):
    """Safety cap: a scope above the node/edge bound must skip Louvain and use
    the fast connected-components fallback so recompute can never stall the
    worker. Seeds a chain of >_LOUVAIN_MAX_NODES authors (one component)."""
    from backend.coauthorship import recompute as rc

    n = rc._LOUVAIN_MAX_NODES + 200
    ids = _bulk_authors(db, "big_", n)
    db.bulk_save_objects([
        models.CoauthorEdge(author_a_id=min(ids[i], ids[i + 1]),
                            author_b_id=max(ids[i], ids[i + 1]),
                            org_id=0, domain_id="default", weight=1)
        for i in range(n - 1)
    ])
    db.commit()

    import community.community_louvain as cl
    called = {"louvain": False}

    def boom(*a, **kw):
        called["louvain"] = True
        return {}

    monkeypatch.setattr(cl, "best_partition", boom)
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    assert called["louvain"] is False, "Louvain must be skipped above the cap"
    rows = db.query(models.AuthorStats).all()
    assert len(rows) == n
    # One connected chain -> a single community.
    assert len({r.community_id for r in rows}) == 1
