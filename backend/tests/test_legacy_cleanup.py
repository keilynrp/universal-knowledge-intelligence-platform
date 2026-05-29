"""F5.1 — legacy CO_AUTHOR cleanup script tests."""
from backend import models
from backend.scripts.cleanup_legacy_coauthor import run


def test_cleanup_deletes_only_coauthor_rows(db):
    db.add(models.EntityRelationship(source_id=1, target_id=1, relation_type="CO_AUTHOR",
                                     notes="a||b", weight=1.0))
    db.add(models.EntityRelationship(source_id=1, target_id=2, relation_type="REFERENCES",
                                     notes="ref", weight=1.0))
    db.commit()

    deleted = run(db)
    assert deleted == 1
    assert db.query(models.EntityRelationship).filter_by(relation_type="CO_AUTHOR").count() == 0
    assert db.query(models.EntityRelationship).filter_by(relation_type="REFERENCES").count() == 1


def test_cleanup_dry_run_counts_without_deleting(db):
    db.add(models.EntityRelationship(source_id=1, target_id=1, relation_type="CO_AUTHOR",
                                     notes="a||b", weight=1.0))
    db.commit()
    n = run(db, dry_run=True)
    assert n == 1
    assert db.query(models.EntityRelationship).filter_by(relation_type="CO_AUTHOR").count() == 1
