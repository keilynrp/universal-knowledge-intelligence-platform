"""Tests for the optional work_type backfill script."""
from backend.models import RawEntity
from backend.scripts.backfill_work_type import run_backfill


def test_backfill_populates_work_type(db_session):
    db_session.add(RawEntity(primary_label="p", enrichment_doi="10.1/x"))
    db_session.commit()

    class _FakeAdapter:
        def search_by_doi(self, doi):
            class R:
                work_type = "book"
            return R()

    n = run_backfill(db_session, org_id=None, adapter=_FakeAdapter())
    assert n == 1
    assert db_session.query(RawEntity).one().enrichment_work_type == "book"


def test_backfill_skips_already_filled(db_session):
    db_session.add(RawEntity(primary_label="p", enrichment_doi="10.1/x", enrichment_work_type="article"))
    db_session.commit()

    class _FakeAdapter:
        def search_by_doi(self, doi):
            class R:
                work_type = "book"
            return R()

    n = run_backfill(db_session, org_id=None, adapter=_FakeAdapter())
    assert n == 0
    assert db_session.query(RawEntity).one().enrichment_work_type == "article"


def test_backfill_skips_no_doi(db_session):
    db_session.add(RawEntity(primary_label="no-doi"))
    db_session.commit()

    class _FakeAdapter:
        def search_by_doi(self, doi):
            class R:
                work_type = "book"
            return R()

    n = run_backfill(db_session, org_id=None, adapter=_FakeAdapter())
    assert n == 0


def test_backfill_handles_adapter_none_return(db_session):
    db_session.add(RawEntity(primary_label="p", enrichment_doi="10.1/unknown"))
    db_session.commit()

    class _FakeAdapter:
        def search_by_doi(self, doi):
            return None

    n = run_backfill(db_session, org_id=None, adapter=_FakeAdapter())
    assert n == 0
    assert db_session.query(RawEntity).one().enrichment_work_type is None


def test_backfill_scoped_to_org_id(db_session):
    db_session.add(RawEntity(primary_label="in-org", enrichment_doi="10.1/a", org_id=1))
    db_session.add(RawEntity(primary_label="other-org", enrichment_doi="10.1/b", org_id=2))
    db_session.commit()

    class _FakeAdapter:
        def search_by_doi(self, doi):
            class R:
                work_type = "dataset"
            return R()

    n = run_backfill(db_session, org_id=1, adapter=_FakeAdapter())
    assert n == 1

    rows = {r.primary_label: r for r in db_session.query(RawEntity).all()}
    assert rows["in-org"].enrichment_work_type == "dataset"
    assert rows["other-org"].enrichment_work_type is None
