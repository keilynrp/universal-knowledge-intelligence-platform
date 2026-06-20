"""Tests for the surgical journal-metrics backfill (no full re-enrichment).

The backfill populates ``journal_metrics`` for already-enriched works by looking
up each work's OpenAlex source via its stored DOI — deliberately bypassing
``enrich_single_record`` (whose legacy co-author edge path is not idempotent and
violates ``uq_entity_relationships_pair_global`` on re-run).
"""
from backend.models import RawEntity, JournalMetric
from backend.schemas_enrichment import EnrichedRecord, JournalMetrics
import backend.services.journal_backfill as journal_backfill
from backend.services.journal_backfill import (
    backfill_entity_journal,
    backfill_all,
)


class _FakeOpenAlex:
    """Stub adapter: maps DOI -> EnrichedRecord, source_id -> JournalMetrics."""

    def __init__(self, by_doi=None, source_metrics=None, raise_on_doi=None):
        self._by_doi = by_doi or {}
        self._source_metrics = source_metrics or {}
        self._raise_on_doi = raise_on_doi

    def search_by_doi(self, doi):
        if self._raise_on_doi and doi == self._raise_on_doi:
            raise RuntimeError("OpenAlex /works timeout")
        return self._by_doi.get(doi)

    def fetch_source_metrics(self, source_id):
        return self._source_metrics.get(source_id)


def _completed(label, doi, org_id=None, issn=None):
    return RawEntity(
        primary_label=label,
        domain="science",
        enrichment_status="completed",
        enrichment_doi=doi,
        enrichment_issn_l=issn,
        org_id=org_id,
    )


def test_backfill_entity_writes_journal_metric(db_session):
    entity = _completed("Tara Oceans", "10.1/abc")
    db_session.add(entity)
    db_session.commit()

    oa = _FakeOpenAlex(
        by_doi={"10.1/abc": EnrichedRecord(
            title="Tara Oceans",
            journal=JournalMetrics(issn_l="0028-0836", source_id="S77"),
        )},
        source_metrics={"S77": JournalMetrics(
            issn_l="0028-0836", source_id="S77",
            two_yr_mean_citedness=17.4, h_index=1200, apc_usd=11690, is_in_doaj=False,
        )},
    )

    wrote = backfill_entity_journal(db_session, entity, openalex=oa)
    db_session.commit()

    assert wrote is True
    row = db_session.query(JournalMetric).filter_by(issn_l="0028-0836").one()
    assert row.two_yr_mean_citedness == 17.4
    assert row.apc_usd == 11690
    db_session.refresh(entity)
    assert entity.enrichment_issn_l == "0028-0836"


def test_backfill_entity_no_doi_returns_false(db_session):
    entity = _completed("No DOI work", None)
    db_session.add(entity)
    db_session.commit()

    assert backfill_entity_journal(db_session, entity, openalex=_FakeOpenAlex()) is False
    assert db_session.query(JournalMetric).count() == 0


def test_backfill_entity_no_journal_returns_false(db_session):
    entity = _completed("Journal-less work", "10.1/none")
    db_session.add(entity)
    db_session.commit()

    oa = _FakeOpenAlex(by_doi={"10.1/none": EnrichedRecord(title="Journal-less work", journal=None)})
    assert backfill_entity_journal(db_session, entity, openalex=oa) is False
    assert db_session.query(JournalMetric).count() == 0


def test_backfill_entity_falls_back_to_record_issn_when_source_metrics_missing(db_session):
    """If /sources returns nothing, still persist using the issn_l from the work record."""
    entity = _completed("Fallback work", "10.1/fb")
    db_session.add(entity)
    db_session.commit()

    oa = _FakeOpenAlex(
        by_doi={"10.1/fb": EnrichedRecord(
            title="Fallback work",
            journal=JournalMetrics(issn_l="1234-5678", source_id="S99"),
        )},
        source_metrics={},  # fetch_source_metrics returns None
    )
    assert backfill_entity_journal(db_session, entity, openalex=oa) is True
    db_session.commit()
    assert db_session.query(JournalMetric).filter_by(issn_l="1234-5678").count() == 1
    db_session.refresh(entity)
    assert entity.enrichment_issn_l == "1234-5678"


def test_script_configure_logging_quiets_httpx():
    """The operator script quiets httpx's per-request INFO lines (the 429s the
    adapter already retries) while keeping warnings/errors."""
    import logging
    from backend.scripts.backfill_journal_metrics import _configure_logging

    logging.getLogger("httpx").setLevel(logging.INFO)  # arrange: noisy default
    _configure_logging()
    assert logging.getLogger("httpx").level == logging.WARNING


