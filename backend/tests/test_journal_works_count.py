import json
import pathlib
import re

from backend.models import RawEntity


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
    assert heads == {"c5e6f7a8b9c0"}, f"expected single head c5e6f7a8b9c0, got {heads}"


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
