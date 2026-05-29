"""V2 coauthorship write hook (F3.3).

Flag-gated dual-write: builds authors / publications / edges / contributions
for one entity, idempotently, and enqueues the scope for recompute. Does NOT
touch legacy entity_relationships (spec Appendix B item 2).
"""
import json

import pytest

from backend import config, models
from backend.enrichment_worker import write_coauthor_artifacts


@pytest.fixture
def write_on(monkeypatch):
    monkeypatch.setattr(config, "COAUTHOR_V2_WRITE", True)


def _entity(db, *, domain="default", org_id=None, authors=None):
    attrs = json.dumps({"enrichment_authors": authors or []})
    e = models.RawEntity(primary_label="paper", domain=domain, org_id=org_id,
                         attributes_json=attrs)
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def test_write_disabled_does_nothing(db):
    e = _entity(db, authors=["John Smith", "Amy Lee"])
    write_coauthor_artifacts(db, e)
    db.commit()
    assert db.query(models.AuthorPublication).count() == 0


def test_write_enabled_creates_publications_and_edges(db, write_on):
    e = _entity(db, authors=["John Smith", "Amy Lee"])
    write_coauthor_artifacts(db, e)
    db.commit()
    assert db.query(models.AuthorPublication).count() == 2
    assert db.query(models.CoauthorEdge).count() == 1
    assert db.query(models.CoauthorContribution).count() == 1
    assert db.query(models.CoauthorDirtyScope).filter_by(org_id=0, domain_id="default").count() == 1


def test_write_force_bypasses_flag(db):
    e = _entity(db, authors=["John Smith", "Amy Lee"])
    write_coauthor_artifacts(db, e, force=True)
    db.commit()
    assert db.query(models.CoauthorEdge).count() == 1


def test_write_idempotent(db, write_on):
    e = _entity(db, authors=["John Smith", "Amy Lee"])
    write_coauthor_artifacts(db, e)
    db.commit()
    write_coauthor_artifacts(db, e)  # second call must not increment weight
    db.commit()
    edge = db.query(models.CoauthorEdge).one()
    assert edge.weight == 1
    assert db.query(models.AuthorPublication).count() == 2


def test_write_real_org(db, write_on):
    e = _entity(db, authors=["A B", "C D"], org_id=7)
    write_coauthor_artifacts(db, e)
    db.commit()
    assert db.query(models.AuthorPublication).filter_by(org_id=7).count() == 2
    assert db.query(models.CoauthorEdge).filter_by(org_id=7).count() == 1


def test_write_single_author_is_noop(db, write_on):
    e = _entity(db, authors=["Solo Author"])
    write_coauthor_artifacts(db, e)
    db.commit()
    assert db.query(models.AuthorPublication).count() == 0
    assert db.query(models.CoauthorEdge).count() == 0


def test_tenancy_reassignment_moves_publications(db, write_on):
    e = _entity(db, authors=["A B", "C D"], org_id=None)  # legacy scope -> org_id 0
    write_coauthor_artifacts(db, e)
    db.commit()
    e.org_id = 9
    db.commit()
    write_coauthor_artifacts(db, e)
    db.commit()
    pubs = db.query(models.AuthorPublication).all()
    assert pubs and all(p.org_id == 9 for p in pubs)
    scopes = {(s.org_id, s.domain_id) for s in db.query(models.CoauthorDirtyScope).all()}
    assert (0, "default") in scopes  # old scope enqueued for recompute
    assert (9, "default") in scopes  # new scope enqueued
