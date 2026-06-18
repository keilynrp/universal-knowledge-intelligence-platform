# Journal Normalized Impact Factor & APC Enrichment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incorporate a field-Normalized Impact Factor (NIF) and the Article Processing Charge (APC) of each journal into the UKIP enrichment circuit, sourced from open data (OpenAlex Sources + DOAJ).

**Architecture:** Journal-level metrics are modeled as a **dedicated `JournalMetric` table keyed by `issn_l`** — not per-work attributes — because one journal recurs across thousands of entities. During enrichment, the OpenAlex adapter extracts the work's `source_id`/`issn_l`, then a **cached source sub-fetch** (`/sources/{id}`) pulls `2yr_mean_citedness`, `h_index`, `apc_usd`. A **DOAJ adapter** overrides APC with the real charge+currency for Open Access journals. A separate **batch normalizer analyzer** computes `normalized_impact_factor = 2yr_mean_citedness / field_median` per OpenAlex subfield. The NIF is an **open proxy of the JIF, not Clarivate's JIF** — provenance is recorded explicitly (`if_metric_kind`).

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, httpx, pytest. Existing patterns: `backend.cache` (Redis/in-process), `backend.circuit_breaker`, the scientometric Adapter pattern (`backend/adapters/enrichment/`).

**Key decisions (locked with user):**
- IF metric = `2yr_mean_citedness` field-normalized (open OpenAlex proxy). JIF Clarivate is proprietary and out of scope.
- Persistence = dedicated `JournalMetric` table, key `issn_l`.
- APC = OpenAlex `apc_usd` baseline, DOAJ overrides when present (real charge + currency).

**Current-state anchors (verified 2026-06-17):**
- Alembic head: `a8b9c0d1e2f3` (backup_assurance_events). New migration `revision = "c4d5e6f7a8b9"`, `down_revision = "a8b9c0d1e2f3"`. (Do NOT reuse `b1c2d3e4f5a6` — it already exists as Sprint 106 nil-detection.)
- NDO: `backend/schemas_enrichment.py` (`EnrichedRecord`).
- OpenAlex adapter parses `primary_location.source` at `backend/adapters/enrichment/openalex.py:135-139` (only publisher today).
- Worker persists enriched fields at `backend/enrichment_worker.py:581-633`; adapter instances/circuit-breakers at lines 52-79; cascade `_PROVIDER_MAP` at line 86.
- Cache package: `backend.cache` exposes `get_cache(namespace, ttl=, maxsize=, serializer=, deserializer=)` and `make_key(tuple)` (see `backend/authority/cache.py` for usage).
- Test gate: CI runs `pytest backend/tests/` ONLY. Place all tests under `backend/tests/`.

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `backend/models.py` | `JournalMetric` ORM table | Modify (append class) |
| `alembic/versions/c4d5e6f7a8b9_journal_metrics.py` | Schema migration | Create |
| `backend/schemas_enrichment.py` | `JournalMetrics` NDO + `journal` field on `EnrichedRecord` | Modify |
| `backend/adapters/enrichment/openalex.py` | Extract `source_id`/`issn_l`; cached `fetch_source_metrics()` | Modify |
| `backend/adapters/enrichment/doaj.py` | DOAJ APC lookup by ISSN | Create |
| `backend/services/journal_metrics_service.py` | Upsert `JournalMetric` (OpenAlex base + DOAJ override) | Create |
| `backend/enrichment_worker.py` | Persist journal metrics during enrichment | Modify |
| `backend/analyzers/journal_normalization.py` | Batch NIF computation per OpenAlex subfield | Create |
| `backend/routers/analytics_ops.py` | Admin endpoint to trigger normalizer | Modify |
| `backend/tests/test_journal_metrics_*.py` | Unit + integration tests per slice | Create |

---

## Task 1: `JournalMetric` model

