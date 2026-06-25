import datetime as _dt

from alembic.config import Config
from alembic.script import ScriptDirectory
from backend.adapters.enrichment.openalex import _works_last_2_complete_years


def test_single_head_is_nif_bayes():
    cfg = Config("alembic.ini")
    heads = set(ScriptDirectory.from_config(cfg).get_heads())
    assert heads == {"d6e7f8a9b0c1"}, f"expected single head d6e7f8a9b0c1, got {heads}"


def test_journalmetric_has_bayes_columns():
    from backend.models import JournalMetric
    cols = set(JournalMetric.__table__.columns.keys())
    assert {"works_2yr", "nif_bayes", "nif_ci_low",
            "nif_ci_high", "nif_bayes_updated_at"} <= cols


def test_works_last_2_complete_years_basic():
    yr = _dt.datetime.now(_dt.timezone.utc).year
    counts = [
        {"year": yr,     "works_count": 50},   # current (partial) — excluded
        {"year": yr - 1, "works_count": 40},
        {"year": yr - 2, "works_count": 30},
        {"year": yr - 3, "works_count": 20},   # older — excluded
    ]
    assert _works_last_2_complete_years(counts) == 70   # 40 + 30


def test_works_last_2_complete_years_empty_or_missing():
    assert _works_last_2_complete_years([]) is None
    assert _works_last_2_complete_years(None) is None
    assert _works_last_2_complete_years([{"year": "x"}]) is None


def test_works_last_2_complete_years_filters_non_numeric_works_count():
    yr = _dt.datetime.now(_dt.timezone.utc).year
    # string works_count is filtered out (→ None when it's the only entry)
    assert _works_last_2_complete_years([{"year": yr - 1, "works_count": "bad"}]) is None
    # float works_count is accepted and cast
    assert _works_last_2_complete_years([
        {"year": yr - 1, "works_count": 40.0},
        {"year": yr - 2, "works_count": 30},
    ]) == 70


def test_upsert_persists_works_2yr(db_session):
    from backend.services.journal_metrics_service import upsert_journal_metric
    from backend.schemas_enrichment import JournalMetrics
    jm = JournalMetrics(issn_l="1234-5678", two_yr_mean_citedness=3.0, works_2yr=120)
    row = upsert_journal_metric(db_session, jm, org_id=None)
    assert row.works_2yr == 120
