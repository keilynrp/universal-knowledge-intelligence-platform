"""Step 2 of the journal-metrics feature: capture the OpenAlex primary subfield
into `nif_field` so the Normalized Impact Factor is normalized per-discipline
instead of against a single global bucket."""
from unittest.mock import MagicMock

from backend.adapters.enrichment.openalex import OpenAlexAdapter, _SOURCE_CACHE
from backend.cache import make_key
from backend.models import JournalMetric
from backend.schemas_enrichment import JournalMetrics
from backend.services.journal_metrics_service import upsert_journal_metric
from backend.analyzers.journal_normalization import normalize_impact_factors


def _source_body(topics):
    return {
        "id": "https://openalex.org/S77",
        "display_name": "Nat",
        "issn_l": "0028-0836",
        "summary_stats": {"2yr_mean_citedness": 17.4, "h_index": 1200},
        "apc_usd": 11690,
        "is_in_doaj": False,
        "topics": topics,
    }


def _clear(sid):
    _SOURCE_CACHE.delete(make_key(("source", sid)))


# ── NDO ──────────────────────────────────────────────────────────────────────
def test_journal_metrics_ndo_has_nif_field():
    jm = JournalMetrics(nif_field="Artificial Intelligence")
    assert jm.nif_field == "Artificial Intelligence"
    assert JournalMetrics().nif_field is None


# ── OpenAlex extraction ──────────────────────────────────────────────────────
def test_fetch_source_metrics_captures_primary_subfield(monkeypatch):
    _clear("S77")
    adapter = OpenAlexAdapter()
    fake = MagicMock(status_code=200)
    fake.json.return_value = _source_body([
        {"display_name": "Deep learning", "count": 500,
         "subfield": {"id": "https://openalex.org/subfields/1702", "display_name": "Artificial Intelligence"}},
        {"display_name": "Genomics", "count": 100,
         "subfield": {"id": "https://openalex.org/subfields/1311", "display_name": "Genetics"}},
    ])
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    jm = adapter.fetch_source_metrics("S77")
    assert jm.nif_field == "Artificial Intelligence"  # top topic (highest count) wins


def test_fetch_source_metrics_picks_highest_count_subfield_regardless_of_order(monkeypatch):
    _clear("S77b")
    adapter = OpenAlexAdapter()
    body = _source_body([
        {"display_name": "Genomics", "count": 100,
         "subfield": {"display_name": "Genetics"}},
        {"display_name": "Deep learning", "count": 900,  # highest count, listed second
         "subfield": {"display_name": "Artificial Intelligence"}},
    ])
    body["id"] = "https://openalex.org/S77b"
    fake = MagicMock(status_code=200)
    fake.json.return_value = body
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    jm = adapter.fetch_source_metrics("S77b")
    assert jm.nif_field == "Artificial Intelligence"


def test_fetch_source_metrics_subfield_none_when_no_topics(monkeypatch):
    _clear("S78")
    adapter = OpenAlexAdapter()
    body = _source_body([])
    body["id"] = "https://openalex.org/S78"
    fake = MagicMock(status_code=200)
    fake.json.return_value = body
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    jm = adapter.fetch_source_metrics("S78")
    assert jm.nif_field is None


def test_fetch_source_metrics_subfield_none_when_topic_lacks_subfield(monkeypatch):
    _clear("S79")
    adapter = OpenAlexAdapter()
    body = _source_body([{"display_name": "Mystery", "count": 5}])  # no "subfield" key
    body["id"] = "https://openalex.org/S79"
    fake = MagicMock(status_code=200)
    fake.json.return_value = body
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    jm = adapter.fetch_source_metrics("S79")
    assert jm.nif_field is None


# ── upsert persists nif_field ────────────────────────────────────────────────
def test_upsert_persists_nif_field(db_session):
    jm = JournalMetrics(issn_l="0028-0836", source_id="S77",
                        two_yr_mean_citedness=17.4, nif_field="Artificial Intelligence")
    row = upsert_journal_metric(db_session, jm, org_id=None)
    assert row.nif_field == "Artificial Intelligence"


def test_upsert_upgrades_all_bucket_to_real_subfield(db_session):
    # A subfield-less journal gets nif_field="all" written by the normalizer;
    # a later enrichment that discovers the real subfield must replace "all".
    db_session.add(JournalMetric(issn_l="0028-0836", two_yr_mean_citedness=4.0))
    db_session.commit()
    normalize_impact_factors(db_session, org_id=None)
    stuck = db_session.query(JournalMetric).filter_by(issn_l="0028-0836").one()
    assert stuck.nif_field == "all"

    row = upsert_journal_metric(db_session, JournalMetrics(
        issn_l="0028-0836", source_id="S77", nif_field="Artificial Intelligence"), org_id=None)
    assert row.nif_field == "Artificial Intelligence"


def test_upsert_does_not_clobber_existing_nif_field_with_none(db_session):
    upsert_journal_metric(db_session, JournalMetrics(
        issn_l="0028-0836", source_id="S77", nif_field="Artificial Intelligence"), org_id=None)
    # a later upsert without a subfield (e.g. cached pre-subfield entry) must not wipe it
    row = upsert_journal_metric(db_session, JournalMetrics(
        issn_l="0028-0836", source_id="S77", two_yr_mean_citedness=18.0), org_id=None)
    assert row.nif_field == "Artificial Intelligence"


# ── normalizer buckets per real subfield ─────────────────────────────────────
def test_normalization_is_per_subfield(db_session):
    # Field A: medians among AI journals; Field B: among Genetics journals — independent.
    db_session.add(JournalMetric(issn_l="A1", two_yr_mean_citedness=2.0, nif_field="Artificial Intelligence"))
    db_session.add(JournalMetric(issn_l="A2", two_yr_mean_citedness=6.0, nif_field="Artificial Intelligence"))  # AI median = 4.0
    db_session.add(JournalMetric(issn_l="B1", two_yr_mean_citedness=10.0, nif_field="Genetics"))
    db_session.add(JournalMetric(issn_l="B2", two_yr_mean_citedness=30.0, nif_field="Genetics"))  # Gen median = 20.0
    db_session.commit()

    updated = normalize_impact_factors(db_session, org_id=None)
    assert updated == 4
    rows = {r.issn_l: r for r in db_session.query(JournalMetric).all()}
    assert rows["A1"].normalized_impact_factor == 0.5   # 2/4
    assert rows["A2"].normalized_impact_factor == 1.5   # 6/4
    assert rows["B1"].normalized_impact_factor == 0.5   # 10/20
    assert rows["B2"].normalized_impact_factor == 1.5   # 30/20