**Files:**
- Modify: `backend/models.py` (append after `UniversalEntity`/related models)
- Test: `backend/tests/test_journal_metrics_model.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_journal_metrics_model.py
from backend.models import JournalMetric


def test_journal_metric_columns(db_session):
    jm = JournalMetric(
        issn_l="1234-5678",
        source_id="S123",
        display_name="Journal of Testing",
        two_yr_mean_citedness=3.2,
        h_index=80,
        apc_usd=1500,
        apc_currency="USD",
        apc_source="openalex",
        is_in_doaj=True,
        if_metric_kind="openalex_2yr_mean_citedness",
    )
    db_session.add(jm)
    db_session.commit()
    fetched = db_session.query(JournalMetric).filter_by(issn_l="1234-5678").one()
    assert fetched.two_yr_mean_citedness == 3.2
    assert fetched.apc_source == "openalex"
    assert fetched.normalized_impact_factor is None  # not computed yet
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'JournalMetric'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/models.py — append near other tables
class JournalMetric(Base):
    """Journal/source-level scientometric metrics, keyed by ISSN-L.

    One row per journal, reused across many RawEntity works. APC and the
    open Impact-Factor proxy (2yr_mean_citedness) come from OpenAlex/DOAJ;
    normalized_impact_factor is filled by the batch normalizer.
    """
    __tablename__ = "journal_metrics"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    issn_l = Column(String, index=True, nullable=False)
    source_id = Column(String, nullable=True, index=True)  # OpenAlex S-id
    display_name = Column(String, nullable=True)

    # Open IF proxy (NOT Clarivate JIF)
    two_yr_mean_citedness = Column(Float, nullable=True)
    h_index = Column(Integer, nullable=True)
    if_metric_kind = Column(String, default="openalex_2yr_mean_citedness")

    # Article Processing Charge
    apc_usd = Column(Integer, nullable=True)
    apc_currency = Column(String, nullable=True)
    apc_source = Column(String, nullable=True)  # "openalex" | "doaj"
    is_in_doaj = Column(Boolean, nullable=True)

    # Field-normalized impact (filled by batch)
    normalized_impact_factor = Column(Float, nullable=True, index=True)
    nif_field = Column(String, nullable=True)  # OpenAlex subfield used as denominator
    nif_updated_at = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("org_id", "issn_l", name="uq_journal_metric_org_issn"),)
```

Ensure `UniqueConstraint` is imported in `models.py` (add to the existing `from sqlalchemy import ...` line if absent).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/tests/test_journal_metrics_model.py
git commit -m "feat(enrichment): add JournalMetric model for NIF and APC"
```

---

## Task 2: Alembic migration for `journal_metrics`

**Files:**
- Create: `alembic/versions/c4d5e6f7a8b9_journal_metrics.py`
- Test: `backend/tests/test_journal_metrics_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_journal_metrics_migration.py
import pathlib
import re


def test_single_alembic_head():
    versions = pathlib.Path("alembic/versions")
    revisions, downs = set(), set()
    for f in versions.glob("*.py"):
        text = f.read_text(encoding="utf-8")
        if m := re.search(r'^revision\s*=\s*["\']([^"\']+)', text, re.M):
            revisions.add(m.group(1))
        if m := re.search(r'^down_revision\s*=\s*["\']([^"\']+)', text, re.M):
            downs.add(m.group(1))
    heads = revisions - downs
    assert heads == {"c4d5e6f7a8b9"}, f"expected single head c4d5e6f7a8b9, got {heads}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_migration.py -v`
Expected: FAIL — current head is `a8b9c0d1e2f3`, not the new revision. (First also confirm `c4d5e6f7a8b9` is unused: `grep -r "c4d5e6f7a8b9" alembic/versions/` must return nothing.)

- [ ] **Step 3: Write minimal implementation**

```python
# alembic/versions/c4d5e6f7a8b9_journal_metrics.py
"""journal_metrics table for NIF + APC enrichment

Revision ID: c4d5e6f7a8b9
Revises: a8b9c0d1e2f3
"""
import sqlalchemy as sa
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_metrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("issn_l", sa.String, nullable=False),
        sa.Column("source_id", sa.String, nullable=True),
        sa.Column("display_name", sa.String, nullable=True),
        sa.Column("two_yr_mean_citedness", sa.Float, nullable=True),
        sa.Column("h_index", sa.Integer, nullable=True),
        sa.Column("if_metric_kind", sa.String, nullable=True),
        sa.Column("apc_usd", sa.Integer, nullable=True),
        sa.Column("apc_currency", sa.String, nullable=True),
        sa.Column("apc_source", sa.String, nullable=True),
        sa.Column("is_in_doaj", sa.Boolean, nullable=True),
        sa.Column("normalized_impact_factor", sa.Float, nullable=True),
        sa.Column("nif_field", sa.String, nullable=True),
        sa.Column("nif_updated_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("org_id", "issn_l", name="uq_journal_metric_org_issn"),
    )
    op.create_index("ix_journal_metrics_issn_l", "journal_metrics", ["issn_l"])
    op.create_index("ix_journal_metrics_source_id", "journal_metrics", ["source_id"])
    op.create_index("ix_journal_metrics_org_id", "journal_metrics", ["org_id"])
    op.create_index(
        "ix_journal_metrics_normalized_impact_factor",
        "journal_metrics",
        ["normalized_impact_factor"],
    )


def downgrade() -> None:
    op.drop_table("journal_metrics")
```

