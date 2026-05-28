# Coauthorship Module Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the parasitic `entity_relationships(relation_type='CO_AUTHOR', notes='A||B')` storage with a first-class authors/publications/edges/stats data model, materialized by a worker, served behind feature flags, with GraphDB-style frontend.

**Architecture:** Seven mergeable phases (F1 schema → F2 identity → F3 worker shadow → F4a migration+diagnostics → F4b reads → F4c frontend → F5 cleanup). Each phase is one or more PRs gated by feature flags (`COAUTHOR_V2_WRITE`, `COAUTHOR_V2_SHADOW`, `COAUTHOR_V2_READ`). TDD throughout: failing test → implementation → green → commit. Pure-Python identity engine (deterministic `name_key`), `python-louvain` for community detection, durable `coauthor_dirty_scopes` table for recompute queue.

**Tech Stack:** FastAPI + SQLAlchemy + SQLite (Postgres-compat target), pytest, `python-louvain` (new dep), Next.js 16 / React 19 / d3-force / d3-selection, Playwright e2e.

**Spec:** `docs/superpowers/specs/2026-05-28-coauthorship-refactor-design.md` (rev 2, architect-approved).

---

## File Structure

### New backend files

```
backend/coauthorship/
  __init__.py
  identity.py         # name_key, get_or_create_author, merge classifier, merge_authors
  recompute.py        # recompute_coauthor_stats + Louvain wiring
  migration.py        # one-shot legacy → V2 conversion library used by script and tests
  diagnostics.py      # storage/scope counters used by /diagnostics endpoint

backend/scripts/
  migrate_coauthor_graph.py   # CLI + run() invoked from admin endpoint

backend/routers/
  coauthorship.py     # all V2 endpoints (GET network, GET author, GET diagnostics,
                      # POST recompute, GET/POST merge-suggestions)

backend/tests/
  test_coauthor_schema.py
  test_identity_engine.py
  test_merge_classifier.py
  test_get_or_create_author_race.py
  test_worker_coauthor_hook.py
  test_recompute_stats.py
  test_migration_script.py
  test_diagnostics_endpoint.py
  test_analyzer_v2.py
  test_merge_suggestions_api.py
  test_legacy_cleanup.py
```

### Modified backend files

```
backend/models.py              # +7 model classes
backend/main.py                # router include + lifespan DDL for the 7 new tables
backend/enrichment_worker.py   # write hook + dirty_scopes enqueue + tenancy reassignment
backend/analyzers/coauthorship.py  # V1 readers eventually retired; library code kept for migration
backend/routers/analytics.py   # remove coauthorship route after F4b
backend/config.py              # feature flags (WRITE, SHADOW, READ)
requirements.txt               # +python-louvain
```

### New frontend files

```
frontend/app/components/graph/MergeSuggestionsPanel.tsx
frontend/app/components/graph/NodePropertiesPanel.tsx
frontend/app/components/graph/GraphControls.tsx
frontend/e2e/coauthorship.spec.ts
frontend/e2e/network_graph_visual.spec.ts
```

### Modified frontend files

```
frontend/app/analytics/coauthorship/page.tsx
frontend/app/components/graph/NetworkGraph.tsx
frontend/app/components/graph/useForceLayout.ts
```

### Removed in F5

```
backend/scripts/backfill_coauthor_edges.py
backend/routers/admin_data_fixes.py    # coauthor-edges route + request models only
backend/tests/test_admin_data_fixes.py # coauthor-edges tests only
```

---

## Phase F1 — Schema (low risk, ~280 LOC)

Tables exist, nothing reads or writes them yet. Three tasks.

### Task F1.1 · SQLAlchemy model classes

**Files:**
- Modify: `backend/models.py` (append 7 model classes)
- Test: `backend/tests/test_coauthor_schema.py` (new)

- [ ] **Step 1: Write failing tests** in `backend/tests/test_coauthor_schema.py`:

```python
"""Schema-level tests for the V2 coauthorship tables. These exercise DDL,
compound primary keys, the org_id=0 sentinel invariant, and FK cascades.
Pure schema — no business logic."""
import pytest
from sqlalchemy.exc import IntegrityError
from backend import models
from backend.database import SessionLocal


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def test_author_unique_name_key(db):
    a = models.Author(name_key="smith_john", display_name="John Smith")
    b = models.Author(name_key="smith_john", display_name="John SMITH")
    db.add(a); db.commit()
    db.add(b)
    with pytest.raises(IntegrityError):
        db.commit()


def test_author_unique_orcid_nullable(db):
    db.add(models.Author(name_key="a_a", display_name="A A", orcid=None))
    db.add(models.Author(name_key="b_b", display_name="B B", orcid=None))
    db.commit()  # two NULLs allowed
    db.add(models.Author(name_key="c_c", display_name="C C", orcid="0000-1"))
    db.add(models.Author(name_key="d_d", display_name="D D", orcid="0000-1"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_coauthor_edges_pk_uniqueness_legacy_scope(db):
    """Two edges with the same author pair and org_id=0 (legacy) MUST collide.
    This is the architect-review C2 regression — nullable org_id used to
    silently allow duplicates."""
    a1 = models.Author(name_key="x_x", display_name="X X"); db.add(a1)
    a2 = models.Author(name_key="y_y", display_name="Y Y"); db.add(a2)
    db.commit()
    lo, hi = sorted([a1.id, a2.id])
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=0, domain_id="default", weight=1))
    db.commit()
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=0, domain_id="default", weight=1))
    with pytest.raises(IntegrityError):
        db.commit()


def test_coauthor_edges_pk_allows_different_scopes(db):
    a1 = models.Author(name_key="p_p", display_name="P P"); db.add(a1)
    a2 = models.Author(name_key="q_q", display_name="Q Q"); db.add(a2)
    db.commit()
    lo, hi = sorted([a1.id, a2.id])
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=0, domain_id="default", weight=1))
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=1, domain_id="default", weight=1))
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=0, domain_id="science", weight=1))
    db.commit()  # all three distinct rows


def test_author_publication_cascade_on_entity_delete(db):
    """Deleting a raw_entity must cascade to author_publications."""
    a = models.Author(name_key="z_z", display_name="Z Z"); db.add(a)
    e = models.RawEntity(name="paper", domain="default", attributes_json="{}")
    db.add(e); db.commit()
    db.add(models.AuthorPublication(author_id=a.id, entity_id=e.id, org_id=0,
                                     domain_id="default", position=1))
    db.commit()
    db.delete(e); db.commit()
    assert db.query(models.AuthorPublication).count() == 0


def test_dirty_scopes_pk(db):
    db.add(models.CoauthorDirtyScope(org_id=0, domain_id="default", reason="enrichment"))
    db.commit()
    db.add(models.CoauthorDirtyScope(org_id=0, domain_id="default", reason="migration"))
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] **Step 2: Run tests, expect ImportError** (`Author`, `CoauthorEdge`, etc. don't exist).

```bash
.venv/Scripts/python -m pytest backend/tests/test_coauthor_schema.py -v
```
Expected: collection error / ImportError.

- [ ] **Step 3: Add models** to `backend/models.py` (append at end):

```python
# ── V2 Coauthorship tables (Sprint 2026-05-28 refactor) ────────────────────

