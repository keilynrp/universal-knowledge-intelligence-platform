from backend.models import JournalMetric


def test_journal_metric_columns(db_session):
    jm = JournalMetric(
        issn_l="1234-5678",
        source_id="S123",
        display_name="Journal of Testing",
        two_yr_mean_citedness=3.2,
        h_index=80,
        apc_usd=1500,
        apc_currency="USD",
        apc_source="openalex",
        is_in_doaj=True,
        if_metric_kind="openalex_2yr_mean_citedness",
    )
    db_session.add(jm)
    db_session.commit()
    fetched = db_session.query(JournalMetric).filter_by(issn_l="1234-5678").one()
    assert fetched.two_yr_mean_citedness == 3.2
    assert fetched.apc_source == "openalex"
    assert fetched.normalized_impact_factor is None  # not computed yet