- [ ] **Step 4: Run test + apply migration**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_migration.py -v`
Expected: PASS
Run: `.venv/Scripts/python -m alembic upgrade head`
Expected: applies `c4d5e6f7a8b9` cleanly (single head).

- [ ] **Step 5: Commit**

```bash
git add alembic/versions/c4d5e6f7a8b9_journal_metrics.py backend/tests/test_journal_metrics_migration.py
git commit -m "feat(enrichment): migration for journal_metrics table"
```

---

## Task 3: `JournalMetrics` NDO + `EnrichedRecord.journal`

**Files:**
- Modify: `backend/schemas_enrichment.py`
- Test: `backend/tests/test_journal_metrics_ndo.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_journal_metrics_ndo.py
from backend.schemas_enrichment import EnrichedRecord, JournalMetrics


def test_enriched_record_carries_journal_metrics():
    rec = EnrichedRecord(
        title="X",
        journal=JournalMetrics(
            issn_l="1111-2222",
            source_id="S99",
            two_yr_mean_citedness=4.1,
            apc_usd=2000,
        ),
    )
    assert rec.journal.issn_l == "1111-2222"
    assert rec.journal.normalized_impact_factor is None


def test_journal_defaults_none_when_absent():
    assert EnrichedRecord(title="Y").journal is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_ndo.py -v`
Expected: FAIL — `cannot import name 'JournalMetrics'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/schemas_enrichment.py — add new model + field
class JournalMetrics(BaseModel):
    """Journal/source-level metrics resolved during enrichment."""
    issn_l: Optional[str] = Field(default=None, description="Linking ISSN")
    source_id: Optional[str] = Field(default=None, description="OpenAlex source ID")
    display_name: Optional[str] = Field(default=None, description="Journal name")
    two_yr_mean_citedness: Optional[float] = Field(default=None, description="Open IF proxy (OpenAlex 2yr mean citedness)")
    h_index: Optional[int] = Field(default=None, description="Source h-index")
    apc_usd: Optional[int] = Field(default=None, description="Article Processing Charge in USD")
    apc_currency: Optional[str] = Field(default=None, description="APC currency when from DOAJ")
    apc_source: Optional[str] = Field(default=None, description="'openalex' | 'doaj'")
    is_in_doaj: Optional[bool] = Field(default=None, description="Indexed in DOAJ")
    normalized_impact_factor: Optional[float] = Field(default=None, description="Field-normalized IF (filled by batch)")
```

Then on `EnrichedRecord` add:

```python
    journal: Optional["JournalMetrics"] = Field(default=None, description="Resolved journal-level metrics")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_ndo.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/schemas_enrichment.py backend/tests/test_journal_metrics_ndo.py
