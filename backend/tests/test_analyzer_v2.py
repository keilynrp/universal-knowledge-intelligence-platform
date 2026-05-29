"""F4b.1 — V2 coauthorship network reader behind COAUTHOR_V2_READ.

Reads materialized author_stats + coauthor_edges. auth_headers == super_admin
(org_id None -> unscoped); viewer_headers == viewer (org_id None -> legacy ->
V2 sentinel org 0).
"""
import pytest

from backend import config, models


@pytest.fixture
def read_on(monkeypatch):
    monkeypatch.setattr(config, "COAUTHOR_V2_READ", True)


def _author(db, name_key, name):
    a = models.Author(name_key=name_key, display_name=name)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _edge(db, a, b, *, domain, org_id, weight):
    lo, hi = sorted([a.id, b.id])
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=org_id,
                              domain_id=domain, weight=weight))


def _stat(db, author, *, domain, org_id, degree, centrality, community):
    db.add(models.AuthorStats(author_id=author.id, org_id=org_id, domain_id=domain,
                              degree=degree, centrality=centrality,
                              community_id=community, publication_count=degree))


def _seed(db, *, domain="default", org_id=0):
    a = _author(db, f"{domain}{org_id}_a", "Alice")
    b = _author(db, f"{domain}{org_id}_b", "Bob")
    c = _author(db, f"{domain}{org_id}_c", "Carol")
    d = _author(db, f"{domain}{org_id}_d", "Dan")
    e = _author(db, f"{domain}{org_id}_e", "Eve")
    _edge(db, a, b, domain=domain, org_id=org_id, weight=3)
    _edge(db, b, c, domain=domain, org_id=org_id, weight=1)
    _edge(db, d, e, domain=domain, org_id=org_id, weight=2)
    _stat(db, b, domain=domain, org_id=org_id, degree=2, centrality=0.9, community=0)
    _stat(db, a, domain=domain, org_id=org_id, degree=1, centrality=0.5, community=0)
    _stat(db, c, domain=domain, org_id=org_id, degree=1, centrality=0.4, community=0)
    _stat(db, d, domain=domain, org_id=org_id, degree=1, centrality=0.3, community=1)
    _stat(db, e, domain=domain, org_id=org_id, degree=1, centrality=0.2, community=1)
    db.commit()
    return {"a": a, "b": b, "c": c, "d": d, "e": e}


