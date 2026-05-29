"""Author identity engine — deterministic, pure-Python.

Public API:
- name_key(surface_form: str) -> str
- classify_merge(db, a, b) -> MergeDecision
- get_or_create_author(db, surface_form, *, orcid=None) -> Author
- merge_authors(db, winner, loser, *, tier, reason, performed_by=None, evidence=None)
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.exc import IntegrityError

_ALIAS_CAP = 50

_STRIP_PARTS = {
    "dr", "dr.", "prof", "prof.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.",
    "phd", "ph.d", "md", "m.d", "jr", "jr.", "sr", "sr.", "iii", "iv", "ii",
}
_PARTICLES = {
    "van", "der", "den", "de", "du", "la", "del", "da", "dos",
    "el", "al", "von", "di",
}


def _strip_diacritics(s: str) -> str:
    # Decompose, drop combining marks, then RE-COMPOSE (NFC). The final NFC is
    # essential for Hangul: NFD splits syllables (e.g. 김) into conjoining jamo
    # which would otherwise defeat East-Asian surname detection. Latin letters
    # are unaffected (José -> Jose either way).
    stripped = "".join(
        c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)
    )
    return unicodedata.normalize("NFC", stripped)


def _tokenize(surface: str) -> list[str]:
    return [t for t in re.split(r"\s+", surface.strip()) if t]


def _alpha_lower(tok: str) -> str:
    return "".join(ch for ch in tok if ch.isalpha() or ch == "-").lower()


def _is_cjk_char(ch: str) -> bool:
    """True for Han ideographs (CJK Unified + Ext-A + Compatibility) and
    Hangul syllables — scripts that order the family name first."""
    return (
        "㐀" <= ch <= "鿿"   # CJK Unified Ideographs (+ Ext-A)
        or "豈" <= ch <= "﫿"  # CJK Compatibility Ideographs
        or "가" <= ch <= "힣"  # Hangul syllables
    )


def _is_cjk_token(tok: str) -> bool:
    letters = [c for c in tok if c.isalpha()]
    return bool(letters) and all(_is_cjk_char(c) for c in letters)


def name_key(surface_form: str) -> str:
    """Canonical fingerprint. Deterministic. Empty input -> empty string."""
    if not surface_form or not surface_form.strip():
        return ""

    s = _strip_diacritics(surface_form)
    inverted = "," in s
    if inverted:
        left, right = s.split(",", 1)
        toks_last = _tokenize(left)
        toks_first = _tokenize(right)
        # "John Smith, PhD" / "John Smith, Jr." are NOT "Last, First" — the
        # comma only fences off a suffix/title. If the right side is empty
        # once suffixes are stripped, reparse the left side as a normal name.
        right_meaningful = [
            t for t in toks_first if t.rstrip(".").lower() not in _STRIP_PARTS
        ]
        if not right_meaningful and len(toks_last) > 1:
            inverted = False
            s = left

    if not inverted:
        toks = _tokenize(s)
        toks = [t for t in toks if t.rstrip(".").lower() not in _STRIP_PARTS]
        if not toks:
            return ""
        if len(toks) >= 2 and all(_is_cjk_token(t) for t in toks):
            # East-Asian order: family name first. "李 明" -> last=李, first=明.
            toks_last = [toks[0]]
            toks_first = toks[1:]
        else:
            toks_last = [toks[-1]]
            toks_first = toks[:-1]
            while toks_first and toks_first[-1].lower().rstrip(".") in _PARTICLES:
                toks_last.insert(0, toks_first.pop())

    toks_last = [t for t in toks_last if t.rstrip(".").lower() not in _STRIP_PARTS]
    toks_first = [t for t in toks_first if t.rstrip(".").lower() not in _STRIP_PARTS]

    if not toks_last:
        return ""

    last = "".join(_alpha_lower(t) for t in toks_last) or toks_last[0].lower()

    first = ""
    for t in toks_first:
        cleaned = _alpha_lower(t).rstrip(".")
        if len(cleaned) >= 2:
            first = cleaned
            break
    if not first and toks_first:
        cleaned = _alpha_lower(toks_first[0])
        first = cleaned[:1] if cleaned else ""

    return f"{last}_{first}"


# ── Merge classifier (F2.2) ─────────────────────────────────────────────────


@dataclass(frozen=True)
class MergeDecision:
    tier: Literal["strong", "probable", "ambiguous", "distinct"]
    reason: str
    evidence: dict


def _last_initial_pair(a_key: str, b_key: str) -> bool:
    """True when keys share a last name and exactly one has only an initial
    that is a prefix of the other's first name (e.g. smith_j vs smith_john)."""
    if "_" not in a_key or "_" not in b_key:
        return False
    la, fa = a_key.split("_", 1)
    lb, fb = b_key.split("_", 1)
    if la != lb or not fa or not fb:
        return False
    one_initial = (len(fa) == 1) != (len(fb) == 1)
    return one_initial and (fa.startswith(fb[:1]) or fb.startswith(fa[:1]))


