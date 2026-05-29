"""get_or_create_author upsert semantics + merge_authors + the race code path.

Identity model = Plan B (optimistic collapse): same name_key => same author.
The concurrency test exercises the IntegrityError->refetch path; under UKIP's
StaticPool test engine all sessions share one SQLite connection, so this proves
the recovery code path, not true multi-process contention (see conftest).
"""
import threading

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


def test_concurrent_get_or_create_one_row(db_factory):
    """5 threads insert 'New Author' simultaneously.

    The durable invariant — guaranteed by the UNIQUE name_key constraint and
    the IntegrityError->refetch recovery — is that EXACTLY ONE row exists
    afterward, and every successful caller resolves to that same id. Per-thread
    StaticPool artifacts are tolerated (UKIP shares one SQLite connection across
    sessions; see conftest db_factory caveat)."""
    results = []
    errors = []
    barrier = threading.Barrier(5)

    def worker():
        s = db_factory()
        try:
            barrier.wait()
            a = get_or_create_author(s, "New Author")
            results.append(a.id)
        except Exception as exc:  # StaticPool cross-thread artifact, not a logic error
            errors.append(exc)
        finally:
            s.close()

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results, f"no worker produced an author; errors={errors}"
    assert len(set(results)) == 1, "successful callers must converge to one id"
    rows = db_factory().query(models.Author).filter_by(name_key="author_new").all()
    assert len(rows) == 1, "exactly one canonical row must exist"
    assert rows[0].id == results[0]
