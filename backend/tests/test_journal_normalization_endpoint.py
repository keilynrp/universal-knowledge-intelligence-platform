from backend.models import JournalMetric


def test_admin_can_trigger_normalization(client, auth_headers, db_session):
    db_session.add(JournalMetric(issn_l="A", two_yr_mean_citedness=2.0))
    db_session.add(JournalMetric(issn_l="B", two_yr_mean_citedness=4.0))
    db_session.commit()
    resp = client.post("/journals/normalize", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2


def test_viewer_forbidden(client, viewer_headers):
    resp = client.post("/journals/normalize", headers=viewer_headers)
    assert resp.status_code == 403