git commit -m "feat(enrichment): JournalMetrics NDO on EnrichedRecord"
```

---

## Task 4: OpenAlex — extract `source_id`/`issn_l` + cached `fetch_source_metrics`

**Files:**
- Modify: `backend/adapters/enrichment/openalex.py`
- Test: `backend/tests/test_journal_metrics_openalex.py`

The work payload's `primary_location.source` has `id` + `issn_l` but NOT `summary_stats`/`apc_usd`. Those require a `/sources/{id}` call, cached by `source_id`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_journal_metrics_openalex.py
from unittest.mock import MagicMock
from backend.adapters.enrichment.openalex import OpenAlexAdapter


def _work_with_source():
    return {
        "display_name": "Paper",
        "primary_location": {
            "source": {"id": "https://openalex.org/S77", "display_name": "Nat", "issn_l": "0028-0836"},
        },
        "authorships": [],
    }


def test_parse_record_captures_source_id_and_issn():
    rec = OpenAlexAdapter()._parse_record(_work_with_source())
    assert rec.journal is not None
    assert rec.journal.source_id == "S77"          # URL prefix stripped
    assert rec.journal.issn_l == "0028-0836"


def test_fetch_source_metrics_parses_summary_stats(monkeypatch):
    adapter = OpenAlexAdapter()
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "id": "https://openalex.org/S77",
        "display_name": "Nat",
        "issn_l": "0028-0836",
        "summary_stats": {"2yr_mean_citedness": 17.4, "h_index": 1200},
        "apc_usd": 11690,
        "is_in_doaj": False,
    }
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    jm = adapter.fetch_source_metrics("S77")
    assert jm.two_yr_mean_citedness == 17.4
    assert jm.h_index == 1200
    assert jm.apc_usd == 11690
    assert jm.apc_source == "openalex"
    assert jm.is_in_doaj is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_openalex.py -v`
Expected: FAIL — `rec.journal is None` / `fetch_source_metrics` missing.

- [ ] **Step 3: Write minimal implementation**

In `_parse_record`, where `source` is read (around line 135), capture the source id/issn and attach a lightweight `JournalMetrics` to the returned `EnrichedRecord`:

```python
# top of file
from backend.schemas_enrichment import JournalMetrics
# (add to existing schemas_enrichment import line)

# inside _parse_record, after computing `publisher`:
journal = None
if source:
    raw_sid = source.get("id")
    source_id = raw_sid.replace("https://openalex.org/", "") if raw_sid else None
    journal = JournalMetrics(
        issn_l=source.get("issn_l"),
        source_id=source_id,
        display_name=source.get("display_name"),
    )
# ...pass `journal=journal` into the EnrichedRecord(...) constructor.
```

Add the cached source fetch + a module-level cache:

```python
# module level, after imports
from backend.cache import get_cache, make_key

_SOURCE_CACHE = get_cache("enrichment:openalex_source", ttl=7 * 24 * 3600, maxsize=20_000)

# method on OpenAlexAdapter
SOURCES_URL = "https://api.openalex.org/sources"

def fetch_source_metrics(self, source_id: str) -> Optional[JournalMetrics]:
    """Fetch /sources/{id} metrics (2yr_mean_citedness, h_index, apc_usd), cached by source_id."""
    if not source_id:
        return None

    def _load():
        params = self._build_params({})
        resp = self.client.get(f"{self.SOURCES_URL}/{source_id}", params=params)
        if resp.status_code != 200:
            return None
        body = resp.json()
        stats = body.get("summary_stats", {}) or {}
        return {
            "issn_l": body.get("issn_l"),
            "source_id": source_id,
            "display_name": body.get("display_name"),
            "two_yr_mean_citedness": stats.get("2yr_mean_citedness"),
            "h_index": stats.get("h_index"),
            "apc_usd": body.get("apc_usd"),
            "apc_source": "openalex" if body.get("apc_usd") is not None else None,
            "is_in_doaj": body.get("is_in_doaj"),
        }

    cached = _SOURCE_CACHE.get_or_load(make_key(("source", source_id)), _load)
    return JournalMetrics(**cached) if cached else None
```

(The cache stores JSON-safe dicts; reconstruct `JournalMetrics` on read. Confirm `get_cache` default serializer handles plain dicts — it does for the in-process backend; for Redis the dict is JSON-serializable.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_openalex.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/enrichment/openalex.py backend/tests/test_journal_metrics_openalex.py
git commit -m "feat(enrichment): OpenAlex source-metric fetch with cache"
```

---

## Task 5: DOAJ adapter for APC override

**Files:**
- Create: `backend/adapters/enrichment/doaj.py`
- Test: `backend/tests/test_journal_metrics_doaj.py`

DOAJ API: `https://doaj.org/api/v2/search/journals/issn:{issn}` returns `bibjson.apc.has_apc` + `bibjson.apc.max[].price`/`.currency`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_journal_metrics_doaj.py
from unittest.mock import MagicMock
from backend.adapters.enrichment.doaj import DoajAdapter


def test_doaj_returns_apc_with_currency(monkeypatch):
    adapter = DoajAdapter()
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "results": [{"bibjson": {"apc": {"has_apc": True, "max": [{"price": 900, "currency": "EUR"}]}}}]
    }
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    apc = adapter.fetch_apc("0028-0836")
    assert apc == {"apc_amount": 900, "apc_currency": "EUR", "apc_source": "doaj", "is_in_doaj": True}