def test_backfill_all_throttles_between_entities(db_session, monkeypatch):
    """A positive `delay` sleeps between works (polite-pool throttle to avoid 429s)."""
    db_session.add(_completed("a", "10.1/a"))
    db_session.add(_completed("b", "10.1/b"))
    db_session.commit()
    oa = _FakeOpenAlex(
        by_doi={
            "10.1/a": EnrichedRecord(title="a", journal=JournalMetrics(issn_l="0028-0836", source_id="S1")),
            "10.1/b": EnrichedRecord(title="b", journal=JournalMetrics(issn_l="1111-2222", source_id="S2")),
        },
        source_metrics={
            "S1": JournalMetrics(issn_l="0028-0836", source_id="S1", two_yr_mean_citedness=1.0, is_in_doaj=False),
            "S2": JournalMetrics(issn_l="1111-2222", source_id="S2", two_yr_mean_citedness=1.0, is_in_doaj=False),
        },
    )
    slept: list[float] = []
    monkeypatch.setattr(journal_backfill.time, "sleep", lambda s: slept.append(s))

    backfill_all(db_session, openalex=oa, only_missing=True, delay=0.2)

    assert slept and all(s == 0.2 for s in slept)


def test_backfill_all_default_has_no_delay(db_session, monkeypatch):
    """The library default is no throttle (fast, pure); the script opts into a delay."""
    db_session.add(_completed("a", "10.1/a"))
    db_session.commit()
    oa = _FakeOpenAlex(
        by_doi={"10.1/a": EnrichedRecord(title="a", journal=JournalMetrics(issn_l="0028-0836", source_id="S1"))},
        source_metrics={"S1": JournalMetrics(issn_l="0028-0836", source_id="S1", two_yr_mean_citedness=1.0, is_in_doaj=False)},
    )
    slept: list[float] = []
    monkeypatch.setattr(journal_backfill.time, "sleep", lambda s: slept.append(s))

    backfill_all(db_session, openalex=oa, only_missing=True)

    assert slept == []


def test_backfill_all_only_missing(db_session):
    done = _completed("Already backfilled", "10.1/done", issn="9999-0000")
    todo = _completed("Needs backfill", "10.1/todo")
    db_session.add_all([done, todo])
    db_session.commit()

    oa = _FakeOpenAlex(
        by_doi={
            "10.1/todo": EnrichedRecord(title="Needs backfill",
                                        journal=JournalMetrics(issn_l="0028-0836", source_id="S77")),
            "10.1/done": EnrichedRecord(title="Already backfilled",
                                        journal=JournalMetrics(issn_l="9999-0000", source_id="S1")),
        },
        source_metrics={"S77": JournalMetrics(issn_l="0028-0836", source_id="S77",
                                              two_yr_mean_citedness=5.0, is_in_doaj=False)},
    )

    result = backfill_all(db_session, openalex=oa, only_missing=True)

    assert result["written"] == 1
    assert result["processed"] == 1  # the "done" row is excluded by only_missing
    assert db_session.query(JournalMetric).filter_by(issn_l="0028-0836").count() == 1


def test_backfill_all_survives_per_entity_error(db_session):
    bad = _completed("Boom", "10.1/boom")
    good = _completed("Fine", "10.1/fine")
    db_session.add_all([bad, good])
    db_session.commit()

    oa = _FakeOpenAlex(
        by_doi={"10.1/fine": EnrichedRecord(title="Fine",
                                            journal=JournalMetrics(issn_l="0028-0836", source_id="S77"))},
        source_metrics={"S77": JournalMetrics(issn_l="0028-0836", source_id="S77",
                                              two_yr_mean_citedness=3.0, is_in_doaj=False)},
        raise_on_doi="10.1/boom",
    )

    result = backfill_all(db_session, openalex=oa, only_missing=True)

    assert result["errors"] == 1
    assert result["written"] == 1
    # The good row still landed despite the bad one raising.
    assert db_session.query(JournalMetric).filter_by(issn_l="0028-0836").count() == 1


def test_backfill_all_is_idempotent(db_session):
    entity = _completed("Repeatable", "10.1/rep")
    db_session.add(entity)
    db_session.commit()

    oa = _FakeOpenAlex(
        by_doi={"10.1/rep": EnrichedRecord(title="Repeatable",
                                           journal=JournalMetrics(issn_l="0028-0836", source_id="S77"))},
        source_metrics={"S77": JournalMetrics(issn_l="0028-0836", source_id="S77",
                                              two_yr_mean_citedness=2.0, is_in_doaj=False)},
    )

    first = backfill_all(db_session, openalex=oa, only_missing=True)
    second = backfill_all(db_session, openalex=oa, only_missing=True)

    assert first["written"] == 1
    assert second["processed"] == 0  # nothing left to do
    assert db_session.query(JournalMetric).filter_by(issn_l="0028-0836").count() == 1
