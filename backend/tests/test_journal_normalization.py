from backend.models import JournalMetric
from backend.analyzers.journal_normalization import normalize_impact_factors


def _seed(db, issn, val, field="all"):
    db.add(JournalMetric(issn_l=issn, two_yr_mean_citedness=val, nif_field=field))


def test_nif_is_metric_over_field_median(db_session):
    _seed(db_session, "A", 2.0)
    _seed(db_session, "B", 4.0)
    _seed(db_session, "C", 6.0)  # median = 4.0
    db_session.commit()
    updated = normalize_impact_factors(db_session, org_id=None)
    assert updated == 3
    rows = {r.issn_l: r for r in db_session.query(JournalMetric).all()}
    assert rows["A"].normalized_impact_factor == 0.5   # 2/4
    assert rows["B"].normalized_impact_factor == 1.0   # 4/4
    assert rows["C"].normalized_impact_factor == 1.5   # 6/4
    assert rows["B"].nif_updated_at is not None


def test_journals_without_metric_are_skipped(db_session):
    _seed(db_session, "A", 4.0)
    db_session.add(JournalMetric(issn_l="D", two_yr_mean_citedness=None))
    db_session.commit()
    normalize_impact_factors(db_session, org_id=None)
    d = db_session.query(JournalMetric).filter_by(issn_l="D").one()
    assert d.normalized_impact_factor is None
