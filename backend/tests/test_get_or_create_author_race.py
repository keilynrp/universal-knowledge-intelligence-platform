"""get_or_create_author upsert semantics + merge_authors + the race code path.

Identity model = Plan B (optimistic collapse): same name_key => same author.

The "lost race" recovery (IntegrityError -> rollback -> refetch) is verified
DETERMINISTICALLY by forcing the pre-insert existence check to miss exactly
once. A real-thread test was rejected: UKIP's StaticPool test engine shares one
SQLite connection across sessions, so concurrent commits are non-deterministic
and produce flaky results under full-suite load — the recovery *code path* is
what matters, and this proves it without flakiness.
"""
from sqlalchemy.orm import Query

from backend import models
from backend.coauthorship.identity import get_or_create_author, merge_authors


def test_get_or_create_returns_existing(db):
    a1 = get_or_create_author(db, "John Smith")
    a2 = get_or_create_author(db, "John Smith")
    assert a1.id == a2.id


def test_get_or_create_distinct_namekeys_are_separate(db):
    # "John Smith" -> smith_john, "J. SMITH" -> smith_j : different authors.
    a = get_or_create_author(db, "John Smith")
    b = get_or_create_author(db, "J. SMITH")
    assert a.id != b.id


def test_get_or_create_collapses_same_namekey(db):
    a = get_or_create_author(db, "Smith, John")
    b = get_or_create_author(db, "John Smith")
    assert a.id == b.id
    aliases = a.aliases_list
    assert "Smith, John" in aliases
    assert "John Smith" in aliases


def test_get_or_create_adopts_orcid(db):
    a = get_or_create_author(db, "John Smith")
    assert a.orcid is None
    again = get_or_create_author(db, "John Smith", orcid="0000-0000-0000-0009")
    assert again.id == a.id
    assert again.orcid == "0000-0000-0000-0009"


def test_merge_authors_moves_publications_and_writes_audit(db):
    winner = get_or_create_author(db, "Smith, John")          # smith_john
    loser = get_or_create_author(db, "Jonathan Smith")        # smith_jonathan (distinct)
    assert winner.id != loser.id
    e = models.RawEntity(primary_label="p", domain="default", attributes_json="{}")
    db.add(e)
    db.commit()
    db.add(models.AuthorPublication(author_id=loser.id, entity_id=e.id, org_id=0,
                                    domain_id="default", position=1))
    db.commit()

    merge_authors(db, winner, loser, tier="manual", reason="test")
    db.commit()

    assert db.query(models.Author).filter_by(id=loser.id).first() is None
    pub = db.query(models.AuthorPublication).filter_by(entity_id=e.id).one()
    assert pub.author_id == winner.id
    audit = db.query(models.AuthorMergeAudit).filter_by(loser_author_id=loser.id).one()
    assert audit.tier == "manual"
    assert loser.display_name in winner.aliases_list


def test_get_or_create_recovers_from_lost_race(db, monkeypatch):
    """A concurrent writer can insert the same name_key between our existence
    check and our INSERT. Simulate that 'lost race' by forcing the existence
    check to miss exactly once: get_or_create then attempts an INSERT that
    collides on the UNIQUE name_key, raises IntegrityError, rolls back, and
    refetches the canonical row. Result must converge to one id, one row."""
    canonical = get_or_create_author(db, "New Author")  # creates the real row
    key = canonical.name_key

    real_first = Query.first
    state = {"missed": False}

    def flaky_first(self):
        # Miss only the very next existence check (the one inside the second
        # get_or_create_author call), then behave normally.
        if not state["missed"]:
            state["missed"] = True
            return None
        return real_first(self)

    monkeypatch.setattr(Query, "first", flaky_first, raising=True)

    again = get_or_create_author(db, "New Author")
    monkeypatch.undo()

    assert again.id == canonical.id, "lost-race recovery must return the canonical row"
    assert db.query(models.Author).filter_by(name_key=key).count() == 1