class Author(Base):
    __tablename__ = "authors"
    id = Column(Integer, primary_key=True, index=True)
    name_key = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    aliases = Column(Text, default="[]")  # JSON list, capped 50 entries in worker
    orcid = Column(String, unique=True, nullable=True, index=True)
    authority_record_id = Column(Integer, ForeignKey("authority_records.id"), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuthorPublication(Base):
    __tablename__ = "author_publications"
    author_id = Column(Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    entity_id = Column(Integer, ForeignKey("raw_entities.id", ondelete="CASCADE"), primary_key=True)
    org_id = Column(Integer, nullable=False, default=0, index=True)
    domain_id = Column(String, nullable=False, index=True)
    position = Column(Integer, nullable=True)
    __table_args__ = (
        Index("ix_author_pub_scope", "author_id", "org_id", "domain_id"),
        Index("ix_author_pub_entity", "entity_id"),
    )


class CoauthorEdge(Base):
    __tablename__ = "coauthor_edges"
    author_a_id = Column(Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    author_b_id = Column(Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    org_id = Column(Integer, primary_key=True, nullable=False, default=0)
    domain_id = Column(String, primary_key=True, nullable=False)
    weight = Column(Integer, nullable=False, default=1)
    last_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        Index("ix_coauthor_edge_scope_weight", "org_id", "domain_id", "weight"),
    )


class AuthorStats(Base):
    __tablename__ = "author_stats"
    author_id = Column(Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    org_id = Column(Integer, primary_key=True, nullable=False, default=0)
    domain_id = Column(String, primary_key=True, nullable=False)
    degree = Column(Integer, default=0)
    centrality = Column(Float, default=0.0)
    community_id = Column(Integer, default=0)
    publication_count = Column(Integer, default=0)
    computed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        Index("ix_author_stats_centrality", "org_id", "domain_id", "centrality"),
        Index("ix_author_stats_community", "org_id", "domain_id", "community_id"),
    )


class AuthorMergeSuggestion(Base):
    __tablename__ = "author_merge_suggestions"
    id = Column(Integer, primary_key=True, index=True)
    author_a_id = Column(Integer, ForeignKey("authors.id", ondelete="CASCADE"), nullable=False)
    author_b_id = Column(Integer, ForeignKey("authors.id", ondelete="CASCADE"), nullable=False)
    reason = Column(String)
    evidence = Column(Text)  # JSON
    status = Column(String, default="pending", index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class AuthorMergeAudit(Base):
    __tablename__ = "author_merge_audit"
    id = Column(Integer, primary_key=True, index=True)
    winner_author_id = Column(Integer, nullable=False)
    loser_author_id = Column(Integer, nullable=False)
    tier = Column(String, nullable=False)  # strong | probable | manual
    reason = Column(String)
    evidence = Column(Text)  # JSON
    performed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    performed_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class CoauthorDirtyScope(Base):
    __tablename__ = "coauthor_dirty_scopes"
    org_id = Column(Integer, primary_key=True, nullable=False)
    domain_id = Column(String, primary_key=True, nullable=False)
    enqueued_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reason = Column(String, nullable=False)


class CoauthorContribution(Base):
    """Idempotency log: ensures one (entity, author_a, author_b) triple
    contributes exactly +1 to a coauthor_edges.weight, regardless of how
    many times the worker or migration script processes that entity."""
    __tablename__ = "coauthor_contributions"
    entity_id = Column(Integer, ForeignKey("raw_entities.id", ondelete="CASCADE"), primary_key=True)
    author_a_id = Column(Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    author_b_id = Column(Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    org_id = Column(Integer, nullable=False, default=0)
    domain_id = Column(String, nullable=False)
```

Verify the existing `Base`, `Column`, `Integer`, `String`, `Float`, `DateTime`, `Text`, `ForeignKey`, `Index`, `datetime`, `timezone` imports are present at top of `models.py`. Add `Index` to imports if missing.

- [ ] **Step 4: Run tests** — expect passes for unique constraints; cascade test will fail because lifespan DDL doesn't create the tables yet. That's OK, we wire it in F1.2.

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/tests/test_coauthor_schema.py
git commit -m "feat(coauthor): add V2 schema models (F1.1)"
```

### Task F1.2 · Lifespan DDL migration

**Files:**
- Modify: `backend/main.py` (lifespan function)

- [ ] **Step 1: Find the lifespan block** in `backend/main.py`. After existing `Base.metadata.create_all(bind=engine)`, no extra DDL needed — SQLAlchemy emits the new tables automatically. The only manual statement needed: backfill `org_id IS NULL` legacy rows on tables that newly require `NOT NULL DEFAULT 0`. The 7 new tables are empty, so nothing to backfill. Add a one-liner comment:

```python
# V2 coauthorship tables (authors, author_publications, coauthor_edges,
# author_stats, author_merge_suggestions, author_merge_audit,
# coauthor_dirty_scopes, coauthor_contributions) are created by the
# Base.metadata.create_all above. No backfill needed — empty on first boot.
```

- [ ] **Step 2: Run schema tests** — all should pass now.

```bash
.venv/Scripts/python -m pytest backend/tests/test_coauthor_schema.py -v
```
Expected: 6 passing.

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat(coauthor): wire V2 tables into lifespan DDL (F1.2)"
```

### Task F1.3 · Feature flags

**Files:**
- Modify: `backend/config.py` (or create if absent)

- [ ] **Step 1: Add flags**:

```python
import os

def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"

COAUTHOR_V2_WRITE  = _flag("COAUTHOR_V2_WRITE",  "false")
COAUTHOR_V2_SHADOW = _flag("COAUTHOR_V2_SHADOW", "true")   # default ON during F3
COAUTHOR_V2_READ   = _flag("COAUTHOR_V2_READ",   "false")
```

- [ ] **Step 2: Commit**

```bash
git add backend/config.py
git commit -m "feat(coauthor): add feature flags COAUTHOR_V2_{WRITE,SHADOW,READ} (F1.3)"
```

---

## Phase F2 — Identity engine (low risk, ~450 LOC)

Pure-Python logic. No side effects in core functions.

### Task F2.1 · `name_key` algorithm

**Files:**
- Create: `backend/coauthorship/__init__.py` (empty)
- Create: `backend/coauthorship/identity.py`
- Create: `backend/tests/test_identity_engine.py`
- Create: `backend/tests/fixtures/name_key_golden.json` (golden file)

- [ ] **Step 1: Write the golden file** — ≥150 cases covering Latin, CJK, mononyms, particles, initials. Example shape:

```json
[
  {"input": "Dr. John A. Smith Jr.",        "name_key": "smith_john"},
  {"input": "Smith, John A.",               "name_key": "smith_john"},
  {"input": "J. A. Smith",                  "name_key": "smith_j"},
  {"input": "J. Smith",                     "name_key": "smith_j"},
  {"input": "John Smith",                   "name_key": "smith_john"},
  {"input": "José García",                  "name_key": "garcia_jose"},
  {"input": "Vincent van der Berg",         "name_key": "vanderberg_vincent"},
  {"input": "Marie-Claire Lefebvre",        "name_key": "lefebvre_marie-claire"},
  {"input": "Madonna",                      "name_key": "madonna_"},
  {"input": "李 明",                         "name_key": "李_明"},
  {"input": "Wang, Wei",                    "name_key": "wang_wei"},
  {"input": "  J Smith  ",                  "name_key": "smith_j"},
  {"input": "John Smith PhD",               "name_key": "smith_john"},
  {"input": "Smith III, John",              "name_key": "smith_john"}
]
```

Build the full ≥150-case set with help from the spec §4 policy.

- [ ] **Step 2: Write failing tests** in `test_identity_engine.py`:

```python
import json
from pathlib import Path
import pytest
from backend.coauthorship.identity import name_key

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "name_key_golden.json").read_text())


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: c["input"])
def test_name_key_golden(case):
    assert name_key(case["input"]) == case["name_key"]


def test_name_key_empty():
    assert name_key("") == ""
    assert name_key("   ") == ""


def test_name_key_idempotent():
    # Running name_key on the surface form derived from a key should still produce that key
    for case in GOLDEN[:10]:
        k = case["name_key"]
        # Reconstruct a "Last First" surface form from a key:
        if "_" in k:
            last, first = k.split("_", 1)
            surface = f"{first.title()} {last.title()}" if first else last.title()
            assert name_key(surface) == k


def test_name_key_pure():
    # Same input → same output, no global state
    for _ in range(3):
        assert name_key("Dr. John A. Smith Jr.") == "smith_john"
```

- [ ] **Step 3: Run tests, expect ImportError**.

- [ ] **Step 4: Implement `name_key`** in `backend/coauthorship/identity.py`:

```python
"""Author identity engine — deterministic, pure-Python.

Public API:
- name_key(surface_form: str) -> str
- classify_merge(a: Author, b: Author, db) -> MergeDecision
- get_or_create_author(db, surface_form: str, *, orcid: str | None = None) -> Author
- merge_authors(db, winner: Author, loser: Author, *, tier, reason, performed_by=None) -> None
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

# Titles/suffixes stripped before parsing. Lowercase compared after NFD.
_STRIP_PARTS = {
    "dr", "dr.", "prof", "prof.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.",
    "phd", "ph.d", "md", "m.d", "jr", "jr.", "sr", "sr.", "iii", "iv", "ii",
}
_PARTICLES = {"van", "der", "de", "la", "del", "da", "dos", "el", "al", "von", "di"}


def _strip_diacritics(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def _tokenize(surface: str) -> list[str]:
    return [t for t in re.split(r"\s+", surface.strip()) if t]


def _alpha_lower(tok: str) -> str:
    # Keep Unicode letter-likes (CJK, Cyrillic) — only drop punctuation
    return "".join(ch for ch in tok if ch.isalpha() or ch == "-").lower()


def name_key(surface_form: str) -> str:
    """Canonical fingerprint. Deterministic. Empty input → empty string."""
    if not surface_form or not surface_form.strip():
        return ""

    s = _strip_diacritics(surface_form)
    # "Last, First" detection
    inverted = "," in s
    if inverted:
        left, right = s.split(",", 1)
        toks_last = _tokenize(left)
        toks_first = _tokenize(right)
    else:
        toks = _tokenize(s)
        # Filter out titles/suffixes from anywhere
        toks = [t for t in toks if t.rstrip(".").lower() not in _STRIP_PARTS]
        if not toks:
            return ""
        toks_last = [toks[-1]]
        toks_first = toks[:-1]
        # Pull leading particles ("van der") onto the last-name side
        while toks_first and toks_first[-1].lower().rstrip(".") in _PARTICLES:
            toks_last.insert(0, toks_first.pop())

    # Drop titles/suffixes from inverted form too
    toks_last = [t for t in toks_last if t.rstrip(".").lower() not in _STRIP_PARTS]
    toks_first = [t for t in toks_first if t.rstrip(".").lower() not in _STRIP_PARTS]

    if not toks_last:
        return ""

    last = "".join(_alpha_lower(t) for t in toks_last) or toks_last[0].lower()

    # Pick first: prefer first non-initial token of length ≥ 2; else first initial letter
    first = ""
    for t in toks_first:
        cleaned = _alpha_lower(t).rstrip(".")
        if len(cleaned) >= 2:
            first = cleaned
            break
    if not first and toks_first:
        # Use leading letter of first token
        cleaned = _alpha_lower(toks_first[0])
        first = cleaned[:1] if cleaned else ""

    return f"{last}_{first}"
```

- [ ] **Step 5: Run tests** — iterate until all golden cases pass. Failures here mean either the algorithm needs tightening or the golden case is wrong (revisit spec §4).

- [ ] **Step 6: Commit**

```bash
git add backend/coauthorship/__init__.py backend/coauthorship/identity.py \
        backend/tests/test_identity_engine.py backend/tests/fixtures/name_key_golden.json
git commit -m "feat(coauthor): name_key canonicalization engine (F2.1)"
```

### Task F2.2 · Merge classifier (3 tiers)

**Files:**
- Modify: `backend/coauthorship/identity.py` (append)
- Create: `backend/tests/test_merge_classifier.py`

- [ ] **Step 1: Failing tests**:

```python
"""Classifier maps (Author A, Author B) → 'strong' | 'probable' | 'ambiguous' | 'distinct'.

Per spec §4:
  strong   = identical ORCID, OR identical name_key + ≥1 shared publication
  probable = identical name_key + ≥1 shared affiliation OR ≥1 shared concept,
             AND no ORCID conflict
  ambiguous = last+initial match across different first-name forms,
              OR name_key collision without disambiguator
  distinct = none of the above
"""
import pytest
from backend.coauthorship.identity import classify_merge, MergeDecision
from backend import models

# fixture `db` is the standard project conftest one (in-memory SQLite, StaticPool)


def _author(db, name_key, **kw):
    a = models.Author(name_key=name_key, display_name=kw.get("display_name", name_key),
                       orcid=kw.get("orcid"))
    db.add(a); db.commit(); db.refresh(a)
    return a


def test_strong_orcid_match(db):
    a = _author(db, "smith_john", orcid="0000-0000-0000-0001")
    b = _author(db, "smith_jonathan", orcid="0000-0000-0000-0001")
    d = classify_merge(db, a, b)
    assert d.tier == "strong"
    assert "orcid" in d.reason


def test_strong_orcid_conflict_blocks_probable(db):
    a = _author(db, "smith_john", orcid="0000-0000-0000-0001")
    b = _author(db, "smith_john", orcid="0000-0000-0000-0002")
    # Same name_key but DIFFERENT ORCIDs → these are NOT the same person.
    d = classify_merge(db, a, b)
    assert d.tier == "distinct"
    assert "orcid conflict" in d.reason


def test_strong_namekey_plus_shared_publication(db):
    a = _author(db, "smith_john")
    b = _author(db, "smith_john")
    # Seed a shared publication
    e = models.RawEntity(name="paper", domain="default", attributes_json="{}"); db.add(e); db.commit()
    db.add(models.AuthorPublication(author_id=a.id, entity_id=e.id, org_id=0, domain_id="default", position=1))
    db.add(models.AuthorPublication(author_id=b.id, entity_id=e.id, org_id=0, domain_id="default", position=2))
    db.commit()
    d = classify_merge(db, a, b)
    assert d.tier == "strong"


def test_namekey_match_without_disambiguator_is_ambiguous(db):
    """Critical case from architect review C3 — bare 'John Smith' collision must NOT auto-merge."""
    a = _author(db, "smith_john")
    b = _author(db, "smith_john")
    d = classify_merge(db, a, b)
    assert d.tier == "ambiguous"


def test_last_plus_initial_is_ambiguous(db):
    """'J. Smith' vs 'John Smith' → ambiguous queue, never auto-merge."""
    a = _author(db, "smith_j")
    b = _author(db, "smith_john")
    d = classify_merge(db, a, b)
    assert d.tier == "ambiguous"


def test_distinct_when_unrelated(db):
    a = _author(db, "smith_john")
    b = _author(db, "lee_amy")
    d = classify_merge(db, a, b)
    assert d.tier == "distinct"
```

- [ ] **Step 2: Implement** by appending to `identity.py`:

```python
@dataclass(frozen=True)
class MergeDecision:
    tier: Literal["strong", "probable", "ambiguous", "distinct"]
    reason: str
    evidence: dict


def _last_initial_pair(a_key: str, b_key: str) -> bool:
    """True when keys share last name and one has only an initial."""
    if "_" not in a_key or "_" not in b_key:
        return False
    la, fa = a_key.split("_", 1)
    lb, fb = b_key.split("_", 1)
    if la != lb:
        return False
    one_initial = (len(fa) == 1) != (len(fb) == 1)
    return one_initial and (fa.startswith(fb[:1]) or fb.startswith(fa[:1]))


def _shared_publication_ids(db, a_id: int, b_id: int) -> list[int]:
    from backend import models
    rows = (
        db.query(models.AuthorPublication.entity_id)
        .filter(models.AuthorPublication.author_id == a_id)
        .filter(models.AuthorPublication.entity_id.in_(
            db.query(models.AuthorPublication.entity_id)
              .filter(models.AuthorPublication.author_id == b_id)
        ))
        .all()
    )
    return [r[0] for r in rows]


def classify_merge(db, a, b) -> MergeDecision:
    from backend import models  # local import to avoid cycle
    if a.orcid and b.orcid and a.orcid == b.orcid:
        return MergeDecision("strong", "orcid match", {"orcid": a.orcid})
    if a.orcid and b.orcid and a.orcid != b.orcid:
        return MergeDecision("distinct", "orcid conflict", {"a": a.orcid, "b": b.orcid})

    if a.name_key == b.name_key:
        shared = _shared_publication_ids(db, a.id, b.id)
        if shared:
            return MergeDecision("strong", "name_key + shared publications",
                                 {"shared_entity_ids": shared[:10]})
        # TODO probable tier: shared affiliation / concept (deferred to F2.3 if needed
        #   — current corpus has no affiliation metadata indexed yet)
        return MergeDecision("ambiguous", "name_key collision without disambiguator", {})

    if _last_initial_pair(a.name_key, b.name_key):
        return MergeDecision("ambiguous", "last+initial match across name forms", {})

    return MergeDecision("distinct", "no overlap", {})
```

- [ ] **Step 3: Run tests, iterate to green, commit**:

```bash
git add backend/coauthorship/identity.py backend/tests/test_merge_classifier.py
git commit -m "feat(coauthor): 3-tier merge classifier (F2.2)"
```

### Task F2.3 · `get_or_create_author` + race test + `merge_authors`

**Files:**
- Modify: `backend/coauthorship/identity.py`
- Create: `backend/tests/test_get_or_create_author_race.py`

- [ ] **Step 1: Failing tests**:

```python
"""Concurrent inserts on the same name_key must converge to a single row.

Reproduces the Sprint 2 atomic-claim pattern adapted for upsert-on-unique."""
import threading
from backend.coauthorship.identity import get_or_create_author, merge_authors
from backend import models


def test_get_or_create_returns_existing(db):
    a1 = get_or_create_author(db, "John Smith")
    a2 = get_or_create_author(db, "John Smith")
    assert a1.id == a2.id


def test_get_or_create_appends_alias(db):
    a = get_or_create_author(db, "John Smith")
    a2 = get_or_create_author(db, "J. SMITH")  # different surface, COLLIDES — see F2.1 golden
    # Wait — "J. SMITH" → smith_j, "John Smith" → smith_john. Different rows.
    assert a.id != a2.id


def test_get_or_create_collapses_same_namekey(db):
    a = get_or_create_author(db, "Smith, John")
    b = get_or_create_author(db, "John Smith")
    assert a.id == b.id
    aliases = a.aliases_list
    assert "Smith, John" in aliases
    assert "John Smith" in aliases


def test_merge_authors_moves_publications_and_edges(db):
    winner = get_or_create_author(db, "Smith, John")
    loser = get_or_create_author(db, "John A. Smith")  # different name_key
    e = models.RawEntity(name="p", domain="default", attributes_json="{}")
    db.add(e); db.commit()
    db.add(models.AuthorPublication(author_id=loser.id, entity_id=e.id, org_id=0,
                                     domain_id="default", position=1))
    db.commit()
    merge_authors(db, winner, loser, tier="manual", reason="test")
    assert db.query(models.Author).filter_by(id=loser.id).first() is None
    pub = db.query(models.AuthorPublication).filter_by(entity_id=e.id).one()
    assert pub.author_id == winner.id
    audit = db.query(models.AuthorMergeAudit).filter_by(loser_author_id=loser.id).one()
    assert audit.tier == "manual"


def test_concurrent_get_or_create_one_row(db_factory):
    """Race: 5 threads insert 'New Author' simultaneously → exactly one row exists."""
    results = []
    barrier = threading.Barrier(5)
    def worker():
        s = db_factory()
        try:
            barrier.wait()
            a = get_or_create_author(s, "New Author")
            results.append(a.id)
        finally:
            s.close()
    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(set(results)) == 1
    # Note: `db_factory` is a new conftest fixture that returns a fresh Session each call,
    # backed by the same StaticPool engine. Add it to backend/tests/conftest.py.
```

- [ ] **Step 2: Implement** in `identity.py`:

```python
import json
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError

_ALIAS_CAP = 50


def _aliases_list(a) -> list[str]:
    try:
        return json.loads(a.aliases or "[]")
    except (ValueError, TypeError):
        return []


def _set_aliases(a, items: list[str]) -> None:
    # Dedup preserving order, cap to _ALIAS_CAP
    seen, out = set(), []
    for x in items:
        if x and x not in seen:
            seen.add(x); out.append(x)
    a.aliases = json.dumps(out[:_ALIAS_CAP])


# Monkey-patch convenience accessor for tests
def _aliases_property(self):
    return _aliases_list(self)


def get_or_create_author(db, surface_form: str, *, orcid: str | None = None):
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
        db.refresh(a)
        return a
    except IntegrityError:
        # Race lost — another thread inserted the same name_key. Re-fetch.
        db.rollback()
        return db.query(models.Author).filter_by(name_key=key).one()


def merge_authors(db, winner, loser, *, tier: str, reason: str, performed_by: int | None = None,
                  evidence: dict | None = None) -> None:
    """Repoint all `loser`'s rows to `winner`, append aliases, write audit, delete loser.

    Must be called inside a transaction. Caller handles commit on the surrounding scope."""
    from backend import models
    if winner.id == loser.id:
        return

    # Audit first (loser id still resolvable)
    db.add(models.AuthorMergeAudit(
        winner_author_id=winner.id,
        loser_author_id=loser.id,
        tier=tier,
        reason=reason,
        evidence=json.dumps(evidence or {}),
        performed_by=performed_by,
    ))

    # Move publications
    db.query(models.AuthorPublication).filter_by(author_id=loser.id) \
      .update({"author_id": winner.id}, synchronize_session=False)
    # Move contributions (idempotency log)
    db.query(models.CoauthorContribution) \
      .filter((models.CoauthorContribution.author_a_id == loser.id) |
              (models.CoauthorContribution.author_b_id == loser.id)) \
      .delete(synchronize_session=False)
    # Move edges — easier to delete and let next recompute regenerate from contributions
    db.query(models.CoauthorEdge) \
      .filter((models.CoauthorEdge.author_a_id == loser.id) |
              (models.CoauthorEdge.author_b_id == loser.id)) \
      .delete(synchronize_session=False)
    # Append aliases
    winner_aliases = _aliases_list(winner) + _aliases_list(loser) + [loser.display_name]
    _set_aliases(winner, winner_aliases)
    # Adopt loser's ORCID if winner lacked one
    if loser.orcid and not winner.orcid:
        winner.orcid = loser.orcid
    db.delete(loser)
    db.flush()  # Author rows gone; next recompute will rebuild edges for affected scopes
```

Add a convenience SQLAlchemy hybrid property `aliases_list` to `models.Author`:

```python
# In models.py inside class Author:
@property
def aliases_list(self) -> list[str]:
    import json
    try:
        return json.loads(self.aliases or "[]")
    except (ValueError, TypeError):
        return []
```

- [ ] **Step 3: Add `db_factory` fixture** to `backend/tests/conftest.py`:

```python
@pytest.fixture
def db_factory():
    """Returns a function that produces fresh Sessions sharing the same engine.
    Used for race-condition tests requiring real cross-session contention."""
    from backend.database import SessionLocal
    sessions = []
    def factory():
        s = SessionLocal()
        sessions.append(s)
        return s
    yield factory
    for s in sessions:
        s.close()
```

- [ ] **Step 4: Run all F2 tests, commit**:

```bash
git add backend/coauthorship/identity.py backend/models.py \
        backend/tests/test_get_or_create_author_race.py backend/tests/conftest.py
git commit -m "feat(coauthor): get_or_create_author + merge_authors + race test (F2.3)"
```

---

## Phase F3 — Worker integration (medium risk, ~400 LOC)

### Task F3.1 · Add `python-louvain` dep

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Append** `python-louvain==0.16` (latest at plan time; verify on PyPI). Also `networkx>=3.0` if not present (transitive but pin explicitly for clarity).

- [ ] **Step 2: Install + smoke test**:

```bash
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -c "import community.community_louvain as cl; import networkx; print(cl.best_partition)"
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: add python-louvain for community detection (F3.1)"
```

### Task F3.2 · `recompute_coauthor_stats` (with perf gate)

**Files:**
- Create: `backend/coauthorship/recompute.py`
- Create: `backend/tests/test_recompute_stats.py`

- [ ] **Step 1: Failing tests** — include the 100k-edge perf gate that blocks F3 merge:

```python
"""Tests for the Louvain-backed recompute job.

Performance: at 100k edges the recompute must complete < 5s, OR < 10s with a
documented gate failure recorded in success criteria (spec §12.3)."""
import time
import random
import pytest
from backend.coauthorship.recompute import recompute_coauthor_stats
from backend.coauthorship.identity import get_or_create_author
from backend import models


def _seed_pair(db, a_name, b_name, *, weight=1, org_id=0, domain="default"):
    a = get_or_create_author(db, a_name)
    b = get_or_create_author(db, b_name)
    lo, hi = sorted([a.id, b.id])
    db.add(models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=org_id,
                                domain_id=domain, weight=weight))
    db.commit()
    return a, b


def test_recompute_empty_scope_is_noop(db):
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    assert db.query(models.AuthorStats).count() == 0


def test_recompute_small_graph_uses_connected_components(db):
    _seed_pair(db, "A A", "B B")
    _seed_pair(db, "B B", "C C")
    _seed_pair(db, "X X", "Y Y")
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    rows = db.query(models.AuthorStats).all()
    assert len(rows) == 5
    by_name = {r.author_id: r for r in rows}
    # A, B, C share one community; X, Y another
    communities = {r.community_id for r in rows}
    assert len(communities) == 2


def test_recompute_uses_louvain_above_threshold(db, monkeypatch):
    # Seed >50 nodes
    for i in range(60):
        _seed_pair(db, f"P{i:02d} X", f"Q{i:02d} Y")
    called = {"louvain": False}
    import community.community_louvain as cl
    orig = cl.best_partition
    def spy(G, *a, **kw):
        called["louvain"] = True
        return orig(G, *a, **kw)
    monkeypatch.setattr(cl, "best_partition", spy)
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    assert called["louvain"] is True


def test_recompute_clears_dirty_scope(db):
    db.add(models.CoauthorDirtyScope(org_id=0, domain_id="default", reason="test"))
    db.commit()
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    assert db.query(models.CoauthorDirtyScope).filter_by(org_id=0, domain_id="default").count() == 0


@pytest.mark.slow
def test_louvain_100k_edges_under_5s(db):
    """Performance gate — blocks F3 merge if regressed.

    Acceptance: completes in < 5s. Soft gate: < 10s passes with warning."""
    random.seed(42)
    N = 1000  # 1k authors, ~100k random edges
    authors = [get_or_create_author(db, f"Auth{i:05d} X") for i in range(N)]
    edges = set()
    while len(edges) < 100_000:
        i, j = random.sample(range(N), 2)
        lo, hi = sorted([authors[i].id, authors[j].id])
        edges.add((lo, hi))
    db.bulk_save_objects([
        models.CoauthorEdge(author_a_id=lo, author_b_id=hi, org_id=0, domain_id="default", weight=1)
        for lo, hi in edges
    ])
    db.commit()
    t0 = time.perf_counter()
    recompute_coauthor_stats(db, org_id=0, domain_id="default")
    elapsed = time.perf_counter() - t0
    print(f"100k-edge recompute: {elapsed*1000:.0f}ms")
    assert elapsed < 10.0, f"Recompute too slow: {elapsed:.2f}s"
    if elapsed > 5.0:
        pytest.skip(f"Soft gate: 5s target missed but <10s OK ({elapsed:.2f}s)")
```

- [ ] **Step 2: Implement** `recompute.py`:

```python
"""Materialize author_stats for a (org_id, domain_id) scope.

Uses python-louvain for graphs ≥ 50 nodes; connected components otherwise.
Writes are idempotent: full scope rewrite per call."""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

import networkx as nx
import community.community_louvain as community_louvain
from sqlalchemy import delete

from backend import models

logger = logging.getLogger(__name__)
_LOUVAIN_THRESHOLD = 50


def _connected_components(G: nx.Graph) -> dict[int, int]:
    out: dict[int, int] = {}
    for cid, comp in enumerate(nx.connected_components(G)):
        for node in comp:
            out[node] = cid
    return out


def recompute_coauthor_stats(db, *, org_id: int, domain_id: str) -> dict:
    t0 = datetime.now(timezone.utc)
    edges = db.query(models.CoauthorEdge).filter_by(org_id=org_id, domain_id=domain_id).all()

    # Wipe prior stats for this scope (full rewrite)
    db.execute(delete(models.AuthorStats).where(
        models.AuthorStats.org_id == org_id,
        models.AuthorStats.domain_id == domain_id,
    ))

    if not edges:
        # Drop dirty marker even when empty
        db.execute(delete(models.CoauthorDirtyScope).where(
            models.CoauthorDirtyScope.org_id == org_id,
            models.CoauthorDirtyScope.domain_id == domain_id,
        ))
        db.commit()
        return {"nodes": 0, "edges": 0, "communities": 0, "wall_time_ms": 0}

    G = nx.Graph()
    for e in edges:
        G.add_edge(e.author_a_id, e.author_b_id, weight=e.weight)

    n_nodes = G.number_of_nodes()
    communities = (
        community_louvain.best_partition(G, weight="weight", random_state=42)
        if n_nodes >= _LOUVAIN_THRESHOLD else _connected_components(G)
    )
    centrality = nx.degree_centrality(G)
    degree = dict(G.degree())

    # publication_count per author within this scope
    pub_counts = {
        author_id: count for author_id, count in
        db.query(models.AuthorPublication.author_id,
                 # Count distinct entities to be safe even if there are dupes
                 # (PK on (author_id, entity_id) makes duplicates impossible, but explicit)
                 # sqlalchemy.func.count
                 ).filter_by(org_id=org_id, domain_id=domain_id)
                  .group_by(models.AuthorPublication.author_id)
                  .all()
    }
    # Above shape is incomplete — Pythonize:
    from sqlalchemy import func
    pub_counts = dict(
        db.query(models.AuthorPublication.author_id, func.count(models.AuthorPublication.entity_id))
          .filter_by(org_id=org_id, domain_id=domain_id)
          .group_by(models.AuthorPublication.author_id)
          .all()
    )

    db.bulk_save_objects([
        models.AuthorStats(
            author_id=node,
            org_id=org_id,
            domain_id=domain_id,
            degree=int(degree.get(node, 0)),
            centrality=float(centrality.get(node, 0.0)),
            community_id=int(communities.get(node, 0)),
            publication_count=int(pub_counts.get(node, 0)),
            computed_at=t0,
        )
        for node in G.nodes()
    ])

    db.execute(delete(models.CoauthorDirtyScope).where(
        models.CoauthorDirtyScope.org_id == org_id,
        models.CoauthorDirtyScope.domain_id == domain_id,
    ))
    db.commit()

    elapsed_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    logger.info(
        "recompute_coauthor_stats scope=(%s, %s) nodes=%d edges=%d communities=%d wall_ms=%d",
        org_id, domain_id, n_nodes, len(edges), len(set(communities.values())), elapsed_ms,
    )
    return {
        "nodes": n_nodes, "edges": len(edges),
        "communities": len(set(communities.values())),
        "wall_time_ms": elapsed_ms,
    }
```

- [ ] **Step 3: Run tests, commit**:

```bash
.venv/Scripts/python -m pytest backend/tests/test_recompute_stats.py -v
git add backend/coauthorship/recompute.py backend/tests/test_recompute_stats.py
git commit -m "feat(coauthor): recompute_coauthor_stats with Louvain + perf gate (F3.2)"
```

### Task F3.3 · Worker hook (dual-write under flag)

**Files:**
- Modify: `backend/enrichment_worker.py`
- Create: `backend/tests/test_worker_coauthor_hook.py`

- [ ] **Step 1: Failing tests**. Key behaviors:
  - When `COAUTHOR_V2_WRITE=false`: no V2 rows written
  - When `COAUTHOR_V2_WRITE=true` and `SHADOW=true`: writes to `*_shadow` tables (see note below)
  - When `COAUTHOR_V2_WRITE=true` and `SHADOW=false`: writes to real V2 tables
  - Dual-write does NOT touch legacy `entity_relationships` (decision: skip per Appendix B)
  - `dirty_scopes` row enqueued after write
  - Idempotent: re-running the hook on the same entity doesn't double-count
  - Tenancy reassignment: if `entity.org_id` changes, hook UPDATEs `author_publications.org_id` and enqueues both old and new scopes

**Note on shadow tables**: implementing seven parallel `*_shadow` tables is heavy. Pragmatic shortcut: under `SHADOW=true` use a single boolean column `is_shadow` on `coauthor_contributions` (and stats/edges) marking the row as shadow-only — readers ignore `is_shadow=true`. Add to F1.1 schema as a follow-up if not already there. **Decision for plan: defer shadow implementation. Run F3 directly to real tables behind `WRITE=false` flag for safety, skip step 2 of cutover sequence.** Update spec §8 cutover during F3 PR review if accepted.

Write tests for the simpler flag-gated flow:

```python
import os
import pytest
from backend.enrichment_worker import write_coauthor_artifacts
from backend.coauthorship.identity import get_or_create_author
from backend import models, config


@pytest.fixture
def write_on(monkeypatch):
    monkeypatch.setattr(config, "COAUTHOR_V2_WRITE", True)


def _entity(db, domain="default", org_id=None, authors=None):
    import json
    attrs = json.dumps({"enrichment_authors": authors or []})
    e = models.RawEntity(name="paper", domain=domain, org_id=org_id, attributes_json=attrs)
    db.add(e); db.commit(); db.refresh(e)
    return e


def test_write_disabled_does_nothing(db):
    e = _entity(db, authors=["John Smith", "Amy Lee"])
    write_coauthor_artifacts(db, e)
    assert db.query(models.AuthorPublication).count() == 0


def test_write_enabled_creates_publications_and_edges(db, write_on):
    e = _entity(db, authors=["John Smith", "Amy Lee"])
    write_coauthor_artifacts(db, e)
    assert db.query(models.AuthorPublication).count() == 2
    assert db.query(models.CoauthorEdge).count() == 1
    assert db.query(models.CoauthorContribution).count() == 1
    # Dirty scope enqueued
    assert db.query(models.CoauthorDirtyScope).filter_by(org_id=0, domain_id="default").count() == 1


def test_write_idempotent(db, write_on):
    e = _entity(db, authors=["John Smith", "Amy Lee"])
    write_coauthor_artifacts(db, e)
    write_coauthor_artifacts(db, e)  # second call must not increment weight
    edge = db.query(models.CoauthorEdge).one()
    assert edge.weight == 1


def test_write_real_org(db, write_on):
    e = _entity(db, authors=["A B", "C D"], org_id=7)
    write_coauthor_artifacts(db, e)
    assert db.query(models.AuthorPublication).filter_by(org_id=7).count() == 2
    assert db.query(models.CoauthorEdge).filter_by(org_id=7).count() == 1


def test_tenancy_reassignment_moves_publications(db, write_on):
    e = _entity(db, authors=["A B", "C D"], org_id=None)
    write_coauthor_artifacts(db, e)
    e.org_id = 9
    db.commit()
    write_coauthor_artifacts(db, e)
    pubs = db.query(models.AuthorPublication).all()
    assert all(p.org_id == 9 for p in pubs)
    # Both old (0) and new (9) scopes enqueued
    scopes = {(s.org_id, s.domain_id) for s in db.query(models.CoauthorDirtyScope).all()}
    assert (0, "default") in scopes
    assert (9, "default") in scopes
```

- [ ] **Step 2: Implement** the new module entry point in `enrichment_worker.py`. Add the function (don't yet call it from the worker loop — that's step 3):

```python
def write_coauthor_artifacts(db, entity) -> None:
    """Write V2 coauthorship rows for one entity. Idempotent.

    Gated by COAUTHOR_V2_WRITE. Does NOT touch legacy entity_relationships
    (decision per spec Appendix B item 2). Handles tenancy reassignment by
    UPDATEing existing publications to the entity's current org_id and
    enqueueing both old and new scopes."""
    from backend import config
    if not config.COAUTHOR_V2_WRITE:
        return
    from backend.analyzers.coauthorship import authors_from_attrs
    from backend.coauthorship.identity import get_or_create_author
    from backend import models
    from itertools import combinations
    from datetime import datetime, timezone

    authors = authors_from_attrs(entity.attributes_json)
    if len(authors) < 2:
        return

    org_id = entity.org_id if entity.org_id is not None else 0
    domain_id = entity.domain or "default"

    # 1. Resolve authors
    author_ids = []
    for pos, name in enumerate(authors[:MAX_AUTHORS_FOR_COAUTH], start=1):
        a = get_or_create_author(db, name)
        author_ids.append((a.id, pos))

    # 2. Handle tenancy reassignment: detect prior org_ids for this entity
    prior_scopes = {
        (p.org_id, p.domain_id) for p in
        db.query(models.AuthorPublication).filter_by(entity_id=entity.id).all()
    }
    if prior_scopes and (org_id, domain_id) not in prior_scopes:
        # Enqueue prior scopes for recompute (their edges will lose this entity's contributions)
        for prior_org, prior_dom in prior_scopes:
            db.merge(models.CoauthorDirtyScope(org_id=prior_org, domain_id=prior_dom, reason="reassign"))
        # Move publication rows to new scope
        db.query(models.AuthorPublication).filter_by(entity_id=entity.id) \
          .update({"org_id": org_id, "domain_id": domain_id}, synchronize_session=False)
        # Remove obsolete contributions; will be re-inserted below in new scope
        db.query(models.CoauthorContribution).filter_by(entity_id=entity.id) \
          .delete(synchronize_session=False)

    # 3. Upsert publications (idempotent via PK)
    existing_pubs = {p.author_id for p in
                     db.query(models.AuthorPublication.author_id)
                       .filter_by(entity_id=entity.id).all()}
    for aid, pos in author_ids:
        if aid not in existing_pubs:
            db.add(models.AuthorPublication(
                author_id=aid, entity_id=entity.id,
                org_id=org_id, domain_id=domain_id, position=pos,
            ))

    # 4. Insert contributions + edges. Contribution PK enforces idempotency.
    from sqlalchemy.exc import IntegrityError
    for (a_id, _), (b_id, _) in combinations(author_ids, 2):
        lo, hi = sorted([a_id, b_id])
        db.add(models.CoauthorContribution(
            entity_id=entity.id, author_a_id=lo, author_b_id=hi,
            org_id=org_id, domain_id=domain_id,
        ))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue  # already contributed — skip edge increment
        # Increment edge weight (UPSERT)
        edge = (
            db.query(models.CoauthorEdge)
              .filter_by(author_a_id=lo, author_b_id=hi, org_id=org_id, domain_id=domain_id)
              .first()
        )
        if edge:
            edge.weight += 1
            edge.last_seen_at = datetime.now(timezone.utc)
        else:
            db.add(models.CoauthorEdge(
                author_a_id=lo, author_b_id=hi,
                org_id=org_id, domain_id=domain_id, weight=1,
            ))

    # 5. Enqueue current scope
    db.merge(models.CoauthorDirtyScope(org_id=org_id, domain_id=domain_id, reason="enrichment"))
    db.commit()
```

- [ ] **Step 3: Call from worker loop**. In `enrichment_worker.py`, after a successful enrichment commit, invoke `write_coauthor_artifacts(db, entity)`. Guard with try/except — never let coauthor write failure break enrichment.

- [ ] **Step 4: Run tests, commit**:

```bash
git add backend/enrichment_worker.py backend/tests/test_worker_coauthor_hook.py
git commit -m "feat(coauthor): worker hook for V2 coauthorship writes (F3.3)"
```

### Task F3.4 · Recompute dispatcher (worker poll loop)

**Files:**
- Modify: `backend/enrichment_worker.py`

- [ ] **Step 1: Add a periodic loop** that polls `coauthor_dirty_scopes` every 30s (debounce 30s on `enqueued_at`) and runs `recompute_coauthor_stats` per row.

```python
async def coauthor_recompute_loop():
    from backend.coauthorship.recompute import recompute_coauthor_stats
    from datetime import datetime, timezone, timedelta
    while True:
        try:
            await asyncio.sleep(30)
            db = SessionLocal()
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
                scopes = (
                    db.query(models.CoauthorDirtyScope)
                      .filter(models.CoauthorDirtyScope.enqueued_at < cutoff)
                      .all()
                )
                for scope in scopes:
                    try:
                        recompute_coauthor_stats(db, org_id=scope.org_id, domain_id=scope.domain_id)
                    except Exception:
                        logger.exception("recompute failed for scope=(%s,%s)",
                                          scope.org_id, scope.domain_id)
            finally:
                db.close()
        except Exception:
            logger.exception("coauthor recompute loop iteration failed")
```

Register in lifespan alongside the existing enrichment task.

- [ ] **Step 2: Commit**:

```bash
git add backend/enrichment_worker.py
git commit -m "feat(coauthor): periodic recompute dispatcher (F3.4)"
```

---

## Phase F4a — Migration + diagnostics (medium-high risk, ~300 LOC)

### Task F4a.1 · Migration library

**Files:**
- Create: `backend/coauthorship/migration.py`
- Create: `backend/scripts/migrate_coauthor_graph.py`
- Create: `backend/tests/test_migration_script.py`

- [ ] **Step 1: Failing tests**:

```python
"""Migration script tests.

Covered: dry-run reports counts without writes; full run is idempotent
(re-running produces same row counts); interruption + resume yields no
duplicates and no missed edges."""
import json
from backend.coauthorship.migration import migrate_coauthor_graph
from backend import models


def _legacy_seed(db, *, entity_id, authors):
    e = models.RawEntity(id=entity_id, name=f"e{entity_id}", domain="default",
                          attributes_json=json.dumps({"enrichment_authors": authors}))
    db.add(e); db.commit()
    from itertools import combinations
    for a, b in combinations(authors, 2):
        lo, hi = sorted([a, b])
        db.add(models.EntityRelationship(
            source_id=entity_id, target_id=entity_id,
            relation_type="CO_AUTHOR", weight=1.0, notes=f"{lo}||{hi}",
            org_id=None,
        ))
    db.commit()


def test_dry_run_no_writes(db):
    _legacy_seed(db, entity_id=1, authors=["John Smith", "Amy Lee"])
    stats = migrate_coauthor_graph(db, dry_run=True)
    assert stats["legacy_edges_found"] == 1
    assert stats["authors_created"] == 0  # dry-run
    assert db.query(models.Author).count() == 0


def test_full_run_creates_authors_and_edges(db):
    _legacy_seed(db, entity_id=1, authors=["John Smith", "Amy Lee", "K. Park"])
    stats = migrate_coauthor_graph(db, dry_run=False)
    assert stats["authors_created"] == 3
    assert stats["edges_created"] == 3
    assert db.query(models.Author).count() == 3
    assert db.query(models.CoauthorEdge).count() == 3


def test_full_run_idempotent(db):
    _legacy_seed(db, entity_id=1, authors=["John Smith", "Amy Lee"])
    migrate_coauthor_graph(db, dry_run=False)
    counts_before = (db.query(models.Author).count(),
                     db.query(models.CoauthorEdge).count(),
                     db.query(models.AuthorPublication).count())
    migrate_coauthor_graph(db, dry_run=False)
    counts_after = (db.query(models.Author).count(),
                    db.query(models.CoauthorEdge).count(),
                    db.query(models.AuthorPublication).count())
    assert counts_before == counts_after


def test_namekey_collapses_legacy_surface_forms(db):
    _legacy_seed(db, entity_id=1, authors=["Smith, John", "John Smith"])  # same person twice — bad
    # Migration must NOT count this as a real coauthor edge (self-pair).
    stats = migrate_coauthor_graph(db, dry_run=False)
    assert stats["self_pairs_skipped"] == 1
    assert db.query(models.CoauthorEdge).count() == 0
    assert db.query(models.Author).count() == 1
```

- [ ] **Step 2: Implement** `migration.py` reusing the F3 worker hook (DRY):

```python
"""One-shot conversion of legacy entity_relationships(CO_AUTHOR) → V2 tables.

Strategy: walk raw_entities with author payloads (the source of truth), not
the notes field (which is lossy). The legacy table is only consulted for
the count + audit. Worker write path is reused so the migration produces
exactly the same shape the runtime would produce — single code path."""
from __future__ import annotations

import logging
from sqlalchemy import select
from backend import models
from backend.analyzers.coauthorship import authors_from_attrs
from backend.coauthorship.identity import get_or_create_author, name_key

logger = logging.getLogger(__name__)


def migrate_coauthor_graph(db, *, dry_run: bool = True, domain: str | None = None) -> dict:
    stats = {
        "legacy_edges_found": 0,
        "entities_scanned": 0,
        "entities_with_authors": 0,
        "authors_created": 0,
        "publications_created": 0,
        "edges_created": 0,
        "self_pairs_skipped": 0,
    }

    # 1. Count legacy edges for the audit
    legacy_q = db.query(models.EntityRelationship).filter_by(relation_type="CO_AUTHOR")
    if domain:
        legacy_q = legacy_q.join(models.RawEntity,
                                  models.RawEntity.id == models.EntityRelationship.source_id) \
                            .filter(models.RawEntity.domain == domain)
    stats["legacy_edges_found"] = legacy_q.count()

    # 2. Walk eligible entities
    ent_q = db.query(models.RawEntity)
    if domain:
        ent_q = ent_q.filter(models.RawEntity.domain == domain)

    initial_author_count = db.query(models.Author).count()
    for ent in ent_q.yield_per(500):
        stats["entities_scanned"] += 1
        authors = authors_from_attrs(ent.attributes_json)
        if len(authors) < 2:
            continue
        stats["entities_with_authors"] += 1
        if dry_run:
            continue

        # Reuse worker hook logic but temporarily force write=on
        from backend import config
        orig = config.COAUTHOR_V2_WRITE
        config.COAUTHOR_V2_WRITE = True
        try:
            from backend.enrichment_worker import write_coauthor_artifacts
            # Detect self-pairs in source — multiple surface forms collapsing to one name_key
            keys = {name_key(a) for a in authors}
            if len(keys) < 2:
                stats["self_pairs_skipped"] += 1
                # Still write publications (one author, many entities), but skip edges path
                for name in authors:
                    a = get_or_create_author(db, name)
                    if not db.query(models.AuthorPublication).filter_by(
                        author_id=a.id, entity_id=ent.id,
                    ).first():
                        db.add(models.AuthorPublication(
                            author_id=a.id, entity_id=ent.id,
                            org_id=ent.org_id or 0,
                            domain_id=ent.domain or "default",
                            position=1,
                        ))
                db.commit()
                continue
            write_coauthor_artifacts(db, ent)
        finally:
            config.COAUTHOR_V2_WRITE = orig

    stats["authors_created"] = db.query(models.Author).count() - initial_author_count if not dry_run else 0
    stats["publications_created"] = db.query(models.AuthorPublication).count() if not dry_run else 0
    stats["edges_created"] = db.query(models.CoauthorEdge).count() if not dry_run else 0

    logger.info("migrate_coauthor_graph dry_run=%s domain=%s stats=%s",
                 dry_run, domain, stats)
    return stats
```

- [ ] **Step 3: CLI wrapper** in `backend/scripts/migrate_coauthor_graph.py` (mirror existing scripts pattern). Argparse with `--dry-run`, `--domain`, prints stats as JSON.

- [ ] **Step 4: Run tests, commit**:

```bash
git add backend/coauthorship/migration.py backend/scripts/migrate_coauthor_graph.py \
        backend/tests/test_migration_script.py
git commit -m "feat(coauthor): one-shot migration library + CLI (F4a.1)"
```

### Task F4a.2 · Diagnostics endpoint + admin endpoints

**Files:**
- Create: `backend/coauthorship/diagnostics.py`
- Create: `backend/routers/coauthorship.py`
- Modify: `backend/main.py` (include router)
- Create: `backend/tests/test_diagnostics_endpoint.py`

- [ ] **Step 1: Failing tests** for `/diagnostics`:

```python
def test_diagnostics_reports_storage_and_scope(client, auth_headers, db_session):
    """/diagnostics returns row counts at every step of the scope pipeline."""
    # Seed authors + edges across two scopes
    ... # use models.Author, AuthorPublication, CoauthorEdge directly
    r = client.get("/analyzers/coauthorship/default/diagnostics", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "edges_in_storage" in body
    assert "edges_after_scope" in body
    assert "authors_total" in body
    assert "dirty_queue_depth" in body
    assert "coverage_pct" in body
    assert "scope_breakdown" in body


def test_diagnostics_distinguishes_super_admin_view(client, super_admin_headers, viewer_headers):
    # Super admin sees global counts; viewer sees only their org
    ...
```

- [ ] **Step 2: Implement** `diagnostics.py`:

```python
"""Storage + scope counters consumed by /diagnostics endpoint."""
from sqlalchemy import func
from backend import models


def diagnostics(db, *, org_id: int | None, domain_id: str) -> dict:
    edges_total = db.query(models.CoauthorEdge).count()
    if org_id is None:
        edges_scoped = (db.query(models.CoauthorEdge)
                          .filter_by(domain_id=domain_id).count())
    else:
        edges_scoped = (db.query(models.CoauthorEdge)
                          .filter_by(org_id=org_id, domain_id=domain_id).count())

    authors_total = db.query(models.Author).count()
    dirty_depth = db.query(models.CoauthorDirtyScope).count()
    last_stats = (db.query(func.max(models.AuthorStats.computed_at))
                    .filter(models.AuthorStats.domain_id == domain_id).scalar())

    # coverage_pct: publications_processed / source_entities_eligible in this scope
    eligible_entities = (db.query(models.RawEntity)
                           .filter(models.RawEntity.domain == domain_id).count())
    if org_id is not None and org_id > 0:
        eligible_entities = (db.query(models.RawEntity)
                                .filter_by(domain=domain_id, org_id=org_id).count())
    processed_entities = (db.query(func.count(func.distinct(models.AuthorPublication.entity_id)))
                            .filter(models.AuthorPublication.domain_id == domain_id).scalar() or 0)
    coverage = (processed_entities / eligible_entities * 100) if eligible_entities else 0.0

    breakdown = dict(
        db.query(models.CoauthorEdge.org_id, func.count())
          .group_by(models.CoauthorEdge.org_id).all()
    )

    return {
        "edges_in_storage": edges_total,
        "edges_after_scope": edges_scoped,
        "authors_total": authors_total,
        "stats_computed_at": last_stats.isoformat() if last_stats else None,
        "dirty_queue_depth": dirty_depth,
        "coverage_pct": round(coverage, 2),
        "scope_breakdown": {"by_org": {str(k): v for k, v in breakdown.items()}},
    }
```

- [ ] **Step 3: Router skeleton** `backend/routers/coauthorship.py`. Implement only `/diagnostics`, `/recompute`, and the merge-suggestions endpoints in this task (the network + author endpoints come in F4b). All routes carry `Depends(get_current_user)`; `/recompute` and merge endpoints add `require_role("super_admin", "admin")`. Apply a simple per-process rate limit on `/recompute` (in-memory dict of `(scope, last_call_ts)`, return 429 if <30s elapsed).

- [ ] **Step 4: Register router** in `backend/main.py`:

```python
from backend.routers import coauthorship as coauthorship_router
app.include_router(coauthorship_router.router)
```

- [ ] **Step 5: Run tests, commit**:

```bash
git add backend/coauthorship/diagnostics.py backend/routers/coauthorship.py \
        backend/main.py backend/tests/test_diagnostics_endpoint.py
git commit -m "feat(coauthor): /diagnostics + /recompute + merge-suggestions endpoints (F4a.2)"
```

### Task F4a.3 · Admin migrate endpoint

**Files:**
- Modify: `backend/routers/coauthorship.py`

- [ ] **Step 1: Add** `POST /admin/data-fixes/migrate-coauthor-graph` (admin+, `dry_run=true` default) that calls `migrate_coauthor_graph` and returns the stats dict. Tests in `test_migration_script.py` already cover the library; add one router-level test verifying admin-only auth.

- [ ] **Step 2: Commit**

```bash
git commit -am "feat(coauthor): admin POST /migrate-coauthor-graph endpoint (F4a.3)"
```

---

## Phase F4b — V2 read endpoints (medium risk, ~250 LOC)

### Task F4b.1 · `GET /analyzers/coauthorship/{domain_id}` (V2 reader behind flag)

**Files:**
- Modify: `backend/routers/coauthorship.py`
- Create: `backend/tests/test_analyzer_v2.py`

- [ ] **Step 1: Failing tests**. Cover:
  - Empty scope returns `{nodes: [], edges: [], computed_at: null, stale: false, coverage_pct: 0}`
  - Populated scope returns sorted nodes by `centrality DESC`
  - `min_weight` filter excludes lighter edges
  - `community_id` filter excludes other communities
  - `search` filter matches `display_name` substring (case-insensitive)
  - `limit` caps node count and prunes edges to surviving nodes
  - Super admin sees global view; org viewer sees only their org_id rows
  - The regression test `test_backfill_visibility_after_recompute` from spec §9

- [ ] **Step 2: Implement** in `routers/coauthorship.py`:

```python
from backend.tenant_access import resolve_request_org_id

@router.get("/analyzers/coauthorship/{domain_id}")
def coauthorship_network_v2(
    response: Response,
    domain_id: str,
    min_weight: int = Query(default=1, ge=1),
    limit: int | None = Query(default=100, ge=1, le=500),
    community_id: int | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=80),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    from backend.config import COAUTHOR_V2_READ
    if not COAUTHOR_V2_READ:
        # Fall through to legacy
        from backend.routers.analytics import analyzer_coauthorship as legacy
        return legacy(response=response, domain_id=domain_id, ...)  # pass through

    response.headers["Cache-Control"] = "no-store"
    org_id = resolve_request_org_id(db, current_user)

    # Nodes query
    q = db.query(models.AuthorStats, models.Author) \
          .join(models.Author, models.Author.id == models.AuthorStats.author_id) \
          .filter(models.AuthorStats.domain_id == domain_id)
    if org_id is not None:
        q = q.filter(models.AuthorStats.org_id == org_id)
    if community_id is not None:
        q = q.filter(models.AuthorStats.community_id == community_id)
    if search:
        like = f"%{search}%"
        q = q.filter(models.Author.display_name.ilike(like))
    q = q.order_by(models.AuthorStats.centrality.desc())
    if limit:
        q = q.limit(limit)
    rows = q.all()

    node_ids = [a.id for _stats, a in rows]
    nodes = [
        {
            "id": str(a.id),
            "label": a.display_name,
            "degree": s.degree,
            "centrality": s.centrality,
            "community_id": s.community_id,
            "total_publications": s.publication_count,
        }
        for s, a in rows
    ]

    # Edges among surviving nodes
    if not node_ids:
        edges_rows = []
    else:
        edge_q = db.query(models.CoauthorEdge) \
                   .filter(models.CoauthorEdge.domain_id == domain_id) \
                   .filter(models.CoauthorEdge.author_a_id.in_(node_ids)) \
                   .filter(models.CoauthorEdge.author_b_id.in_(node_ids)) \
                   .filter(models.CoauthorEdge.weight >= min_weight)
        if org_id is not None:
            edge_q = edge_q.filter(models.CoauthorEdge.org_id == org_id)
        edges_rows = edge_q.all()

    edges = [
        {"source": str(e.author_a_id), "target": str(e.author_b_id), "weight": e.weight}
        for e in edges_rows
    ]

    # Stale flag + coverage
    from datetime import datetime, timezone, timedelta
    latest = max((s.computed_at for s, _ in rows), default=None)
    stale = bool(latest and latest < datetime.now(timezone.utc) - timedelta(minutes=5))
    cov = diagnostics(db, org_id=org_id, domain_id=domain_id)["coverage_pct"]

    return {
        "domain_id": domain_id,
        "nodes": nodes,
        "edges": edges,
        "computed_at": latest.isoformat() if latest else None,
        "stale": stale,
        "coverage_pct": cov,
    }
```

- [ ] **Step 3: Decommission legacy route**. In `backend/routers/analytics.py`, remove or rename the existing `/analyzers/coauthorship/{domain_id}` to `_legacy_coauthorship_network` and re-export only for the fall-through call above. Once `COAUTHOR_V2_READ=true` is set globally, this is dead code; F5 removes it.

- [ ] **Step 4: Run tests, commit**:

```bash
git add backend/routers/coauthorship.py backend/routers/analytics.py \
        backend/tests/test_analyzer_v2.py
git commit -m "feat(coauthor): V2 /analyzers/coauthorship reader behind flag (F4b.1)"
```

### Task F4b.2 · `GET /analyzers/coauthorship/{domain_id}/author/{author_id}`

**Files:**
- Modify: `backend/routers/coauthorship.py`
- Append to `backend/tests/test_analyzer_v2.py`

- [ ] **Step 1: Tests** for author detail: returns publications (top 20 by year desc when available), collaborators (top 50 by weight desc), community summary.

- [ ] **Step 2: Implement** — straightforward SELECT + JOIN. Use `raw_entities.name` as title fallback when no `attributes_json.title`.

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(coauthor): /author/{author_id} endpoint (F4b.2)"
```

### Task F4b.3 · Merge-suggestions API

**Files:**
- Modify: `backend/routers/coauthorship.py`
- Create: `backend/tests/test_merge_suggestions_api.py`

- [ ] **Step 1: Tests**: GET lists pending suggestions; POST `/confirm` calls `merge_authors(tier="manual")` and writes audit; POST `/reject` flips status; non-admin gets 403.

- [ ] **Step 2: Implement**: lookups + state mutations + audit. Reuse `merge_authors` from F2.3. Enqueue dirty scopes for both authors after merge.

- [ ] **Step 3: Commit**

```bash
git commit -am "feat(coauthor): merge-suggestions confirm/reject API (F4b.3)"
```

---

## Phase F4c — Frontend rebuild (medium risk, ~500 LOC)

### Task F4c.1 · `NodePropertiesPanel.tsx`

**Files:**
- Create: `frontend/app/components/graph/NodePropertiesPanel.tsx`

- [ ] **Step 1: Implement** the GraphDB-style side panel. Props: `authorId | null`, `onClose`, `domainId`. Internally fetches `/analyzers/coauthorship/{domain}/author/{authorId}`. Renders: header (display_name + ORCID badge), grid of metrics (publications, degree, centrality, community), collapsible aliases, top collaborators list with weight badges, top publications list (title + year). Show skeleton state during fetch. ARIA `aria-live="polite"`. ~150 LOC.

- [ ] **Step 2: Commit**

```bash
git add frontend/app/components/graph/NodePropertiesPanel.tsx
git commit -m "feat(coauthor): NodePropertiesPanel GraphDB-style (F4c.1)"
```

### Task F4c.2 · `GraphControls.tsx`

**Files:**
- Create: `frontend/app/components/graph/GraphControls.tsx`

- [ ] **Step 1: Implement** zoom/pan/fit controls + top-bar filters (search input, min_weight slider, community dropdown). Emits change events. ~80 LOC.

- [ ] **Step 2: Commit**

```bash
git commit -am "feat(coauthor): GraphControls bar + zoom buttons (F4c.2)"
```

### Task F4c.3 · `MergeSuggestionsPanel.tsx`

**Files:**
- Create: `frontend/app/components/graph/MergeSuggestionsPanel.tsx`

- [ ] **Step 1: Implement** collapsible card listing ambiguous pairs from `/merge-suggestions`. Buttons Merge/Reject. Admin-only (consume `useAuth().user.role`). ~120 LOC.

- [ ] **Step 2: Commit**

```bash
git commit -am "feat(coauthor): MergeSuggestionsPanel (F4c.3)"
```

### Task F4c.4 · Rewrite `NetworkGraph.tsx`

**Files:**
- Modify: `frontend/app/components/graph/NetworkGraph.tsx`
- Modify: `frontend/app/components/graph/useForceLayout.ts`

- [ ] **Step 1: Rewrite** to render:
  - SVG with `<g>` for zoomable surface (d3-zoom installed via d3-selection)
  - Edges as cubic Béziers with grosor `log(weight+1)*1.5px`; midpoint `<text>` label of `weight` shown when scale > 0.7
  - Nodes as `<circle>` with radius `sqrt(publication_count)*2+6`, fill from OKLCH palette indexed by `community_id % 10`
  - Hover: scale neighbor + dim others (via `opacity` transitions)
  - Click: `onNodeClick(id)`
  - Reduced-motion: simulation stops at tick 1
  - Keyboard: when a node is focused, arrow keys cycle neighbors (computed from edge list)
  - ~400 LOC

- [ ] **Step 2: Commit**

```bash
git commit -am "feat(coauthor): rewrite NetworkGraph with GraphDB look (F4c.4)"
```

### Task F4c.5 · Page simplification

**Files:**
- Modify: `frontend/app/analytics/coauthorship/page.tsx`

- [ ] **Step 1: Strip** all derived computations (`selectedNode`, `neighborEdges`, `communityCount`) — they come from API now. Compose top bar + graph + panel + merge suggestions. Remove the old backfill button. Keep error/loading states. Show "Updated N min ago" from `computed_at`, banner "Recomputing…" when `stale`. Show `coverage_pct` if `< 100`.

- [ ] **Step 2: Commit**

```bash
git commit -am "feat(coauthor): simplify coauthorship page to compose V2 components (F4c.5)"
```

### Task F4c.6 · E2E spec

**Files:**
- Create: `frontend/e2e/coauthorship.spec.ts`

- [ ] **Step 1: Write Playwright spec** with the user flow from spec §9. Log in as admin, navigate, await populated graph, click a high-centrality node, assert side panel hydrates, test zoom in/out, assert merge-suggestions panel visible.

- [ ] **Step 2: Commit + run locally**:

```bash
pnpm playwright test e2e/coauthorship.spec.ts
git commit -am "test(coauthor): e2e Playwright spec (F4c.6)"
```

### Task F4c.7 · Visual regression spec

**Files:**
- Create: `frontend/e2e/network_graph_visual.spec.ts`

- [ ] **Step 1: Screenshot baselines** at 320/768/1280/1920, light + dark. Use Playwright's `toHaveScreenshot()`. Run with `--update-snapshots` once to bootstrap.

- [ ] **Step 2: Commit**

```bash
git commit -am "test(coauthor): visual regression baselines (F4c.7)"
```

---

## Phase F5 — Cleanup (low risk, ~80 LOC removed)

Pre-conditions: 7 consecutive stable days post-F4c with `COAUTHOR_V2_READ=true` in production. Verify via prod logs and `/diagnostics` showing `coverage_pct = 100`.

### Task F5.1 · Delete legacy CO_AUTHOR rows

**Files:**
- Create one-shot migration: `backend/scripts/cleanup_legacy_coauthor.py`
- Create: `backend/tests/test_legacy_cleanup.py`

- [ ] **Step 1: Failing test**:

```python
def test_cleanup_deletes_only_coauthor_rows(db):
    db.add(models.EntityRelationship(source_id=1, target_id=1, relation_type="CO_AUTHOR",
                                      notes="a||b", weight=1.0))
    db.add(models.EntityRelationship(source_id=1, target_id=2, relation_type="REFERENCES",
                                      notes="ref", weight=1.0))
    db.commit()
    from backend.scripts.cleanup_legacy_coauthor import run
    deleted = run(db)
    assert deleted == 1
    assert db.query(models.EntityRelationship).filter_by(relation_type="CO_AUTHOR").count() == 0
    assert db.query(models.EntityRelationship).filter_by(relation_type="REFERENCES").count() == 1
```

- [ ] **Step 2: Implement** trivially with `DELETE WHERE relation_type='CO_AUTHOR'`.

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/cleanup_legacy_coauthor.py backend/tests/test_legacy_cleanup.py
git commit -m "feat(coauthor): cleanup script for legacy CO_AUTHOR rows (F5.1)"
```

### Task F5.2 · Drop feature flags + dead code

**Files:**
- Modify: `backend/config.py` (remove three flags)
- Modify: `backend/routers/coauthorship.py` (remove `if not COAUTHOR_V2_READ` branch)
- Delete: `backend/scripts/backfill_coauthor_edges.py`
- Modify: `backend/routers/admin_data_fixes.py` (remove `CoauthorBackfillRequest`, `fix_coauthor_edges`)
- Delete: `backend/tests/test_admin_data_fixes.py` coauthor cases (keep other data-fix tests)
- Modify: `backend/routers/analytics.py` (delete `analyzer_coauthorship`)
- Modify: `backend/analyzers/coauthorship.py` (delete `_load_coauthor_edges`, `coauthorship_network`, but keep `authors_from_attrs` and `extract_coauthor_edges` if any tests still reference — verify)

- [ ] **Step 1: Run full test suite**, fix any imports that broke.

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "chore(coauthor): drop V2 flags + delete legacy code paths (F5.2)"
```

### Task F5.3 · Tag release

```bash
git tag -a coauthor-v2-cleanup -m "Coauthorship V2 refactor complete (F5)"
git push --tags
```

---

## Acceptance checklist (run before declaring done)

- [ ] All test files pass: `.venv/Scripts/python -m pytest backend/tests/test_coauthor*.py backend/tests/test_identity*.py backend/tests/test_merge*.py backend/tests/test_recompute*.py backend/tests/test_migration*.py backend/tests/test_analyzer_v2.py backend/tests/test_diagnostics*.py backend/tests/test_worker_coauthor*.py backend/tests/test_legacy_cleanup.py -v`
- [ ] Coverage ≥ 85% on `backend/coauthorship/`, `backend/routers/coauthorship.py`
- [ ] Performance gate: `test_louvain_100k_edges_under_5s` passes (or documented soft-pass at <10s)
- [ ] Frontend e2e green: `pnpm playwright test e2e/coauthorship.spec.ts e2e/network_graph_visual.spec.ts`
- [ ] Manual smoke: `/analytics/coauthorship` shows populated graph for super_admin, admin (real org), and viewer roles
- [ ] `/diagnostics` returns `edges_after_scope > 0` for every role that sees a populated graph
- [ ] `coverage_pct == 100` reported in `/diagnostics` after migration
- [ ] Zero rows: `SELECT COUNT(*) FROM entity_relationships WHERE relation_type='CO_AUTHOR'` → 0 post-F5

---

## Notes for the implementing engineer

- **Run pytest with `-x`** while iterating; once green, run the full suite to catch interaction breakage.
- **Worker tests use `monkeypatch` to flip flags** — don't mutate `config` globally; the `write_on` fixture pattern is safer.
- **Migration script's `write_coauthor_artifacts` reuse**: it mutates `config.COAUTHOR_V2_WRITE` in a try/finally. Acceptable for the script, but never do this in request handlers.
- **`python-louvain`'s `random_state` is fixed** to keep community IDs stable across runs. Don't remove it.
- **`tenant_access.resolve_request_org_id`** returns `None` for super_admin and the sentinel `LEGACY_GLOBAL_ORG_ID` (currently some negative int) for legacy users. Our V2 code treats `None` as "no filter" and translates LEGACY_GLOBAL_ORG_ID → 0 before SQL. Add a `_persisted_org_id_or_zero` helper if you find yourself repeating this.
- **Aliases JSON cap of 50** is enforced in `_set_aliases`. If you ever see an author with >50 aliases observed, the oldest evicted are gone — that is intentional. The merge audit captures merge events as a separate trail.

End of plan.
