import json
from backend.models import RawEntity, JournalMetric
from backend.schemas_enrichment import EnrichedRecord, JournalMetrics
from backend import enrichment_worker


def test_worker_persists_journal_metric(db_session, monkeypatch):
    entity = RawEntity(primary_label="Some Paper", domain="science", enrichment_status="pending")
    db_session.add(entity)
    db_session.commit()

    enriched = EnrichedRecord(
        title="Some Paper",
        citation_count=5,
        journal=JournalMetrics(issn_l="0028-0836", source_id="S77"),
    )
    # Drive the REAL cascade: monkeypatch the module-level _ACTIVE_CASCADE list
    # so only "openalex" is attempted, and monkeypatch the adapter's methods so
    # no real HTTP calls are made.  enrich_single_record itself is NOT mocked —
    # we exercise the full real persistence path.
    monkeypatch.setattr(enrichment_worker, "_ACTIVE_CASCADE", ["openalex"])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "search_by_title",
                        lambda query, limit=1: [enriched])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "fetch_source_metrics",
                        lambda sid: JournalMetrics(issn_l="0028-0836", source_id=sid,
                                                   two_yr_mean_citedness=17.4, apc_usd=11690,
                                                   is_in_doaj=False))

    enrichment_worker.enrich_single_record(db_session, entity)

    row = db_session.query(JournalMetric).filter_by(issn_l="0028-0836").one()
    assert row.two_yr_mean_citedness == 17.4
    attrs = json.loads(entity.attributes_json or "{}")
    assert attrs.get("issn_l") == "0028-0836"


def test_worker_survives_journal_metric_failure(db_session, monkeypatch):
    """A journal sub-step failure (e.g. OpenAlex /sources timeout) must NOT abort
    persistence of the work's primary enrichment."""
    from backend.enrichment_worker import EnrichmentStatus

    entity = RawEntity(primary_label="Resilient Paper", domain="science", enrichment_status="pending")
    db_session.add(entity)
    db_session.commit()

    enriched = EnrichedRecord(
        title="Resilient Paper",
        citation_count=7,
        journal=JournalMetrics(issn_l="0028-0836", source_id="S77"),
    )

    def _boom(_sid):
        raise RuntimeError("OpenAlex /sources timeout")

    monkeypatch.setattr(enrichment_worker, "_ACTIVE_CASCADE", ["openalex"])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "search_by_title",
                        lambda query, limit=1: [enriched])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "fetch_source_metrics", _boom)

    enrichment_worker.enrich_single_record(db_session, entity)

    # Work enrichment is persisted (status completed) despite the journal step raising.
    db_session.refresh(entity)
    assert entity.enrichment_status == EnrichmentStatus.completed
    assert entity.enrichment_citation_count == 7
    # The journal step bailed, so no JournalMetric row and no issn_l tag.
    assert db_session.query(JournalMetric).filter_by(issn_l="0028-0836").count() == 0
    attrs = json.loads(entity.attributes_json or "{}")
    assert "issn_l" not in attrs