def test_doaj_no_result_returns_none(monkeypatch):
    adapter = DoajAdapter()
    fake = MagicMock(status_code=200)
    fake.json.return_value = {"results": []}
    monkeypatch.setattr(adapter.client, "get", lambda *a, **k: fake)
    assert adapter.fetch_apc("0000-0000") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_doaj.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/adapters/enrichment/doaj.py
from typing import Optional
import httpx

from backend.cache import get_cache, make_key

_DOAJ_CACHE = get_cache("enrichment:doaj_apc", ttl=7 * 24 * 3600, maxsize=20_000)


class DoajAdapter:
    """Lookup APC (amount + currency) for Open Access journals via DOAJ."""

    BASE_URL = "https://doaj.org/api/v2/search/journals/issn:"

    def __init__(self) -> None:
        self.client = httpx.Client(timeout=10.0)

    def fetch_apc(self, issn: str) -> Optional[dict]:
        if not issn:
            return None

        def _load():
            resp = self.client.get(f"{self.BASE_URL}{issn}")
            if resp.status_code != 200:
                return None
            results = resp.json().get("results", [])
            if not results:
                return None
            apc = results[0].get("bibjson", {}).get("apc", {}) or {}
            if not apc.get("has_apc"):
                return {"apc_amount": None, "apc_currency": None, "apc_source": "doaj", "is_in_doaj": True}
            prices = apc.get("max", []) or []
            if not prices:
                return {"apc_amount": None, "apc_currency": None, "apc_source": "doaj", "is_in_doaj": True}
            return {
                "apc_amount": prices[0].get("price"),
                "apc_currency": prices[0].get("currency"),
                "apc_source": "doaj",
                "is_in_doaj": True,
            }

        return _DOAJ_CACHE.get_or_load(make_key(("doaj", issn)), _load)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_doaj.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/adapters/enrichment/doaj.py backend/tests/test_journal_metrics_doaj.py
git commit -m "feat(enrichment): DOAJ adapter for OA journal APC"
```

---

## Task 6: `journal_metrics_service` — upsert with OpenAlex base + DOAJ override

**Files:**
- Create: `backend/services/journal_metrics_service.py`
- Test: `backend/tests/test_journal_metrics_service.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_journal_metrics_service.py
from backend.models import JournalMetric
from backend.schemas_enrichment import JournalMetrics
from backend.services.journal_metrics_service import upsert_journal_metric


def test_upsert_creates_then_updates(db_session):
    jm = JournalMetrics(issn_l="0028-0836", source_id="S77", two_yr_mean_citedness=17.4, apc_usd=11690, apc_source="openalex")
    row1 = upsert_journal_metric(db_session, jm, org_id=None)
    assert row1.two_yr_mean_citedness == 17.4
    # second call updates same row (no duplicate)
    jm2 = JournalMetrics(issn_l="0028-0836", source_id="S77", two_yr_mean_citedness=18.0, apc_usd=11690, apc_source="openalex")
    row2 = upsert_journal_metric(db_session, jm2, org_id=None)
    assert row2.id == row1.id
    assert db_session.query(JournalMetric).filter_by(issn_l="0028-0836").count() == 1
    assert row2.two_yr_mean_citedness == 18.0


def test_doaj_override_wins_for_apc(db_session):
    base = JournalMetrics(issn_l="1111-2222", source_id="S1", apc_usd=2000, apc_source="openalex")
    upsert_journal_metric(db_session, base, org_id=None)
    override = {"apc_amount": 900, "apc_currency": "EUR", "apc_source": "doaj", "is_in_doaj": True}
    row = upsert_journal_metric(db_session, base, org_id=None, doaj=override)
    assert row.apc_currency == "EUR"
    assert row.apc_source == "doaj"
    assert row.is_in_doaj is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/journal_metrics_service.py
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from backend.models import JournalMetric
from backend.schemas_enrichment import JournalMetrics


