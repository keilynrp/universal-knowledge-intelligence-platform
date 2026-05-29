"""F4a.2/F4a.3 — diagnostics, recompute, merge-suggestions, admin migrate.

auth_headers == bootstrap super_admin (org_id None -> unscoped view).
viewer_headers == viewer (org_id None -> legacy/global -> V2 sentinel org 0).
"""
from backend import models


def _seed_scope(db, *, domain, org_id=0, n_pairs=2):
    """Create n_pairs disjoint author pairs + edges in (org_id, domain)."""
    aid = 0
    made = []
    for p in range(n_pairs):
        a = models.Author(name_key=f"{domain}_a{p}", display_name=f"A{p} {domain}")
        b = models.Author(name_key=f"{domain}_b{p}", display_name=f"B{p} {domain}")
        db.add_all([a, b])
        db.commit()
        lo, hi = sorted([a.id, b.id])
        db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=org_id,
                                   domain_id=domain, weight=1))
        e = models.RawEntity(primary_label=f"p{p}", domain=domain, org_id=None,
                             attributes_json="{}")
        db.add(e)
        db.commit()
        db.add_all([
            models.AuthorPublication(author_id=a.id, entity_id=e.id, org_id=org_id,
                                     domain_id=domain, position=1),
            models.AuthorPublication(author_id=b.id, entity_id=e.id, org_id=org_id,
                                     domain_id=domain, position=2),
        ])
        db.commit()
        made.append((a.id, b.id))
    return made


def test_diagnostics_reports_pipeline_counters(client, auth_headers, db_session):
    _seed_scope(db_session, domain="default", n_pairs=2)
    r = client.get("/analyzers/coauthorship/default/diagnostics", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    for key in ("edges_in_storage", "edges_after_scope", "authors_total",
                "dirty_queue_depth", "coverage_pct", "scope_breakdown"):
        assert key in body
    assert body["edges_in_storage"] == 2
    assert body["authors_total"] == 4


def test_diagnostics_requires_auth(client):
    r = client.get("/analyzers/coauthorship/default/diagnostics")
    assert r.status_code in (401, 403)


def test_recompute_admin_only(client, viewer_headers):
    r = client.post("/analyzers/coauthorship/diag_recompute_v/recompute", headers=viewer_headers)
    assert r.status_code == 403


def test_recompute_materializes_stats(client, auth_headers, db_session):
    _seed_scope(db_session, domain="recompute_dom", n_pairs=3)
    r = client.post("/analyzers/coauthorship/recompute_dom/recompute", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scopes_recomputed"] >= 1
    assert db_session.query(models.AuthorStats).filter_by(domain_id="recompute_dom").count() == 6


def test_recompute_is_rate_limited(client, auth_headers, db_session):
    _seed_scope(db_session, domain="ratelimit_dom", n_pairs=1)
    first = client.post("/analyzers/coauthorship/ratelimit_dom/recompute", headers=auth_headers)
    assert first.status_code == 200
    second = client.post("/analyzers/coauthorship/ratelimit_dom/recompute", headers=auth_headers)
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_merge_suggestions_admin_only(client, viewer_headers):
    r = client.get("/coauthorship/merge-suggestions", headers=viewer_headers)
    assert r.status_code == 403


def test_merge_suggestions_lists_pending(client, auth_headers, db_session):
    a = models.Author(name_key="ms_a", display_name="Ann")
    b = models.Author(name_key="ms_b", display_name="Anne")
    db_session.add_all([a, b])
    db_session.commit()
    db_session.add(models.AuthorMergeSuggestion(
        author_a_id=a.id, author_b_id=b.id, reason="last+initial", status="pending"))
    db_session.commit()
    r = client.get("/coauthorship/merge-suggestions", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["author_a_name"] == "Ann"
    assert body[0]["reason"] == "last+initial"


def test_migrate_endpoint_admin_only(client, viewer_headers):
    r = client.post("/admin/data-fixes/migrate-coauthor-graph",
                    json={"dry_run": True}, headers=viewer_headers)
    assert r.status_code == 403


def test_migrate_endpoint_dry_run(client, auth_headers, db_session):
    import json as _json
    e = models.RawEntity(primary_label="paper", domain="default", org_id=None,
                         attributes_json=_json.dumps({"enrichment_authors": ["X Y", "Z W"]}))
    db_session.add(e)
    db_session.commit()
    r = client.post("/admin/data-fixes/migrate-coauthor-graph",
                    json={"dry_run": True}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "dry-run"
    assert body["entities_with_authors"] == 1
    assert db_session.query(models.Author).count() == 0  # dry-run wrote nothing
