"""Classifier maps (Author A, Author B) -> 'strong' | 'probable' | 'ambiguous' | 'distinct'.

Identity model decision: name_key is UNIQUE ("optimistic collapse + ORCID
override" — see spec §4 note). Two PERSISTED authors therefore always have
distinct name_keys, so the classifier's real production value is:
  - ORCID match    -> strong   (authoritative, regardless of name)
  - ORCID conflict -> distinct (different people even if names match)
  - near-miss keys (smith_j vs smith_john) -> ambiguous review queue (C3/H1)
  - unrelated      -> distinct

The same-name_key branches (strong-via-shared-pub, probable-via-affiliation)
are reachable only when classify_merge is handed a TRANSIENT candidate that
collides with a stored author; one defensive test covers the bare-collision
path. Full same-name splitting is deferred (Plan A, follow-up sprint).
"""
from backend import models
from backend.coauthorship.identity import classify_merge


def _author(db, name_key, **kw):
    a = models.Author(
        name_key=name_key,
        display_name=kw.get("display_name", name_key),
        orcid=kw.get("orcid"),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_strong_orcid_match(db):
    # ORCID is UNIQUE, so two stored authors can't share one. The strong tier
    # is reached only when a transient candidate carries a matching ORCID
    # (the equality check is pure-Python — no DB write).
    a = _author(db, "smith_john", orcid="0000-0000-0000-0001")
    b = models.Author(name_key="smith_jonathan", display_name="Jonathan Smith",
                       orcid="0000-0000-0000-0001")
    d = classify_merge(db, a, b)
    assert d.tier == "strong"
    assert "orcid" in d.reason


def test_orcid_conflict_is_distinct(db):
    # Different ORCIDs -> different people, even when names are close.
    a = _author(db, "smith_john", orcid="0000-0000-0000-0001")
    b = _author(db, "smith_jon", orcid="0000-0000-0000-0002")
    d = classify_merge(db, a, b)
    assert d.tier == "distinct"
    assert "orcid conflict" in d.reason


def test_last_plus_initial_is_ambiguous(db):
    """'J. Smith' (smith_j) vs 'John Smith' (smith_john) -> ambiguous queue,
    never auto-merged. This is the primary architect concern (C3/H1)."""
    a = _author(db, "smith_j")
    b = _author(db, "smith_john")
    d = classify_merge(db, a, b)
    assert d.tier == "ambiguous"


def test_distinct_when_unrelated(db):
    a = _author(db, "smith_john")
    b = _author(db, "lee_amy")
    d = classify_merge(db, a, b)
    assert d.tier == "distinct"


def test_bare_namekey_collision_ambiguous_with_transient_candidate(db):
    """Defensive: if a transient candidate shares a stored author's name_key
    but carries no disambiguator (no ORCID, no shared publication/affiliation),
    the decision must be 'ambiguous' — never an auto-merge.

    The candidate is intentionally NOT committed (the UNIQUE constraint would
    reject it); classify_merge must operate on the in-memory pair."""
    stored = _author(db, "smith_john")
    candidate = models.Author(name_key="smith_john", display_name="John Smith")
    # candidate has no id -> no publications/affiliations resolvable
    d = classify_merge(db, stored, candidate)
    assert d.tier == "ambiguous"
    assert "without disambiguator" in d.reason
