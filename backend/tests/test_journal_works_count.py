import json
import pathlib
import re

from backend.models import JournalMetric, RawEntity


def test_raw_entity_has_enrichment_issn_l(db_session):
    e = RawEntity(primary_label="W", enrichment_issn_l="0028-0836")
    db_session.add(e); db_session.commit()
    assert db_session.query(RawEntity).filter_by(enrichment_issn_l="0028-0836").count() == 1


def test_single_alembic_head_after_migration():
    versions = pathlib.Path("alembic/versions")
    revs, downs = set(), set()
    for f in versions.glob("*.py"):
        t = f.read_text(encoding="utf-8")
        for m in re.finditer(r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)', t, re.M):
            revs.add(m.group(1))
        # Capture ALL revision ids on each down_revision line — handles plain
        # strings, typed annotations, AND tuple forms like ("x","y") in the repo.
        # Pattern accepts any alphanumeric ID (hex OR mixed like eng1prereq00001).
        for m in re.finditer(r"down_revision[^=]*=.*?$", t, re.M):
            for rid in re.findall(r'["\']([a-zA-Z0-9_]{4,})["\']', m.group(0)):
                downs.add(rid)
    heads = revs - downs
    assert heads == {"b7c8d9e0f1a2"}, f"expected single head b7c8d9e0f1a2, got {heads}"


def test_migration_backfills_issn_from_attributes(tmp_path):
    """Apply the migration's upgrade() against in-memory SQLite and confirm backfill."""
    import importlib.util
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    spec = importlib.util.spec_from_file_location(
        "mig_issn", "alembic/versions/c5e6f7a8b9c0_raw_entity_issn_l.py")
    mig = importlib.util.module_from_spec(spec); spec.loader.exec_module(mig)

    eng = sa.create_engine("sqlite://")
    with eng.connect() as conn:
        # minimal raw_entities table with the columns the backfill touches
        conn.execute(sa.text(
            "CREATE TABLE raw_entities (id INTEGER PRIMARY KEY, "
            "attributes_json TEXT)"))
        conn.execute(sa.text(
            "INSERT INTO raw_entities (id, attributes_json) VALUES "
            "(1, '{\"issn_l\": \"0028-0836\"}'), (2, '{\"other\": 1}'), (3, NULL)"))
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mig.upgrade()
        rows = dict(conn.execute(sa.text(
            "SELECT id, enrichment_issn_l FROM raw_entities")).fetchall())
        assert rows[1] == "0028-0836" and rows[2] is None and rows[3] is None
        with Operations.context(ctx):
            mig.downgrade()
        cols = [c["name"] for c in sa.inspect(conn).get_columns("raw_entities")]
        assert "enrichment_issn_l" not in cols


def test_worker_sets_enrichment_issn_l(db_session, monkeypatch):
    from backend import enrichment_worker
    from backend.schemas_enrichment import EnrichedRecord, JournalMetrics
    entity = RawEntity(primary_label="Some Paper", domain="science", enrichment_status="pending")
    db_session.add(entity); db_session.commit()
    enriched = EnrichedRecord(title="Some Paper", citation_count=1,
                              journal=JournalMetrics(issn_l="0028-0836", source_id="S77"))
    monkeypatch.setattr(enrichment_worker, "_ACTIVE_CASCADE", ["openalex"])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "search_by_title",
                        lambda query, limit=1: [enriched])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "fetch_source_metrics",
                        lambda sid: JournalMetrics(issn_l="0028-0836", source_id=sid,
                                                   two_yr_mean_citedness=1.0, is_in_doaj=False))
    enrichment_worker.enrich_single_record(db_session, entity)
    db_session.refresh(entity)
    assert entity.enrichment_issn_l == "0028-0836"


from backend.services.journal_metrics_service import works_count_by_issn


def test_works_count_by_issn_org_scoped(db_session):
    db_session.add(RawEntity(primary_label="a", org_id=1, enrichment_issn_l="X"))
    db_session.add(RawEntity(primary_label="b", org_id=1, enrichment_issn_l="X"))
    db_session.add(RawEntity(primary_label="c", org_id=1, enrichment_issn_l="Y"))
    db_session.add(RawEntity(primary_label="d", org_id=2, enrichment_issn_l="X"))  # other org
    db_session.commit()
    counts = works_count_by_issn(db_session, 1)
    assert counts == {"X": 2, "Y": 1}


def test_works_count_filtered_by_issns(db_session):
    db_session.add(RawEntity(primary_label="a", org_id=None, enrichment_issn_l="X"))
    db_session.add(RawEntity(primary_label="b", org_id=None, enrichment_issn_l="Z"))
    db_session.commit()
    assert works_count_by_issn(db_session, None, issns=["X"]) == {"X": 1}


def test_list_includes_works_count(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="0028-0836", normalized_impact_factor=1.5))
    db_session.add(RawEntity(primary_label="w1", org_id=None, enrichment_issn_l="0028-0836"))
    db_session.add(RawEntity(primary_label="w2", org_id=None, enrichment_issn_l="0028-0836"))
    db_session.commit()
    r = client.get("/journals", headers=auth_headers)
    assert r.status_code == 200
    row = next(j for j in r.json() if j["issn_l"] == "0028-0836")
    assert row["works_count"] == 2


def test_list_works_count_zero_when_no_entities(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="1111-2222", normalized_impact_factor=1.0))
    db_session.commit()
    r = client.get("/journals", headers=auth_headers)
    row = next(j for j in r.json() if j["issn_l"] == "1111-2222")
    assert row["works_count"] == 0


def test_single_includes_works_count(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="0028-0836"))
    db_session.add(RawEntity(primary_label="w1", org_id=None, enrichment_issn_l="0028-0836"))
    db_session.commit()
    r = client.get("/journals/0028-0836", headers=auth_headers)
    assert r.status_code == 200 and r.json()["works_count"] == 1
