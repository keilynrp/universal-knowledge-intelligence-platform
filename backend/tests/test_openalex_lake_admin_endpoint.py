"""Admin endpoint for the OpenAlex lake operational status."""


def test_requires_admin_role(client, viewer_headers):
    r = client.get("/admin/openalex-lake/status", headers=viewer_headers)
    assert r.status_code == 403


def test_returns_not_initialized_when_lake_missing(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENALEX_LAKE_DB", str(tmp_path / "nope.duckdb"))
    r = client.get("/admin/openalex-lake/status", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["lake"] == "not_initialized"


def test_views_catalog_requires_admin_and_lists_axes(client, auth_headers, viewer_headers):
    assert client.get("/admin/openalex-lake/views", headers=viewer_headers).status_code == 403
    r = client.get("/admin/openalex-lake/views", headers=auth_headers)
    assert r.status_code == 200
    axes = {entry["axis"] for entry in r.json()["axes"]}
    assert "journal_scientometrics" in axes and "collaboration_networks" in axes


def test_query_endpoint_guards_and_happy_path(client, auth_headers, viewer_headers, monkeypatch, tmp_path):
    from backend.openalex_lake.store import LakeStore
    from backend.openalex_lake.transform import transform_work

    db_path = str(tmp_path / "lake.duckdb")
    with LakeStore(db_path) as store:
        store.ingest_work_rows(transform_work({
            "id": "https://openalex.org/W1",
            "publication_year": 2018,
            "cited_by_count": 42,
            "primary_location": {"source": {"id": "https://openalex.org/S1", "issn_l": "0028-0836"}},
        }))
    monkeypatch.setenv("OPENALEX_LAKE_DB", db_path)

    assert client.get("/admin/openalex-lake/query/v_journal_yearly",
                      headers=viewer_headers).status_code == 403
    assert client.get("/admin/openalex-lake/query/fact_works",
                      headers=auth_headers).status_code == 404  # table, not a whitelisted view
    assert client.get("/admin/openalex-lake/query/v_journal_yearly?order_by=bogus",
                      headers=auth_headers).status_code == 422

    r = client.get(
        "/admin/openalex-lake/query/v_journal_yearly?issn_l=0028-0836&order_by=citations",
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    row = dict(zip(body["columns"], body["rows"][0]))
    assert row["issn_l"] == "0028-0836" and row["citations"] == 42


def test_query_endpoint_not_initialized(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setenv("OPENALEX_LAKE_DB", str(tmp_path / "nope.duckdb"))
    r = client.get("/admin/openalex-lake/query/v_journal_yearly", headers=auth_headers)
    assert r.status_code == 200 and r.json()["lake"] == "not_initialized"


def test_returns_lake_status_when_present(client, auth_headers, monkeypatch, tmp_path, db_session):
    from backend.models import JournalMetric
    from backend.openalex_lake.store import LakeStore
    from backend.openalex_lake.transform import transform_work

    db_session.add_all([
        JournalMetric(issn_l="0028-0836", normalized_impact_factor=1.0),
        JournalMetric(issn_l="1476-4687", normalized_impact_factor=1.0),
    ])
    db_session.commit()

    db_path = str(tmp_path / "lake.duckdb")
    with LakeStore(db_path) as store:
        store.ingest_work_rows(transform_work({
            "id": "https://openalex.org/W1",
            "publication_year": 2018,
            "primary_location": {"source": {"id": "https://openalex.org/S1", "issn_l": "0028-0836"}},
        }))
        store.set_rate_limit_snapshot({"limit": 10000, "remaining": 9412})

    monkeypatch.setenv("OPENALEX_LAKE_DB", db_path)
    r = client.get("/admin/openalex-lake/status", headers=auth_headers)
    body = r.json()
    assert r.status_code == 200
    assert body["tables"]["fact_works"] == 1
    assert body["rate_limit"]["remaining"] == 9412
    assert body["backfill_total_issns"] == 2