def upsert_journal_metric(
    db: Session,
    jm: JournalMetrics,
    org_id: Optional[int],
    doaj: Optional[dict] = None,
) -> Optional[JournalMetric]:
    """Insert or update the JournalMetric row for (org_id, issn_l).

    OpenAlex provides the base record; DOAJ (when present) overrides APC
    amount/currency/source and the is_in_doaj flag. Returns None if no ISSN-L.
    """
    if not jm or not jm.issn_l:
        return None

    row = (
        db.query(JournalMetric)
        .filter(JournalMetric.org_id == org_id, JournalMetric.issn_l == jm.issn_l)
        .first()
    )
    if row is None:
        row = JournalMetric(org_id=org_id, issn_l=jm.issn_l)
        db.add(row)

    row.source_id = jm.source_id or row.source_id
    row.display_name = jm.display_name or row.display_name
    if jm.two_yr_mean_citedness is not None:
        row.two_yr_mean_citedness = jm.two_yr_mean_citedness
    if jm.h_index is not None:
        row.h_index = jm.h_index
    row.if_metric_kind = "openalex_2yr_mean_citedness"

    # APC: OpenAlex baseline
    if jm.apc_usd is not None:
        row.apc_usd = jm.apc_usd
        row.apc_currency = "USD"
        row.apc_source = "openalex"
    if jm.is_in_doaj is not None:
        row.is_in_doaj = jm.is_in_doaj

    # DOAJ override wins
    if doaj:
        if doaj.get("apc_amount") is not None:
            row.apc_usd = doaj["apc_amount"]  # nominal amount; currency carries the unit
            row.apc_currency = doaj.get("apc_currency")
            row.apc_source = "doaj"
        if doaj.get("is_in_doaj") is not None:
            row.is_in_doaj = doaj["is_in_doaj"]

    row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()
    return row
```

> Note: `apc_usd` stores the nominal amount; when `apc_source == "doaj"` the unit is `apc_currency`. If strict USD semantics are required later, add a separate `apc_amount` column — deferred (YAGNI).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/journal_metrics_service.py backend/tests/test_journal_metrics_service.py
git commit -m "feat(enrichment): journal metric upsert with DOAJ override"
```

---

## Task 7: Wire journal metrics into the enrichment worker

**Files:**
- Modify: `backend/enrichment_worker.py` (around lines 581-633, the `if enriched_data:` block)
- Test: `backend/tests/test_journal_metrics_worker.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_journal_metrics_worker.py
import json
from backend.models import RawEntity, JournalMetric
from backend.schemas_enrichment import EnrichedRecord, JournalMetrics
from backend import enrichment_worker


def test_worker_persists_journal_metric(db_session, monkeypatch):
    entity = RawEntity(primary_label="Some Paper", domain="science", enrichment_status="pending")
    db_session.add(entity)
    db_session.commit()

    enriched = EnrichedRecord(
        title="Some Paper",
        citation_count=5,
        journal=JournalMetrics(issn_l="0028-0836", source_id="S77"),
    )
    # Drive the REAL cascade: it calls adapter.search_by_title via cb.call(...).
    # Patch OpenAlex's search_by_title so the first active provider returns our record,
    # and stub the new source-metric fetch + force the DOAJ branch off.
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "search_by_title",
                        lambda query, limit=1: [enriched])
    monkeypatch.setattr(enrichment_worker.adapter_openalex, "fetch_source_metrics",
                        lambda sid: JournalMetrics(issn_l="0028-0836", source_id=sid,
                                                   two_yr_mean_citedness=17.4, apc_usd=11690,
                                                   is_in_doaj=False))

    # Real public entry-point (backend/enrichment_worker.py:533).
    enrichment_worker.enrich_single_record(db_session, entity)

    row = db_session.query(JournalMetric).filter_by(issn_l="0028-0836").one()
    assert row.two_yr_mean_citedness == 17.4
    attrs = json.loads(entity.attributes_json or "{}")
    assert attrs.get("issn_l") == "0028-0836"
```

