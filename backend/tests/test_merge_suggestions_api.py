"""F4b.3 — merge-suggestions confirm/reject API.

Confirm merges author_b into author_a (manual tier) and writes an audit row;
reject flips status. Admin-only.
"""
from backend import models


def _suggestion(db, *, with_pub_on_loser=True):
    a = models.Author(name_key="ms_winner", display_name="Jane Doe")
    b = models.Author(name_key="ms_loser", display_name="J. Doe")
    db.add_all([a, b])
    db.commit()
    db.refresh(a)
    db.refresh(b)
    if with_pub_on_loser:
        e = models.RawEntity(primary_label="paper", domain="default", org_id=None,
                             attributes_json="{}")
        db.add(e)
        db.commit()
        db.add(models.AuthorPublication(author_id=b.id, entity_id=e.id, org_id=0,
                                        domain_id="default", position=1))
        db.commit()
    s = models.AuthorMergeSuggestion(
        author_a_id=a.id, author_b_id=b.id, reason="last+initial", status="pending")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s, a, b


def test_confirm_requires_admin(client, viewer_headers, db_session):
    s, _a, _b = _suggestion(db_session)
    r = client.post(f"/coauthorship/merge-suggestions/{s.id}/confirm", headers=viewer_headers)
    assert r.status_code == 403


def test_confirm_merges_and_audits(client, auth_headers, db_session):
    s, a, b = _suggestion(db_session)
    s_id, a_id, b_id = s.id, a.id, b.id  # capture before the merge deletes the loser
    r = client.post(f"/coauthorship/merge-suggestions/{s_id}/confirm", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "merged"
    assert body["winner_author_id"] == a_id

    # Loser deleted, publication repointed to winner, audit written, suggestion merged.
    db_session.expire_all()
    assert db_session.query(models.Author).filter_by(id=b_id).first() is None
    pub = db_session.query(models.AuthorPublication).one()
    assert pub.author_id == a_id
    audit = db_session.query(models.AuthorMergeAudit).filter_by(loser_author_id=b_id).one()
    assert audit.tier == "manual"
    refreshed = db_session.query(models.AuthorMergeSuggestion).filter_by(id=s_id).one()
    assert refreshed.status == "merged"
    assert refreshed.author_a_id == a_id
    assert refreshed.author_b_id == a_id
    # Winner's scope enqueued for recompute.
    assert db_session.query(models.CoauthorDirtyScope).filter_by(org_id=0, domain_id="default").count() == 1


def test_confirm_handles_duplicate_publication_rows(client, auth_headers, db_session):
    s, a, b = _suggestion(db_session, with_pub_on_loser=False)
    e = models.RawEntity(primary_label="shared paper", domain="default", org_id=None,
                         attributes_json="{}")
    db_session.add(e)
    db_session.commit()
    db_session.add_all([
        models.AuthorPublication(author_id=a.id, entity_id=e.id, org_id=0,
                                 domain_id="default", position=1),
        models.AuthorPublication(author_id=b.id, entity_id=e.id, org_id=0,
                                 domain_id="default", position=2),
    ])
    db_session.commit()

    r = client.post(f"/coauthorship/merge-suggestions/{s.id}/confirm", headers=auth_headers)
    assert r.status_code == 200, r.text
    pubs = db_session.query(models.AuthorPublication).all()
    assert len(pubs) == 1
    assert pubs[0].author_id == a.id


def test_confirm_already_resolved_conflicts(client, auth_headers, db_session):
    s, _a, _b = _suggestion(db_session)
    first = client.post(f"/coauthorship/merge-suggestions/{s.id}/confirm", headers=auth_headers)
    assert first.status_code == 200
    second = client.post(f"/coauthorship/merge-suggestions/{s.id}/confirm", headers=auth_headers)
    assert second.status_code == 409


def test_confirm_missing_404(client, auth_headers):
    r = client.post("/coauthorship/merge-suggestions/999999/confirm", headers=auth_headers)
    assert r.status_code == 404


def test_reject_flips_status(client, auth_headers, db_session):
    s, a, b = _suggestion(db_session, with_pub_on_loser=False)
    r = client.post(f"/coauthorship/merge-suggestions/{s.id}/reject", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    # Both authors survive — rejecting keeps them distinct.
    assert db_session.query(models.Author).filter_by(id=a.id).first() is not None
    assert db_session.query(models.Author).filter_by(id=b.id).first() is not None
    db_session.expire_all()
    assert db_session.query(models.AuthorMergeSuggestion).filter_by(id=s.id).one().status == "rejected"


def test_reject_requires_admin(client, viewer_headers, db_session):
    s, _a, _b = _suggestion(db_session, with_pub_on_loser=False)
    r = client.post(f"/coauthorship/merge-suggestions/{s.id}/reject", headers=viewer_headers)
    assert r.status_code == 403
