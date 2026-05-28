"""Schema-level tests for the V2 coauthorship tables. These exercise DDL,
compound primary keys, the org_id=0 sentinel invariant, and FK cascades.
Pure schema — no business logic."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from backend import models
from backend.database import SessionLocal


@pytest.fixture
def db():
    s = SessionLocal()
    # SQLite enforces FK CASCADE only when PRAGMA foreign_keys=ON.
    # The conftest uses StaticPool (single shared connection), so we must
    # restore the default OFF state after the test to avoid affecting other
    # tests that depend on relaxed FK behavior during cleanup.
    s.execute(text("PRAGMA foreign_keys=ON"))
    try:
        yield s
    finally:
        s.rollback()
        # Clean rows produced by this test before turning FKs back off,
        # then restore default pragma state.
        try:
            s.execute(text("DELETE FROM coauthor_contributions"))
            s.execute(text("DELETE FROM coauthor_edges"))
            s.execute(text("DELETE FROM author_publications"))
            s.execute(text("DELETE FROM author_stats"))
            s.execute(text("DELETE FROM author_merge_suggestions"))
            s.execute(text("DELETE FROM author_merge_audit"))
            s.execute(text("DELETE FROM coauthor_dirty_scopes"))
            s.execute(text("DELETE FROM authors"))
            s.execute(text("DELETE FROM raw_entities"))
            s.commit()
        except Exception:
            s.rollback()
        s.execute(text("PRAGMA foreign_keys=OFF"))
        s.commit()
        s.close()


def test_author_unique_name_key(db):
    a = models.Author(name_key="smith_john", display_name="John Smith")
    b = models.Author(name_key="smith_john", display_name="John SMITH")
    db.add(a); db.commit()
    db.add(b)
    with pytest.raises(IntegrityError):
        db.commit()


def test_author_unique_orcid_nullable(db):
    db.add(models.Author(name_key="a_a", display_name="A A", orcid=None))
    db.add(models.Author(name_key="b_b", display_name="B B", orcid=None))
    db.commit()  # two NULLs allowed
    db.add(models.Author(name_key="c_c", display_name="C C", orcid="0000-1"))
    db.add(models.Author(name_key="d_d", display_name="D D", orcid="0000-1"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_coauthor_edges_pk_uniqueness_legacy_scope(db):
    """Two edges with the same author pair and org_id=0 (legacy) MUST collide.
    Regression: nullable org_id used to silently allow duplicates."""
    a1 = models.Author(name_key="x_x", display_name="X X"); db.add(a1)
    a2 = models.Author(name_key="y_y", display_name="Y Y"); db.add(a2)
    db.commit()
    lo, hi = sorted([a1.id, a2.id])
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=0, domain_id="default", weight=1))
    db.commit()
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=0, domain_id="default", weight=1))
    with pytest.raises(IntegrityError):
        db.commit()


def test_coauthor_edges_pk_allows_different_scopes(db):
    a1 = models.Author(name_key="p_p", display_name="P P"); db.add(a1)
    a2 = models.Author(name_key="q_q", display_name="Q Q"); db.add(a2)
    db.commit()
    lo, hi = sorted([a1.id, a2.id])
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=0, domain_id="default", weight=1))
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=1, domain_id="default", weight=1))
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=0, domain_id="science", weight=1))
    db.commit()  # all three distinct rows


def test_author_publication_cascade_on_entity_delete(db):
    """Deleting a raw_entity must cascade to author_publications."""
    a = models.Author(name_key="z_z", display_name="Z Z"); db.add(a)
    e = models.RawEntity(primary_label="paper", domain="default", attributes_json="{}")
    db.add(e); db.commit()
    db.add(models.AuthorPublication(author_id=a.id, entity_id=e.id, org_id=0,
                                     domain_id="default", position=1))
    db.commit()
    db.delete(e); db.commit()
    assert db.query(models.AuthorPublication).count() == 0


def test_dirty_scopes_pk(db):
    db.add(models.CoauthorDirtyScope(org_id=0, domain_id="default", reason="enrichment"))
    db.commit()
    db.add(models.CoauthorDirtyScope(org_id=0, domain_id="default", reason="migration"))
    with pytest.raises(IntegrityError):
        db.commit()