def _publication_entity_ids(db, author_id: int) -> set[int]:
    from backend import models
    rows = (
        db.query(models.AuthorPublication.entity_id)
        .filter(models.AuthorPublication.author_id == author_id)
        .all()
    )
    return {r[0] for r in rows}


def _shared_publication_ids(db, a_id: int, b_id: int) -> list[int]:
    return sorted(_publication_entity_ids(db, a_id) & _publication_entity_ids(db, b_id))


def _affiliations_for_entities(db, entity_ids: set[int]) -> set[str]:
    """Normalized (lower-cased, stripped) affiliation strings for the given
    entities, read from attributes_json.affiliation / enrichment_affiliation."""
    from backend import models
    if not entity_ids:
        return set()
    affs: set[str] = set()
    for ent in (
        db.query(models.RawEntity)
        .filter(models.RawEntity.id.in_(entity_ids))
        .all()
    ):
        try:
            attrs = json.loads(ent.attributes_json or "{}")
        except (ValueError, TypeError):
            continue
        aff = attrs.get("affiliation") or attrs.get("enrichment_affiliation")
        if isinstance(aff, str) and aff.strip():
            affs.add(aff.strip().lower())
    return affs


def _shared_affiliations(db, a_id: int, b_id: int) -> list[str]:
    """Affiliations common to A's publications and B's publications.

    Returns [] when no affiliation metadata exists, letting the classifier
    fall through to the ambiguous tier.
    """
    a_ents = _publication_entity_ids(db, a_id)
    b_ents = _publication_entity_ids(db, b_id)
    if not a_ents or not b_ents:
        return []
    affs_a = _affiliations_for_entities(db, a_ents)
    affs_b = _affiliations_for_entities(db, b_ents)
    return sorted(affs_a & affs_b)


def classify_merge(db, a, b) -> MergeDecision:
    """Classify whether two Author rows refer to the same person.

    Deterministic — no randomness, no global state. ORCID is authoritative:
    a match forces 'strong', a conflict forces 'distinct' even when name_keys
    are identical (different ORCIDs => different people).
    """
    if a.orcid and b.orcid and a.orcid == b.orcid:
        return MergeDecision("strong", "orcid match", {"orcid": a.orcid})
    if a.orcid and b.orcid and a.orcid != b.orcid:
        return MergeDecision("distinct", "orcid conflict", {"a": a.orcid, "b": b.orcid})

    # Identity model = "optimistic collapse + ORCID override": name_key is
    # UNIQUE, so two PERSISTED authors never share a key. This branch is
    # therefore reachable only with a transient candidate (e.g. dedup/migration
    # comparing a not-yet-inserted author against a stored one). Kept so the
    # logic is correct if Plan A (non-unique name_key) is ever adopted.
    if a.name_key == b.name_key:
        shared = _shared_publication_ids(db, a.id, b.id)
        if shared:
            return MergeDecision(
                "strong",
                "name_key + shared publications",
                {"shared_entity_ids": shared[:10]},
            )
        shared_aff = _shared_affiliations(db, a.id, b.id)
        if shared_aff:
            return MergeDecision(
                "probable",
                "name_key + shared affiliation",
                {"affiliations": shared_aff[:5]},
            )
        return MergeDecision("ambiguous", "name_key collision without disambiguator", {})

    if _last_initial_pair(a.name_key, b.name_key):
        return MergeDecision("ambiguous", "last+initial match across name forms", {})

    return MergeDecision("distinct", "no overlap", {})


# ── Author upsert + merge (F2.3) ────────────────────────────────────────────


def _aliases_list(a) -> list[str]:
    try:
        return json.loads(a.aliases or "[]")
    except (ValueError, TypeError):
        return []


