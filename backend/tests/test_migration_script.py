"""One-shot migration tests (F4a.1).

Covered: dry-run reports counts without writes; full run creates V2 rows; the
run is idempotent; surface forms collapsing to one name_key are recorded as
self-pairs, not coauthor edges.
"""
import json
from itertools import combinations

from backend import models
from backend.coauthorship.migration import migrate_coauthor_graph


def _legacy_seed(db, *, entity_id, authors):
    e = models.RawEntity(
        id=entity_id, primary_label=f"e{entity_id}", domain="default",
        attributes_json=json.dumps({"enrichment_authors": authors}),
    )
    db.add(e)
    db.commit()
    for a, b in combinations(authors, 2):
        lo, hi = sorted([a, b])
        db.add(models.EntityRelationship(
            source_id=entity_id, target_id=entity_id,
            relation_type="CO_AUTHOR", weight=1.0, notes=f"{lo}||{hi}",
            org_id=None,
        ))
    db.commit()


def test_dry_run_no_writes(db):
    _legacy_seed(db, entity_id=1, authors=["John Smith", "Amy Lee"])
    stats = migrate_coauthor_graph(db, dry_run=True)
    assert stats["legacy_edges_found"] == 1
    assert stats["entities_with_authors"] == 1
    assert stats["authors_created"] == 0  # dry-run writes nothing
    assert db.query(models.Author).count() == 0


def test_full_run_creates_authors_and_edges(db):
    _legacy_seed(db, entity_id=1, authors=["John Smith", "Amy Lee", "K. Park"])
    stats = migrate_coauthor_graph(db, dry_run=False)
    assert stats["authors_created"] == 3
    assert stats["edges_created"] == 3
    assert db.query(models.Author).count() == 3
    assert db.query(models.CoauthorEdge).count() == 3
    assert db.query(models.AuthorPublication).count() == 3


def test_full_run_idempotent(db):
    _legacy_seed(db, entity_id=1, authors=["John Smith", "Amy Lee"])
    migrate_coauthor_graph(db, dry_run=False)
    before = (
        db.query(models.Author).count(),
        db.query(models.CoauthorEdge).count(),
        db.query(models.AuthorPublication).count(),
    )
    edge_weight_before = db.query(models.CoauthorEdge).one().weight
    migrate_coauthor_graph(db, dry_run=False)
    after = (
        db.query(models.Author).count(),
        db.query(models.CoauthorEdge).count(),
        db.query(models.AuthorPublication).count(),
    )
    assert before == after
    # Idempotent weight: the single shared publication contributes exactly 1.
    assert db.query(models.CoauthorEdge).one().weight == edge_weight_before == 1


def test_namekey_collapses_legacy_surface_forms(db):
    # "Smith, John" and "John Smith" are one person -> not a real coauthor edge.
    _legacy_seed(db, entity_id=1, authors=["Smith, John", "John Smith"])
    stats = migrate_coauthor_graph(db, dry_run=False)
    assert stats["self_pairs_skipped"] == 1
    assert db.query(models.CoauthorEdge).count() == 0
    assert db.query(models.Author).count() == 1
    # The single (collapsed) author still gets a publication row.
    assert db.query(models.AuthorPublication).count() == 1