> Verified anchors: public entry-point is `enrich_single_record(db, entity)` (line 533); the cascade is an inline `for provider_name in _ACTIVE_CASCADE` loop that calls `cb.call(adapter.search_by_title, query, limit=1)` (lines 559-576) — there is no `_run_cascade_for_entity` helper. The test patches `search_by_title` on `adapter_openalex` so the real loop exercises the new journal-metric branch. If OpenAlex is not first in `_ACTIVE_CASCADE` in the test env, also set `monkeypatch.setattr(enrichment_worker, "_ACTIVE_CASCADE", ["openalex"])` to make the provider deterministic. Intent of the implementation: when `enriched_data.journal` exists, enrich it via `fetch_source_metrics`, optionally DOAJ, upsert, and store `issn_l` on the entity.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_worker.py -v`
Expected: FAIL — no `JournalMetric` row created.

- [ ] **Step 3: Write minimal implementation**

In the `if enriched_data:` block (after the `attrs` are assembled, before `entity.attributes_json = json.dumps(...)` at line 633), insert:

```python
            # Journal-level metrics (NIF base + APC)
            journal = getattr(enriched_data, "journal", None)
            if journal and journal.source_id:
                full = adapter_openalex.fetch_source_metrics(journal.source_id) or journal
                # carry issn from work if the /sources call didn't echo it
                if not full.issn_l:
                    full.issn_l = journal.issn_l
                doaj_apc = None
                if full.is_in_doaj and full.issn_l:
                    try:
                        from backend.adapters.enrichment.doaj import DoajAdapter
                        doaj_apc = DoajAdapter().fetch_apc(full.issn_l)
                    except Exception:
                        doaj_apc = None
                if full.issn_l:
                    from backend.services.journal_metrics_service import upsert_journal_metric
                    upsert_journal_metric(db, full, org_id=entity.org_id, doaj=doaj_apc)
                    attrs["issn_l"] = full.issn_l
```

(Keep the DOAJ + service imports local to avoid import cycles, matching the worker's existing local-import style at lines 276/774.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_metrics_worker.py -v`
Expected: PASS

- [ ] **Step 5: Run the full enrichment test module to check no regression**

Run: `.venv/Scripts/python -m pytest backend/tests/ -k "enrich" -q`
Expected: PASS (no regressions in existing enrichment tests).

- [ ] **Step 6: Commit**

```bash
git add backend/enrichment_worker.py backend/tests/test_journal_metrics_worker.py
git commit -m "feat(enrichment): persist journal NIF base and APC during enrichment"
```

---

## Task 8: Batch normalizer — field-normalized Impact Factor

**Files:**
- Create: `backend/analyzers/journal_normalization.py`
- Test: `backend/tests/test_journal_normalization.py`

NIF per journal = `two_yr_mean_citedness / median(two_yr_mean_citedness over journals in the same field)`. Field grouping: use `nif_field` derived from the OpenAlex source's primary subfield. For v1, group by a `field` argument supplied per journal (stored on upsert if available); if absent, group all journals into a single `"all"` bucket so the analyzer is still runnable. Pure-Python median (no numpy dependency required, matching `topic_modeling.py` style — though numpy is available).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_journal_normalization.py
from backend.models import JournalMetric
from backend.analyzers.journal_normalization import normalize_impact_factors


def _seed(db, issn, val, field="all"):
    db.add(JournalMetric(issn_l=issn, two_yr_mean_citedness=val, nif_field=field))


def test_nif_is_metric_over_field_median(db_session):
    _seed(db_session, "A", 2.0)
    _seed(db_session, "B", 4.0)
    _seed(db_session, "C", 6.0)  # median = 4.0
    db_session.commit()
    updated = normalize_impact_factors(db_session, org_id=None)
    assert updated == 3
    rows = {r.issn_l: r for r in db_session.query(JournalMetric).all()}
    assert rows["A"].normalized_impact_factor == 0.5   # 2/4
    assert rows["B"].normalized_impact_factor == 1.0   # 4/4
    assert rows["C"].normalized_impact_factor == 1.5   # 6/4
    assert rows["B"].nif_updated_at is not None


def test_journals_without_metric_are_skipped(db_session):
    _seed(db_session, "A", 4.0)
    db_session.add(JournalMetric(issn_l="D", two_yr_mean_citedness=None))
    db_session.commit()
    normalize_impact_factors(db_session, org_id=None)
    d = db_session.query(JournalMetric).filter_by(issn_l="D").one()
    assert d.normalized_impact_factor is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_normalization.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/analyzers/journal_normalization.py
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Optional
from sqlalchemy.orm import Session

from backend.models import JournalMetric


