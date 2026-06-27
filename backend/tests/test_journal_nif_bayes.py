import datetime as _dt

from alembic.config import Config
from alembic.script import ScriptDirectory
from backend.adapters.enrichment.openalex import _works_last_2_complete_years
from backend.models import JournalMetric


def test_single_head_is_nif_bayes():
    cfg = Config("alembic.ini")
    heads = set(ScriptDirectory.from_config(cfg).get_heads())
    assert heads == {"e6f7a8b9c0d2"}, f"expected single head e6f7a8b9c0d2, got {heads}"


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


def _mk(db, **kw):
    row = JournalMetric(org_id=None, **kw)
    db.add(row); db.flush(); return row


def test_bayes_shrinks_small_journal_toward_field(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    for i in range(6):
        _mk(db_session, issn_l=f"A-{i}", nif_field="Medicine",
            two_yr_mean_citedness=5.0, works_2yr=400)
    tiny = _mk(db_session, issn_l="A-tiny", nif_field="Medicine",
               two_yr_mean_citedness=0.2, works_2yr=5)
    n = normalize_impact_factors_bayes(db_session, org_id=None)
    assert n == 7
    raw_nif = tiny.two_yr_mean_citedness / 5.0     # 0.04 — the unshrunk ratio
    assert tiny.nif_bayes > raw_nif                 # shrunk UP toward the field average
    assert tiny.nif_ci_low >= 0.0
    assert tiny.nif_ci_high > tiny.nif_bayes


def test_bayes_large_journal_barely_moves(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    for i in range(6):
        _mk(db_session, issn_l=f"B-{i}", nif_field="Physics",
            two_yr_mean_citedness=5.0, works_2yr=800)
    big = _mk(db_session, issn_l="B-big", nif_field="Physics",
              two_yr_mean_citedness=9.0, works_2yr=2000)
    normalize_impact_factors_bayes(db_session, org_id=None)
    assert big.nif_ci_high - big.nif_ci_low < big.nif_bayes  # tight-ish CI
    assert big.nif_bayes > 1.0   # rate 9 is above the field's pooled mean → stays >1


def test_bayes_skips_rows_without_works_2yr(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    r = _mk(db_session, issn_l="C-1", nif_field="Chemistry",
            two_yr_mean_citedness=4.0, works_2yr=None)
    normalize_impact_factors_bayes(db_session, org_id=None)
    assert r.nif_bayes is None


def test_bayes_zero_citedness_ci_nonnegative(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    for i in range(6):
        _mk(db_session, issn_l=f"D-{i}", nif_field="Biology",
            two_yr_mean_citedness=4.0, works_2yr=300)
    z = _mk(db_session, issn_l="D-z", nif_field="Biology",
            two_yr_mean_citedness=0.0, works_2yr=30)
    normalize_impact_factors_bayes(db_session, org_id=None)
    assert z.nif_bayes is not None and z.nif_ci_low >= 0.0


def test_bayes_small_bucket_uses_global_prior(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    for i in range(8):
        _mk(db_session, issn_l=f"E-{i}", nif_field="Medicine",
            two_yr_mean_citedness=5.0, works_2yr=400)
    lone = _mk(db_session, issn_l="E-lone", nif_field="Mathematics",
               two_yr_mean_citedness=3.0, works_2yr=50)
    n = normalize_impact_factors_bayes(db_session, org_id=None)
    assert lone.nif_bayes is not None   # computed via global-prior fallback, not skipped


def test_recompute_returns_both_counters(client, auth_headers, db_session):
    from backend.models import JournalMetric
    for i in range(6):
        db_session.add(JournalMetric(org_id=None, issn_l=f"R-{i}", nif_field="Medicine",
                                     two_yr_mean_citedness=5.0, works_2yr=400))
    db_session.commit()
    resp = client.post("/journals/normalize", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "updated" in body and "updated_bayes" in body
    assert body["updated_bayes"] == 6


def test_journals_api_exposes_nif_bayes(client, auth_headers, db_session):
    from backend.models import JournalMetric
    db_session.add(JournalMetric(org_id=None, issn_l="X-1", nif_field="Medicine",
                                 two_yr_mean_citedness=5.0, works_2yr=400,
                                 nif_bayes=1.02, nif_ci_low=0.8, nif_ci_high=1.25))
    db_session.commit()
    resp = client.get("/journals", headers=auth_headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["issn_l"] == "X-1")
    assert row["nif_bayes"] == 1.02
    assert row["nif_ci_low"] == 0.8 and row["nif_ci_high"] == 1.25


def test_backfill_populates_and_runs_batch(db_session):
    from backend.models import JournalMetric
    from backend.schemas_enrichment import JournalMetrics
    from backend.scripts.backfill_nif_bayes import run_backfill
    for i in range(6):
        db_session.add(JournalMetric(org_id=None, issn_l=f"BF-{i}", source_id=f"S{i}",
                                     nif_field="Medicine", two_yr_mean_citedness=5.0))
    db_session.commit()

    class _FakeAdapter:
        def fetch_source_metrics(self, source_id):
            return JournalMetrics(issn_l=None, source_id=source_id, works_2yr=400)

    updated = run_backfill(db_session, org_id=None, refresh=False, adapter=_FakeAdapter())
    assert updated == 6
    rows = db_session.query(JournalMetric).all()
    assert all(r.works_2yr == 400 for r in rows)
    assert all(r.nif_bayes is not None for r in rows)