def _set_aliases(a, items: list[str]) -> None:
    """Dedup preserving order, cap to _ALIAS_CAP."""
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    a.aliases = json.dumps(out[:_ALIAS_CAP], ensure_ascii=False)


def get_or_create_author(db, surface_form: str, *, orcid: str | None = None):
    """Return the Author for ``surface_form``'s canonical name_key, creating it
    if absent. Optimistic-collapse identity: same name_key => same author.

    New surface forms are appended to the alias list (capped). Adopts an ORCID
    onto an existing author that lacked one. Race-safe: a concurrent insert on
    the same name_key surfaces as IntegrityError, which we recover by re-fetch.
    """
    from backend import models

    key = name_key(surface_form)
    if not key:
        raise ValueError("empty name_key from surface form")

    existing = db.query(models.Author).filter_by(name_key=key).first()
    if existing:
        aliases = _aliases_list(existing)
        if surface_form not in aliases:
            aliases.insert(0, surface_form)
            _set_aliases(existing, aliases)
        existing.last_seen_at = datetime.now(timezone.utc)
        if orcid and not existing.orcid:
            existing.orcid = orcid
        db.commit()
        return existing

    a = models.Author(name_key=key, display_name=surface_form, orcid=orcid)
    _set_aliases(a, [surface_form])
    db.add(a)
    try:
        db.commit()
    except IntegrityError:
        # Race lost — another writer inserted the same name_key. Re-fetch.
        db.rollback()
        return db.query(models.Author).filter_by(name_key=key).one()
    try:
        db.refresh(a)
        return a
    except Exception:
        # The row committed, but the instance can't be refreshed (e.g. its
        # state was expired by a concurrent writer on a shared connection).
        # The unique name_key guarantees a single canonical row — refetch it.
        return db.query(models.Author).filter_by(name_key=key).one()


def merge_authors(
    db,
    winner,
    loser,
    *,
    tier: str,
    reason: str,
    performed_by: int | None = None,
    evidence: dict | None = None,
) -> None:
    """Repoint all of ``loser``'s rows onto ``winner``, append aliases, write an
    audit row, and delete ``loser``.

    Must be called inside a transaction; the caller owns the commit. Edges and
    contribution-log rows for the loser are deleted (not repointed) — the next
    recompute regenerates edges from the surviving contributions, which keeps
    the idempotent weight accounting correct.
    """
    from backend import models

    if winner.id == loser.id:
        return

    db.add(models.AuthorMergeAudit(
        winner_author_id=winner.id,
        loser_author_id=loser.id,
        tier=tier,
        reason=reason,
        evidence=json.dumps(evidence or {}, ensure_ascii=False),
        performed_by=performed_by,
    ))

    winner_entity_ids = {
        row[0]
        for row in db.query(models.AuthorPublication.entity_id)
        .filter_by(author_id=winner.id)
        .all()
    }
    if winner_entity_ids:
        db.query(models.AuthorPublication).filter(
            models.AuthorPublication.author_id == loser.id,
            models.AuthorPublication.entity_id.in_(winner_entity_ids),
        ).delete(synchronize_session=False)
    db.query(models.AuthorPublication).filter_by(author_id=loser.id).update(
        {"author_id": winner.id}, synchronize_session=False
    )
    db.query(models.AuthorStats).filter_by(author_id=loser.id).delete(
        synchronize_session=False
    )
    db.query(models.AuthorMergeSuggestion).filter_by(author_a_id=loser.id).update(
        {"author_a_id": winner.id}, synchronize_session=False
    )
    db.query(models.AuthorMergeSuggestion).filter_by(author_b_id=loser.id).update(
        {"author_b_id": winner.id}, synchronize_session=False
    )
    db.query(models.CoauthorContribution).filter(
        (models.CoauthorContribution.author_a_id == loser.id)
        | (models.CoauthorContribution.author_b_id == loser.id)
    ).delete(synchronize_session=False)
    db.query(models.CoauthorEdge).filter(
        (models.CoauthorEdge.author_a_id == loser.id)
        | (models.CoauthorEdge.author_b_id == loser.id)
    ).delete(synchronize_session=False)

    winner_aliases = _aliases_list(winner) + _aliases_list(loser) + [loser.display_name]
    _set_aliases(winner, winner_aliases)
    if loser.orcid and not winner.orcid:
        winner.orcid = loser.orcid

    db.delete(loser)
    db.flush()