def normalize_impact_factors(db: Session, org_id: Optional[int]) -> int:
    """Compute field-normalized IF for all journals with a metric.

    NIF = two_yr_mean_citedness / median(metric within the same nif_field bucket).
    Returns the count of rows updated.
    """
    q = db.query(JournalMetric).filter(JournalMetric.two_yr_mean_citedness.isnot(None))
    if org_id is not None:
        q = q.filter(JournalMetric.org_id == org_id)
    rows = q.all()

    buckets: dict[str, list[JournalMetric]] = defaultdict(list)
    for r in rows:
        buckets[r.nif_field or "all"].append(r)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    updated = 0
    for field, group in buckets.items():
        med = median([r.two_yr_mean_citedness for r in group])
        if not med:
            continue
        for r in group:
            r.normalized_impact_factor = round(r.two_yr_mean_citedness / med, 4)
            r.nif_field = field
            r.nif_updated_at = now
            updated += 1
    db.flush()
    return updated
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_normalization.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/analyzers/journal_normalization.py backend/tests/test_journal_normalization.py
git commit -m "feat(enrichment): batch field-normalized impact factor"
```

---

## Task 9: Admin endpoint to trigger the normalizer

**Files:**
- Modify: `backend/routers/analytics_ops.py`
- Test: `backend/tests/test_journal_normalization_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_journal_normalization_endpoint.py
from backend.models import JournalMetric


def test_admin_can_trigger_normalization(client, auth_headers, db_session):
    db_session.add(JournalMetric(issn_l="A", two_yr_mean_citedness=2.0))
    db_session.add(JournalMetric(issn_l="B", two_yr_mean_citedness=4.0))
    db_session.commit()
    resp = client.post("/journals/normalize", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2


def test_viewer_forbidden(client, viewer_headers):
    resp = client.post("/journals/normalize", headers=viewer_headers)
    assert resp.status_code == 403
```

> Verified: `analytics_ops.router` is mounted with NO prefix (`app.include_router(analytics_ops.router)` in `backend/main.py:472`), so `@router.post("/journals/normalize")` resolves to `/journals/normalize`. Use the existing `require_role("super_admin", "admin")` dependency pattern already imported in that router.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_normalization_endpoint.py -v`
Expected: FAIL — 404 (route not defined).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/routers/analytics_ops.py — add endpoint following the file's existing patterns
from backend.analyzers.journal_normalization import normalize_impact_factors

@router.post("/journals/normalize")
def trigger_journal_normalization(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Recompute field-normalized Impact Factor across journal_metrics."""
    updated = normalize_impact_factors(db, org_id=user.org_id)
    db.commit()
    return {"updated": updated}
```

(Match the actual imports/dependencies already present in `analytics_ops.py`; do not duplicate `router`/`get_db`/`require_role` imports.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_normalization_endpoint.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routers/analytics_ops.py backend/tests/test_journal_normalization_endpoint.py
git commit -m "feat(enrichment): admin endpoint to recompute NIF"
```

---

## Task 10: Full-suite verification

- [ ] **Step 1: Run the full backend suite**

Run: `.venv/Scripts/python -m pytest backend/tests/ -q`
Expected: all pass, zero new warnings owned by app code.

- [ ] **Step 2: Verify single Alembic head**

Run: `.venv/Scripts/python -m alembic heads`
Expected: single head `c4d5e6f7a8b9`.

- [ ] **Step 3: Final commit (if any cleanup)**

```bash
git add -A
git commit -m "test(enrichment): full-suite verification for NIF + APC"
```

---

## Open items / deferred (YAGNI for v1)

- **Subfield resolution for `nif_field`:** v1 buckets by whatever `nif_field` is set (or `"all"`). A follow-up can populate `nif_field` from the OpenAlex source's primary `topics`/`subfield` during `fetch_source_metrics`, making the normalization genuinely field-specific.
- **Scheduler wiring:** the normalizer is manual (endpoint) for v1. A later slice can call `normalize_impact_factors` from `EnrichmentScheduler.run_once` (`backend/services/enrichment_scheduler.py:209`).
- **Currency normalization for DOAJ APC:** stored as nominal amount + currency; no FX conversion to USD. Add only if a unified-USD report is required.
- **Frontend surfacing:** exposing NIF/APC in entity/analytics responses + UI is a separate front-end plan (provenance label: "Open IF proxy — OpenAlex 2yr mean citedness, field-normalized; not Clarivate JIF").
