from backend.models import JournalMetric
from backend.schemas_enrichment import JournalMetrics
from backend.services.journal_metrics_service import upsert_journal_metric


def test_upsert_creates_then_updates(db_session):
    jm = JournalMetrics(issn_l="0028-0836", source_id="S77", two_yr_mean_citedness=17.4, apc_usd=11690, apc_source="openalex")
    row1 = upsert_journal_metric(db_session, jm, org_id=None)
    assert row1.two_yr_mean_citedness == 17.4
    jm2 = JournalMetrics(issn_l="0028-0836", source_id="S77", two_yr_mean_citedness=18.0, apc_usd=11690, apc_source="openalex")
    row2 = upsert_journal_metric(db_session, jm2, org_id=None)
    assert row2.id == row1.id
    assert db_session.query(JournalMetric).filter_by(issn_l="0028-0836").count() == 1
    assert row2.two_yr_mean_citedness == 18.0


def test_doaj_override_wins_for_apc(db_session):
    base = JournalMetrics(issn_l="1111-2222", source_id="S1", apc_usd=2000, apc_source="openalex")
    upsert_journal_metric(db_session, base, org_id=None)
    override = {"apc_amount": 900, "apc_currency": "EUR", "apc_source": "doaj", "is_in_doaj": True}
    row = upsert_journal_metric(db_session, base, org_id=None, doaj=override)
    assert row.apc_currency == "EUR"
    assert row.apc_source == "doaj"
    assert row.is_in_doaj is True


def test_no_issn_returns_none(db_session):
    assert upsert_journal_metric(db_session, JournalMetrics(source_id="S0"), org_id=None) is None