def test_fallthrough_when_flag_off(client, auth_headers):
    # Flag off (default) -> legacy analyzer; shape preserved.
    r = client.get("/analyzers/coauthorship/default", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body and "edges" in body


def test_empty_scope(client, auth_headers, read_on):
    r = client.get("/analyzers/coauthorship/default", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["nodes"] == []
    assert body["edges"] == []
    assert body["computed_at"] is None
    assert body["stale"] is False
    assert body["coverage_pct"] == 0.0


def test_nodes_sorted_by_centrality(client, auth_headers, read_on, db_session):
    _seed(db_session)
    r = client.get("/analyzers/coauthorship/default", headers=auth_headers)
    assert r.status_code == 200
    nodes = r.json()["nodes"]
    assert [n["label"] for n in nodes[:3]] == ["Bob", "Alice", "Carol"]


def test_min_weight_filter(client, auth_headers, read_on, db_session):
    _seed(db_session)
    r = client.get("/analyzers/coauthorship/default?min_weight=2", headers=auth_headers)
    weights = sorted(e["weight"] for e in r.json()["edges"])
    assert weights == [2, 3]  # Bob-Carol (1) excluded


def test_community_filter(client, auth_headers, read_on, db_session):
    _seed(db_session)
    r = client.get("/analyzers/coauthorship/default?community_id=1", headers=auth_headers)
    labels = {n["label"] for n in r.json()["nodes"]}
    assert labels == {"Dan", "Eve"}


def test_search_filter_case_insensitive(client, auth_headers, read_on, db_session):
    _seed(db_session)
    r = client.get("/analyzers/coauthorship/default?search=ali", headers=auth_headers)
    labels = [n["label"] for n in r.json()["nodes"]]
    assert labels == ["Alice"]


def test_limit_caps_nodes_and_prunes_edges(client, auth_headers, read_on, db_session):
    _seed(db_session)
    r = client.get("/analyzers/coauthorship/default?limit=2", headers=auth_headers)
    body = r.json()
    assert len(body["nodes"]) == 2  # Bob, Alice
    # Only edges between surviving nodes: Bob-Alice (weight 3) survives.
    assert all(
        {e["source"], e["target"]} <= {body["nodes"][0]["id"], body["nodes"][1]["id"]}
        for e in body["edges"]
    )


def test_scope_isolation_viewer_vs_super_admin(client, auth_headers, viewer_headers, read_on, db_session):
    _seed(db_session, org_id=0)   # legacy/global scope
    _seed(db_session, org_id=5)   # a tenant
    # super_admin (org None) -> unscoped -> sees both scopes' authors
    admin_nodes = client.get("/analyzers/coauthorship/default", headers=auth_headers).json()["nodes"]
    assert len(admin_nodes) == 10
    # viewer (org None -> legacy -> sentinel 0) -> only org 0
    viewer_nodes = client.get("/analyzers/coauthorship/default", headers=viewer_headers).json()["nodes"]
    assert len(viewer_nodes) == 5


# ── F4b.2: author detail ─────────────────────────────────────────────────────


def _seed_author_detail(db, *, domain="default", org_id=0):
    import json
    hub = _author(db, "det_hub", "Hub")
    c1 = _author(db, "det_c1", "Collab One")
    c2 = _author(db, "det_c2", "Collab Two")
    _edge(db, hub, c1, domain=domain, org_id=org_id, weight=5)
    _edge(db, hub, c2, domain=domain, org_id=org_id, weight=2)
    _stat(db, hub, domain=domain, org_id=org_id, degree=2, centrality=0.8, community=3)
    e1 = models.RawEntity(primary_label="Old Paper", domain=domain, org_id=None,
                          attributes_json=json.dumps({"year": 2010}))
    e2 = models.RawEntity(primary_label="New Paper", domain=domain, org_id=None,
                          attributes_json=json.dumps({"title": "Newer", "publication_year": 2022}))
    db.add_all([e1, e2])
    db.commit()
    db.add_all([
        models.AuthorPublication(author_id=hub.id, entity_id=e1.id, org_id=org_id,
                                 domain_id=domain, position=1),
        models.AuthorPublication(author_id=hub.id, entity_id=e2.id, org_id=org_id,
                                 domain_id=domain, position=1),
    ])
    db.commit()
    return hub, c1, c2


def test_author_detail_404_for_missing(client, auth_headers):
    r = client.get("/analyzers/coauthorship/default/author/999999", headers=auth_headers)
    assert r.status_code == 404


def test_author_detail_header_and_metrics(client, auth_headers, db_session):
    hub, _c1, _c2 = _seed_author_detail(db_session)
    r = client.get(f"/analyzers/coauthorship/default/author/{hub.id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Hub"
    assert body["metrics"]["community_id"] == 3
    assert body["metrics"]["centrality"] == 0.8


def test_author_detail_collaborators_sorted_by_weight(client, auth_headers, db_session):
    hub, _c1, _c2 = _seed_author_detail(db_session)
    r = client.get(f"/analyzers/coauthorship/default/author/{hub.id}", headers=auth_headers)
    collabs = r.json()["collaborators"]
    assert [(c["name"], c["weight"]) for c in collabs] == [("Collab One", 5), ("Collab Two", 2)]


def test_author_detail_publications_sorted_by_year_desc(client, auth_headers, db_session):
    hub, _c1, _c2 = _seed_author_detail(db_session)
    r = client.get(f"/analyzers/coauthorship/default/author/{hub.id}", headers=auth_headers)
    pubs = r.json()["publications"]
    assert [p["title"] for p in pubs] == ["Newer", "Old Paper"]
    assert [p["year"] for p in pubs] == [2022, 2010]


def test_backfill_visibility_after_recompute(client, auth_headers, read_on, db_session):
    """Regression for the original bug: edges written under org 0 must be VISIBLE
    after recompute materializes stats — no tenancy-scope mismatch."""
    from backend.coauthorship.recompute import recompute_coauthor_stats

    a = _author(db_session, "vis_a", "Anna")
    b = _author(db_session, "vis_b", "Ben")
    _edge(db_session, a, b, domain="default", org_id=0, weight=1)
    db_session.commit()
    recompute_coauthor_stats(db_session, org_id=0, domain_id="default")

    body = client.get("/analyzers/coauthorship/default", headers=auth_headers).json()
    assert len(body["nodes"]) == 2
    assert body["computed_at"] is not None
    labels = {n["label"] for n in body["nodes"]}
    assert labels == {"Anna", "Ben"}


def test_network_auto_materializes_stats_when_edges_exist(client, auth_headers, read_on, db_session):
    """Production cutover guard: if migration wrote edges but the recompute
    worker/script did not materialize author_stats, the first graph request
    should repair the scope and return data instead of a blank graph."""
    a = _author(db_session, "auto_a", "Auto Anna")
    b = _author(db_session, "auto_b", "Auto Ben")
    _edge(db_session, a, b, domain="science", org_id=0, weight=4)
    db_session.commit()

    assert db_session.query(models.AuthorStats).filter_by(domain_id="science").count() == 0

    r = client.get("/analyzers/coauthorship/science", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert {n["label"] for n in body["nodes"]} == {"Auto Anna", "Auto Ben"}
    assert body["edges"] == [{"source": str(a.id), "target": str(b.id), "weight": 4}]
    assert db_session.query(models.AuthorStats).filter_by(domain_id="science").count() == 2


def test_network_falls_back_to_populated_coauthor_domain(client, auth_headers, read_on, db_session):
    a = _author(db_session, "fallback_a", "Fallback Anna")
    b = _author(db_session, "fallback_b", "Fallback Ben")
    _edge(db_session, a, b, domain="science", org_id=0, weight=2)
    db_session.commit()

    r = client.get("/analyzers/coauthorship/all", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["requested_domain_id"] == "all"
    assert body["domain_id"] == "science"
    assert {n["label"] for n in body["nodes"]} == {"Fallback Anna", "Fallback Ben"}


def test_network_serves_v2_edges_even_when_read_flag_off(client, auth_headers, monkeypatch, db_session):
    monkeypatch.setattr(config, "COAUTHOR_V2_READ", False)
    a = _author(db_session, "flag_off_a", "Flag Off Anna")
    b = _author(db_session, "flag_off_b", "Flag Off Ben")
    _edge(db_session, a, b, domain="science", org_id=0, weight=3)
    db_session.commit()

    r = client.get("/analyzers/coauthorship/all", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["requested_domain_id"] == "all"
    assert body["domain_id"] == "science"
    assert {n["label"] for n in body["nodes"]} == {"Flag Off Anna", "Flag Off Ben"}
