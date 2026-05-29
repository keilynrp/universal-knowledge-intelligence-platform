"""F6 — merge-suggestion producer tests."""
from backend import models
from backend.coauthorship.suggestions import generate_merge_suggestions


def _author(db, name_key, name=None):
    a = models.Author(name_key=name_key, display_name=name or name_key)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_enqueues_last_initial_ambiguous_pair(db):
    _author(db, "smith_j", "J. Smith")
    _author(db, "smith_john", "John Smith")
    stats = generate_merge_suggestions(db)
    assert stats["suggestions_created"] == 1
    s = db.query(models.AuthorMergeSuggestion).one()
    assert s.status == "pending"
    assert "initial" in s.reason


def test_distinct_authors_produce_no_suggestion(db):
    _author(db, "smith_john", "John Smith")
    _author(db, "lee_amy", "Amy Lee")          # different family name
    _author(db, "smith_jane", "Jane Smith")    # same family, full first names -> distinct
    stats = generate_merge_suggestions(db)
    assert stats["suggestions_created"] == 0
    assert db.query(models.AuthorMergeSuggestion).count() == 0


def test_idempotent_no_duplicates(db):
    _author(db, "smith_j", "J. Smith")
    _author(db, "smith_john", "John Smith")
    generate_merge_suggestions(db)
    generate_merge_suggestions(db)
    assert db.query(models.AuthorMergeSuggestion).count() == 1


def test_rejected_pair_not_recreated(db):
    a = _author(db, "smith_j", "J. Smith")
    b = _author(db, "smith_john", "John Smith")
    lo, hi = sorted([a.id, b.id])
    db.add(models.AuthorMergeSuggestion(author_a_id=lo, author_b_id=hi,
                                        reason="manual", status="rejected"))
    db.commit()
    stats = generate_merge_suggestions(db)
    assert stats["suggestions_created"] == 0
    # The rejected row stays rejected; no new pending row appears.
    assert db.query(models.AuthorMergeSuggestion).filter_by(status="pending").count() == 0


def test_generate_endpoint_admin_only(client, viewer_headers):
    r = client.post("/coauthorship/merge-suggestions/generate", headers=viewer_headers)
    assert r.status_code == 403


def test_generate_endpoint_creates_and_lists(client, auth_headers, db_session):
    _author(db_session, "doe_j", "J. Doe")
    _author(db_session, "doe_jane", "Jane Doe")
    gen = client.post("/coauthorship/merge-suggestions/generate", headers=auth_headers)
    assert gen.status_code == 200, gen.text
    assert gen.json()["suggestions_created"] == 1
    listed = client.get("/coauthorship/merge-suggestions", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
