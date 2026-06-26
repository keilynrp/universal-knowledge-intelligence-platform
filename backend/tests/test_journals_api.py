from backend.schemas import JournalMetricResponse, EntityAttributesDict


def test_journal_metric_response_shape():
    r = JournalMetricResponse(
        issn_l="0028-0836", display_name="Nat", source_id="S77",
        two_yr_mean_citedness=17.4, h_index=1200, normalized_impact_factor=1.5,
        nif_field="Genetics", apc_usd=11690, apc_currency="USD", apc_source="openalex",
        is_in_doaj=False, if_metric_kind="openalex_2yr_mean_citedness", nif_updated_at=None,
    )
    assert r.apc_usd == 11690 and r.nif_field == "Genetics"


def test_issn_l_documented_in_attributes_contract():
    assert "issn_l" in EntityAttributesDict.__annotations__


from backend.models import JournalMetric
from backend.services.journal_metrics_service import (
    get_journal_metric, list_journal_metrics, journal_stats,
)


def _seed(db, issn, nif=None, cited=None, apc=None, cur=None, doaj=None, field=None, org=None):
    db.add(JournalMetric(org_id=org, issn_l=issn, normalized_impact_factor=nif,
                         two_yr_mean_citedness=cited, apc_usd=apc, apc_currency=cur,
                         is_in_doaj=doaj, nif_field=field))


def test_get_journal_metric_scoped(db_session):
    _seed(db_session, "A", org=None); db_session.commit()
    assert get_journal_metric(db_session, None, "A").issn_l == "A"
    assert get_journal_metric(db_session, None, "ZZZ") is None


def test_list_sorted_and_total(db_session):
    _seed(db_session, "A", nif=0.5); _seed(db_session, "B", nif=2.0); db_session.commit()
    rows, total = list_journal_metrics(db_session, None, sort_by="nif", order="desc", limit=10, offset=0)
    assert total == 2 and [r.issn_l for r in rows] == ["B", "A"]


def test_list_org_isolation(db_session):
    _seed(db_session, "A", org=1); _seed(db_session, "B", org=2); db_session.commit()
    rows, total = list_journal_metrics(db_session, 1, sort_by="nif", order="desc", limit=10, offset=0)
    assert total == 1 and rows[0].issn_l == "A"


def test_stats_aggregates(db_session):
    _seed(db_session, "A", cited=2, apc=1000, cur="USD", doaj=True, field="AI", nif=0.5)
    _seed(db_session, "B", cited=6, apc=3000, cur="USD", doaj=False, field="AI", nif=1.5)
    _seed(db_session, "C", apc=900, cur="EUR", doaj=True, field="Genetics", nif=1.0)
    db_session.commit()
    s = journal_stats(db_session, None)
    usd = next(b for b in s["apc_distribution"] if b["currency"] == "USD")
    assert usd["count"] == 2 and usd["min"] == 1000 and usd["max"] == 3000 and usd["median"] == 2000.0
    assert s["open_access_share"] == {"in_doaj": 2, "total": 3, "pct": round(2/3*100, 1)}
    ai = next(f for f in s["nif_by_field"] if f["nif_field"] == "AI")
    assert ai["journal_count"] == 2 and ai["mean_nif"] == 1.0


def test_get_single_404(client, auth_headers):
    assert client.get("/journals/NOPE", headers=auth_headers).status_code == 404


def test_get_single_ok(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="0028-0836", normalized_impact_factor=1.5))
    db_session.commit()
    r = client.get("/journals/0028-0836", headers=auth_headers)
    assert r.status_code == 200 and r.json()["normalized_impact_factor"] == 1.5


def test_list_pagination_header_and_sort_validation(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="A", normalized_impact_factor=2.0))
    db_session.commit()
    r = client.get("/journals?sort_by=nif&order=desc&limit=10", headers=auth_headers)
    assert r.status_code == 200 and r.headers["X-Total-Count"] == "1"
    assert client.get("/journals?sort_by=bogus", headers=auth_headers).status_code == 422


def test_stats_route_not_shadowed(client, auth_headers):
    r = client.get("/journals/stats", headers=auth_headers)
    assert r.status_code == 200 and "apc_distribution" in r.json()


def test_journals_requires_auth(client):
    assert client.get("/journals/stats").status_code in (401, 403)


def test_list_sort_by_nif_bayes(db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="A", nif_bayes=0.5))
    db_session.add(JournalMetric(org_id=None, issn_l="B", nif_bayes=2.0))
    db_session.commit()
    rows, total = list_journal_metrics(db_session, None, sort_by="nif_bayes",
                                       order="desc", limit=10, offset=0)
    assert total == 2 and [r.issn_l for r in rows] == ["B", "A"]


def test_list_nif_bayes_nulls_sort_last(db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="HAS", nif_bayes=1.0))
    db_session.add(JournalMetric(org_id=None, issn_l="NULL1", nif_bayes=None))
    db_session.add(JournalMetric(org_id=None, issn_l="NULL2", nif_bayes=None))
    db_session.commit()
    rows, _ = list_journal_metrics(db_session, None, sort_by="nif_bayes",
                                   order="desc", limit=10, offset=0)
    assert rows[0].issn_l == "HAS"
    assert rows[-1].nif_bayes is None


def test_endpoint_accepts_nif_bayes_sort(client, auth_headers, db_session):
    db_session.add(JournalMetric(org_id=None, issn_l="A", nif_bayes=2.0))
    db_session.commit()
    r = client.get("/journals?sort_by=nif_bayes&order=desc", headers=auth_headers)
    assert r.status_code == 200
    assert client.get("/journals?sort_by=bogus", headers=auth_headers).status_code == 422
