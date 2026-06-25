# Bayesian NIF (hierarchical shrinkage) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Bayesian, uncertainty-aware companion to the journal NIF — `nif_bayes` plus a 95% credible interval — that shrinks noisy small-sample journals toward their field, alongside (not replacing) the existing `normalized_impact_factor`.

**Architecture:** Closed-form Empirical-Bayes Gamma-Poisson conjugate model in a new analyzer module (`journal_normalization_bayes.py`), sibling of `journal_normalization.py`. The true sample size `n` is the OpenAlex 2-year works count, captured during the existing source fetch into a new `works_2yr` column. Output columns are written by the batch, wired into the existing admin recompute path, backfilled for existing journals, and exposed read-only on the journals API.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, numpy + scipy (already in requirements: scipy 1.17.1, numpy 2.4.2), pytest.

**Spec:** `docs/superpowers/specs/2026-06-25-journal-nif-bayesian-design.md`

**Branch:** `feat/journal-nif-bayesian` (based off origin/main @ #89, `3f689b2`).

**Sub-skills:** @superpowers:test-driven-development, @superpowers:verification-before-completion

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/models.py` (`JournalMetric`, ~line 1299) | Modify | +5 columns: `works_2yr`, `nif_bayes`, `nif_ci_low`, `nif_ci_high`, `nif_bayes_updated_at` |
| `alembic/versions/d6e7f8a9b0c1_journal_nif_bayes.py` | Create | Migration adding the 5 columns + index on `nif_bayes` |
| `backend/tests/test_journal_metrics_migration.py:19`, `backend/tests/test_journal_works_count.py:28` | Modify | Bump asserted single Alembic head to `d6e7f8a9b0c1` |
| `backend/adapters/enrichment/openalex.py` (`fetch_source_metrics`, ~line 141) | Modify | `_works_last_2_complete_years` helper + capture `works_2yr` from `counts_by_year` |
| `backend/schemas_enrichment.py` (`JournalMetrics`, line 25) | Modify | +`works_2yr: Optional[int]` |
| `backend/services/journal_metrics_service.py` (`upsert_journal_metric`, ~line 38) | Modify | Persist `works_2yr` when present |
| `backend/analyzers/journal_normalization_bayes.py` | Create | The Empirical-Bayes batch `normalize_impact_factors_bayes` |
| `backend/routers/analytics_ops.py` (`POST /journals/normalize`, line 442) | Modify | Call the bayes batch after the existing one; return both counters |
| `backend/schemas.py` (`JournalMetricResponse`, line 941) | Modify | +`nif_bayes`, `nif_ci_low`, `nif_ci_high` (auto-populate via `model_validate`) |
| `backend/scripts/backfill_nif_bayes.py` | Create | Management entrypoint: re-fetch `works_2yr` per source + run batch |
| `backend/tests/test_journal_nif_bayes.py` | Create | All new behavior |

**Note on the revision id `d6e7f8a9b0c1`:** any unique id following the repo's rolling-hex convention is fine; this plan uses `d6e7f8a9b0c1`. The existing single head is `c5e6f7a8b9c0`.

---

### Task 1: Schema — new columns + migration

**Files:**
- Modify: `backend/models.py` (`JournalMetric`, after `nif_updated_at` ~line 1301)
- Create: `alembic/versions/d6e7f8a9b0c1_journal_nif_bayes.py`
- Modify: `backend/tests/test_journal_metrics_migration.py:19`, `backend/tests/test_journal_works_count.py:28`
- Test: `backend/tests/test_journal_nif_bayes.py`

- [ ] **Step 1: Write the failing test (columns exist + head moved)**

```python
# backend/tests/test_journal_nif_bayes.py
import importlib.util
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_single_head_is_nif_bayes():
    cfg = Config("alembic.ini")
    heads = set(ScriptDirectory.from_config(cfg).get_heads())
    assert heads == {"d6e7f8a9b0c1"}, f"expected single head d6e7f8a9b0c1, got {heads}"


def test_journalmetric_has_bayes_columns():
    from backend.models import JournalMetric
    cols = set(JournalMetric.__table__.columns.keys())
    assert {"works_2yr", "nif_bayes", "nif_ci_low",
            "nif_ci_high", "nif_bayes_updated_at"} <= cols
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_nif_bayes.py -v`
Expected: FAIL (`nif_bayes` not in columns; head still `c5e6f7a8b9c0`).

- [ ] **Step 3: Add the model columns**

In `backend/models.py`, inside `JournalMetric`, immediately after `nif_updated_at`:
```python
    # Sampling size for the Bayesian model: OpenAlex 2yr paper count.
    works_2yr = Column(Integer, nullable=True)

    # Bayesian (Empirical-Bayes Gamma-Poisson) companion to the NIF —
    # written by normalize_impact_factors_bayes, sibling of normalized_impact_factor.
    nif_bayes = Column(Float, nullable=True, index=True)
    nif_ci_low = Column(Float, nullable=True)
    nif_ci_high = Column(Float, nullable=True)
    nif_bayes_updated_at = Column(DateTime, nullable=True)
```

- [ ] **Step 4: Create the migration**

```python
# alembic/versions/d6e7f8a9b0c1_journal_nif_bayes.py
"""journal NIF bayesian columns

Revision ID: d6e7f8a9b0c1
Revises: c5e6f7a8b9c0
"""
import sqlalchemy as sa
from alembic import op

revision = "d6e7f8a9b0c1"
down_revision = "c5e6f7a8b9c0"
branch_labels = None
depends_on = None

_COLS = [
    ("works_2yr", sa.Integer()),
    ("nif_bayes", sa.Float()),
    ("nif_ci_low", sa.Float()),
    ("nif_ci_high", sa.Float()),
    ("nif_bayes_updated_at", sa.DateTime()),
]


def _has_column(bind, table, col):
    return col in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    for name, type_ in _COLS:
        if not _has_column(bind, "journal_metrics", name):
            op.add_column("journal_metrics", sa.Column(name, type_, nullable=True))
    existing_idx = {i["name"] for i in sa.inspect(bind).get_indexes("journal_metrics")}
    if "ix_journal_metrics_nif_bayes" not in existing_idx:
        op.create_index("ix_journal_metrics_nif_bayes", "journal_metrics", ["nif_bayes"])


def downgrade():
    op.drop_index("ix_journal_metrics_nif_bayes", table_name="journal_metrics")
    for name, _ in _COLS:
        op.drop_column("journal_metrics", name)
```

- [ ] **Step 5: Bump the head assertions in the two existing tests**

In `backend/tests/test_journal_metrics_migration.py:19` and `backend/tests/test_journal_works_count.py:28`, change `{"c5e6f7a8b9c0"}` → `{"d6e7f8a9b0c1"}` (and the message text).

- [ ] **Step 6: Run — expect PASS**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_nif_bayes.py backend/tests/test_journal_metrics_migration.py backend/tests/test_journal_works_count.py -v`
Expected: PASS. Also run `.venv/Scripts/python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"` → `['d6e7f8a9b0c1']`.

- [ ] **Step 7: Commit**

```bash
git add backend/models.py alembic/versions/d6e7f8a9b0c1_journal_nif_bayes.py backend/tests/test_journal_nif_bayes.py backend/tests/test_journal_metrics_migration.py backend/tests/test_journal_works_count.py
git commit -m "feat(journals): journal_metrics bayesian NIF columns + migration"
```

---

### Task 2: Capture `works_2yr` from OpenAlex `counts_by_year`

**Files:**
- Modify: `backend/adapters/enrichment/openalex.py` (`fetch_source_metrics` data dict ~line 146; add module-level helper)
- Modify: `backend/schemas_enrichment.py` (`JournalMetrics`, after line 37)
- Modify: `backend/services/journal_metrics_service.py` (`upsert_journal_metric`, after line 39)
- Test: `backend/tests/test_journal_nif_bayes.py`

- [ ] **Step 1: Write the failing tests (helper + upsert persistence)**

```python
# add to backend/tests/test_journal_nif_bayes.py
import datetime as _dt
from backend.adapters.enrichment.openalex import _works_last_2_complete_years


def test_works_last_2_complete_years_basic():
    yr = _dt.datetime.now(_dt.timezone.utc).year
    counts = [
        {"year": yr,     "works_count": 50},   # current (partial) — excluded
        {"year": yr - 1, "works_count": 40},
        {"year": yr - 2, "works_count": 30},
        {"year": yr - 3, "works_count": 20},   # older — excluded
    ]
    assert _works_last_2_complete_years(counts) == 70   # 40 + 30


def test_works_last_2_complete_years_empty_or_missing():
    assert _works_last_2_complete_years([]) is None
    assert _works_last_2_complete_years(None) is None
    assert _works_last_2_complete_years([{"year": "x"}]) is None


def test_upsert_persists_works_2yr(db_session):
    from backend.services.journal_metrics_service import upsert_journal_metric
    from backend.schemas_enrichment import JournalMetrics
    jm = JournalMetrics(issn_l="1234-5678", two_yr_mean_citedness=3.0, works_2yr=120)
    row = upsert_journal_metric(db_session, jm, org_id=None)
    assert row.works_2yr == 120
```

- [ ] **Step 2: Run — expect FAIL** (`_works_last_2_complete_years` undefined; `JournalMetrics` rejects `works_2yr`).

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_nif_bayes.py -k "works_2yr or works_last" -v`

- [ ] **Step 3: Add `works_2yr` to the `JournalMetrics` schema**

In `backend/schemas_enrichment.py`, after `normalized_impact_factor` (line 37):
```python
    works_2yr: Optional[int] = Field(default=None, description="OpenAlex 2yr paper count (Bayesian model sample size)")
```

- [ ] **Step 4: Add the helper + capture in `openalex.py`**

Module-level helper (near the other private helpers):
```python
def _works_last_2_complete_years(counts) -> Optional[int]:
    """Sum works_count over the two most recent COMPLETE calendar years in
    OpenAlex counts_by_year (the current, partial year is excluded). Returns
    None when the data is absent/unusable."""
    if not counts:
        return None
    current_year = datetime.now(timezone.utc).year
    complete = [
        c for c in counts
        if isinstance(c.get("year"), int) and c["year"] < current_year
        and c.get("works_count") is not None
    ]
    if not complete:
        return None
    complete.sort(key=lambda c: c["year"], reverse=True)
    return sum(int(c["works_count"]) for c in complete[:2])
```
> Ensure `datetime`, `timezone`, and `Optional` are imported in this module (add if missing).

In the `data = {...}` dict of `fetch_source_metrics` (after the `nif_field` line):
```python
            "works_2yr": _works_last_2_complete_years(body.get("counts_by_year")),
```

- [ ] **Step 5: Persist in the upsert**

In `backend/services/journal_metrics_service.py`, after the `h_index` block (line 39):
```python
    if jm.works_2yr is not None:
        row.works_2yr = jm.works_2yr
```

- [ ] **Step 6: Run — expect PASS**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_nif_bayes.py -k "works_2yr or works_last" -v`

- [ ] **Step 7: Commit**

```bash
git add backend/adapters/enrichment/openalex.py backend/schemas_enrichment.py backend/services/journal_metrics_service.py backend/tests/test_journal_nif_bayes.py
git commit -m "feat(journals): capture OpenAlex 2yr works_count into works_2yr"
```

---

### Task 3: The Empirical-Bayes batch

**Files:**
- Create: `backend/analyzers/journal_normalization_bayes.py`
- Test: `backend/tests/test_journal_nif_bayes.py`

- [ ] **Step 1: Write the failing tests**

```python
# add to backend/tests/test_journal_nif_bayes.py
from backend.models import JournalMetric


def _mk(db, **kw):
    row = JournalMetric(org_id=None, **kw)
    db.add(row); db.flush(); return row


def test_bayes_shrinks_small_journal_toward_field(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    # A field of mostly mid-rate journals + one tiny noisy low-rate journal.
    for i in range(6):
        _mk(db_session, issn_l=f"A-{i}", nif_field="Medicine",
            two_yr_mean_citedness=5.0, works_2yr=400)
    tiny = _mk(db_session, issn_l="A-tiny", nif_field="Medicine",
               two_yr_mean_citedness=0.2, works_2yr=5)
    n = normalize_impact_factors_bayes(db_session, org_id=None)
    assert n == 7
    # tiny journal pulled UP toward the field (~1.0); CI wide and non-negative.
    assert tiny.nif_bayes > 0.2 / (5.0)            # moved up from its raw ratio
    assert tiny.nif_ci_low >= 0.0
    assert tiny.nif_ci_high > tiny.nif_bayes


def test_bayes_large_journal_barely_moves(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    for i in range(6):
        _mk(db_session, issn_l=f"B-{i}", nif_field="Physics",
            two_yr_mean_citedness=5.0, works_2yr=800)
    big = _mk(db_session, issn_l="B-big", nif_field="Physics",
              two_yr_mean_citedness=9.0, works_2yr=2000)
    normalize_impact_factors_bayes(db_session, org_id=None)
    # near field-average → nif_bayes close to 9/5 ≈ 1.8 (ref ≈ field mean rate).
    assert big.nif_ci_high - big.nif_ci_low < big.nif_bayes  # tight-ish CI


def test_bayes_skips_rows_without_works_2yr(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    r = _mk(db_session, issn_l="C-1", nif_field="Chemistry",
            two_yr_mean_citedness=4.0, works_2yr=None)
    normalize_impact_factors_bayes(db_session, org_id=None)
    assert r.nif_bayes is None


def test_bayes_zero_citedness_ci_nonnegative(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    for i in range(6):
        _mk(db_session, issn_l=f"D-{i}", nif_field="Biology",
            two_yr_mean_citedness=4.0, works_2yr=300)
    z = _mk(db_session, issn_l="D-z", nif_field="Biology",
            two_yr_mean_citedness=0.0, works_2yr=30)
    normalize_impact_factors_bayes(db_session, org_id=None)
    assert z.nif_bayes is not None and z.nif_ci_low >= 0.0


def test_bayes_small_bucket_uses_global_prior(db_session):
    from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
    # Big well-populated field + a 1-journal field that must borrow the global prior.
    for i in range(8):
        _mk(db_session, issn_l=f"E-{i}", nif_field="Medicine",
            two_yr_mean_citedness=5.0, works_2yr=400)
    lone = _mk(db_session, issn_l="E-lone", nif_field="Mathematics",
               two_yr_mean_citedness=3.0, works_2yr=50)
    n = normalize_impact_factors_bayes(db_session, org_id=None)
    assert lone.nif_bayes is not None   # computed via global-prior fallback, not skipped
```

- [ ] **Step 2: Run — expect FAIL** (module does not exist).

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_nif_bayes.py -k bayes -v`

- [ ] **Step 3: Implement the batch**

```python
# backend/analyzers/journal_normalization_bayes.py
"""Empirical-Bayes Gamma-Poisson shrinkage of the journal NIF.

Sibling of journal_normalization.py. Writes nif_bayes + a 95% credible
interval ALONGSIDE normalized_impact_factor (does not replace it). See
docs/superpowers/specs/2026-06-25-journal-nif-bayesian-design.md.
"""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from scipy.stats import gamma as _gamma
from sqlalchemy.orm import Session

from backend.models import JournalMetric

_SMALL_BUCKET_K = 5   # buckets smaller than this borrow the global prior
_EPS = 1e-6


def _fit_prior(rates: np.ndarray, ns: np.ndarray) -> tuple[float, float]:
    """Method-of-moments Gamma(shape a, rate b) prior over journal citation
    rates, with the Poisson sampling component removed from the between-journal
    variance so the prior reflects true dispersion, not noise."""
    m = float(np.sum(rates * ns) / np.sum(ns))      # pooled rate = ΣC/Σn
    if m <= 0:
        return _EPS, _EPS
    raw_var = float(np.var(rates))                  # observed between-journal var
    sampling = float(np.mean(m / ns))               # mean Poisson sampling var ≈ m/n
    v = max(raw_var - sampling, _EPS)
    return m * m / v, m / v


def normalize_impact_factors_bayes(db: Session, org_id: Optional[int]) -> int:
    """Compute nif_bayes + CI for every eligible journal. Returns rows updated."""
    q = (db.query(JournalMetric)
           .filter(JournalMetric.two_yr_mean_citedness.isnot(None))
           .filter(JournalMetric.works_2yr.isnot(None)))
    if org_id is not None:
        q = q.filter(JournalMetric.org_id == org_id)

    obs = []   # (row, rate, n, C)
    for r in q.all():
        n = int(r.works_2yr)
        if n <= 0:
            continue
        rate = float(r.two_yr_mean_citedness)
        obs.append((r, rate, n, round(rate * n)))
    if not obs:
        return 0

    # Global prior — fallback for small buckets (mirrors normalize_impact_factors'
    # "all" handling but at the prior level).
    g_a, g_b = _fit_prior(
        np.array([o[1] for o in obs], dtype=float),
        np.array([o[2] for o in obs], dtype=float),
    )

    buckets: dict[str, list] = defaultdict(list)
    for o in obs:
        buckets[o[0].nif_field or "all"].append(o)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    updated = 0
    for _field, group in buckets.items():
        if len(group) >= _SMALL_BUCKET_K:
            a, b = _fit_prior(
                np.array([o[1] for o in group], dtype=float),
                np.array([o[2] for o in group], dtype=float),
            )
        else:
            a, b = g_a, g_b
        ref = a / b                       # field reference rate → nif_bayes 1.0 == avg
        if ref <= 0:
            continue
        for r, _rate, n, C in group:
            post_a, post_b = a + C, b + n
            rate_post = post_a / post_b
            lo, hi = _gamma.ppf([0.025, 0.975], a=post_a, scale=1.0 / post_b)
            r.nif_bayes = round(rate_post / ref, 4)
            r.nif_ci_low = round(float(lo) / ref, 4)
            r.nif_ci_high = round(float(hi) / ref, 4)
            r.nif_bayes_updated_at = now
            updated += 1
    db.flush()
    return updated
```

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_nif_bayes.py -k bayes -v`

- [ ] **Step 5: Commit**

```bash
git add backend/analyzers/journal_normalization_bayes.py backend/tests/test_journal_nif_bayes.py
git commit -m "feat(journals): empirical-Bayes Gamma-Poisson NIF shrinkage batch"
```

---

### Task 4: Wire into the admin recompute endpoint

**Files:**
- Modify: `backend/routers/analytics_ops.py` (import ~line 35; `POST /journals/normalize` line 442-454)
- Test: `backend/tests/test_journal_nif_bayes.py`

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_journal_nif_bayes.py
def test_recompute_returns_both_counters(client, auth_headers, db_session):
    from backend.models import JournalMetric
    for i in range(6):
        db_session.add(JournalMetric(org_id=None, issn_l=f"R-{i}", nif_field="Medicine",
                                     two_yr_mean_citedness=5.0, works_2yr=400))
    db_session.commit()
    resp = client.post("/journals/normalize", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "updated" in body and "updated_bayes" in body
    assert body["updated_bayes"] == 6
```
> **Fixture:** use `auth_headers` — the conftest's **super_admin** token (there is no `admin_headers` fixture; `test_journal_normalization_endpoint.py` authenticates this same endpoint with `auth_headers`). This is **load-bearing, not cosmetic**: super_admin resolves to `org_id=None`, so the batch's scope matches the seeded `org_id=None` rows and `updated_bayes == 6`. A non-super-admin "admin" would resolve to `LEGACY_GLOBAL_ORG_ID = -1`, the batch would filter `org_id == -1`, miss the rows, and assert `0`. Do not substitute a differently-scoped fixture.

- [ ] **Step 2: Run — expect FAIL** (`updated_bayes` missing).

- [ ] **Step 3: Wire the call**

In `backend/routers/analytics_ops.py`, extend the existing import:
```python
from backend.analyzers.journal_normalization import normalize_impact_factors
from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes
```
In `trigger_journal_normalization`, after line 452:
```python
    updated = normalize_impact_factors(db, org_id=org_id)
    updated_bayes = normalize_impact_factors_bayes(db, org_id=org_id)
    db.commit()
    return {"updated": updated, "updated_bayes": updated_bayes}
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/routers/analytics_ops.py backend/tests/test_journal_nif_bayes.py
git commit -m "feat(journals): recompute writes nif_bayes alongside NIF"
```

---

### Task 5: Expose on the journals read API

**Files:**
- Modify: `backend/schemas.py` (`JournalMetricResponse`, after line 954)
- Test: `backend/tests/test_journal_nif_bayes.py`

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_journal_nif_bayes.py
def test_journals_api_exposes_nif_bayes(client, auth_headers, db_session):
    from backend.models import JournalMetric
    db_session.add(JournalMetric(org_id=None, issn_l="X-1", nif_field="Medicine",
                                 two_yr_mean_citedness=5.0, works_2yr=400,
                                 nif_bayes=1.02, nif_ci_low=0.8, nif_ci_high=1.25))
    db_session.commit()
    resp = client.get("/journals", headers=auth_headers)
    assert resp.status_code == 200
    row = next(r for r in resp.json() if r["issn_l"] == "X-1")
    assert row["nif_bayes"] == 1.02
    assert row["nif_ci_low"] == 0.8 and row["nif_ci_high"] == 1.25
```

- [ ] **Step 2: Run — expect FAIL** (keys absent from response).

- [ ] **Step 3: Add the response fields**

In `backend/schemas.py`, in `JournalMetricResponse`, after `nif_updated_at` (line 954):
```python
    nif_bayes: Optional[float] = None
    nif_ci_low: Optional[float] = None
    nif_ci_high: Optional[float] = None
```
No router change needed — `journals.py` already builds the response via `JournalMetricResponse.model_validate(row)`, and these are ORM columns.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/schemas.py backend/tests/test_journal_nif_bayes.py
git commit -m "feat(journals): expose nif_bayes + credible interval on read API"
```

---

### Task 6: Backfill script

**Files:**
- Create: `backend/scripts/backfill_nif_bayes.py`
- Test: `backend/tests/test_journal_nif_bayes.py`

- [ ] **Step 1: Write the failing test (orchestration, OpenAlex mocked)**

```python
# add to backend/tests/test_journal_nif_bayes.py
def test_backfill_populates_and_runs_batch(db_session):
    from backend.models import JournalMetric
    from backend.schemas_enrichment import JournalMetrics
    from backend.scripts.backfill_nif_bayes import run_backfill
    for i in range(6):
        db_session.add(JournalMetric(org_id=None, issn_l=f"BF-{i}", source_id=f"S{i}",
                                     nif_field="Medicine", two_yr_mean_citedness=5.0))
    db_session.commit()

    # Fake adapter: returns a JournalMetrics with works_2yr, no network.
    class _FakeAdapter:
        def fetch_source_metrics(self, source_id):
            return JournalMetrics(issn_l=None, source_id=source_id, works_2yr=400)

    updated = run_backfill(db_session, org_id=None, refresh=False, adapter=_FakeAdapter())
    assert updated == 6
    rows = db_session.query(JournalMetric).all()
    assert all(r.works_2yr == 400 for r in rows)
    assert all(r.nif_bayes is not None for r in rows)
```
> `run_backfill` takes an injectable `adapter` so the test never hits OpenAlex (no monkeypatch). With `refresh=False` the test also never calls `clear_source_cache()` (Redis).

- [ ] **Step 2: Run — expect FAIL** (module does not exist).

- [ ] **Step 3: Implement the script**

```python
# backend/scripts/backfill_nif_bayes.py
"""Backfill works_2yr for existing journals, then recompute nif_bayes.

Usage: python -m backend.scripts.backfill_nif_bayes [--org-id N] [--refresh] [--delay 0.1]

Iterates journal_metrics rows directly (one OpenAlex /sources fetch per journal,
not per work), populates works_2yr, then runs the Empirical-Bayes batch.
Idempotent and org-scoped. With --refresh, clears the Redis-backed source cache
first (via clear_source_cache, #89) so stale cached dicts lacking works_2yr are
re-fetched. --delay throttles between fetches to stay in OpenAlex's polite pool.
"""
import argparse
import time
from typing import Optional

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import JournalMetric
from backend.adapters.enrichment.openalex import OpenAlexAdapter, clear_source_cache
from backend.analyzers.journal_normalization_bayes import normalize_impact_factors_bayes


def run_backfill(db: Session, org_id: Optional[int], refresh: bool = False,
                 adapter=None, delay: float = 0.0) -> int:
    """Populate works_2yr from OpenAlex per journal, then recompute nif_bayes.

    `adapter` is injectable for testing (must expose `fetch_source_metrics(source_id)`
    returning a JournalMetrics with `works_2yr`). Returns rows updated by the batch.
    """
    if refresh:
        clear_source_cache()                       # Redis: drop stale pre-works_2yr dicts
    adapter = adapter or OpenAlexAdapter()

    q = db.query(JournalMetric).filter(JournalMetric.source_id.isnot(None))
    if org_id is not None:
        q = q.filter(JournalMetric.org_id == org_id)

    for i, row in enumerate(q.all()):
        if delay and i:
            time.sleep(delay)
        jm = adapter.fetch_source_metrics(row.source_id)
        if jm is not None and getattr(jm, "works_2yr", None) is not None:
            row.works_2yr = jm.works_2yr
    db.flush()
    updated = normalize_impact_factors_bayes(db, org_id=org_id)
    db.commit()
    return updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org-id", type=int, default=None)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--delay", type=float, default=0.0)
    args = ap.parse_args()
    db = SessionLocal()
    try:
        n = run_backfill(db, org_id=args.org_id, refresh=args.refresh, delay=args.delay)
        print(f"nif_bayes recomputed for {n} journals")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```
> Uses the real adapter API: `OpenAlexAdapter` + `clear_source_cache` (both already exported from `backend/adapters/enrichment/openalex.py`, used by `backend/services/journal_backfill.py`). `fetch_source_metrics(source_id)` is single-arg (no `refresh` kwarg); cache-busting is the separate `clear_source_cache()` call.

- [ ] **Step 4: Run — expect PASS**

Run: `.venv/Scripts/python -m pytest backend/tests/test_journal_nif_bayes.py -k backfill -v`

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/backfill_nif_bayes.py backend/tests/test_journal_nif_bayes.py
git commit -m "feat(journals): backfill works_2yr + recompute nif_bayes script"
```

---

### Task 7: Full-suite verification

- [ ] **Step 1: Run the whole journals/enrichment test surface**

Run: `.venv/Scripts/python -m pytest backend/tests/ -k "journal or enrichment or migration or analytics_ops" -q`
Expected: all PASS (watch the two head-assertion tests and the migration drift test).

- [ ] **Step 2: Run the full backend suite**

Run: `.venv/Scripts/python -m pytest backend/tests/ -q`
Expected: green. Per @superpowers:verification-before-completion, do not declare done until this passes.

- [ ] **Step 3: Confirm a single Alembic head**

Run: `.venv/Scripts/python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; print(ScriptDirectory.from_config(Config('alembic.ini')).get_heads())"`
Expected: `['d6e7f8a9b0c1']`.

- [ ] **Step 4: Push + open PR** (only when the user asks)

```bash
git push -u origin feat/journal-nif-bayesian
```
> Repo note: `git push` can hang on Git Credential Manager; if so push via the `gh` API contents path or the established gh-credential-helper workaround. `main` has no branch protection.

---

## Deferred follow-ups (NOT in this plan)

- **Frontend surfacing** — `nif_bayes` + CI in the entity modal "Journal" section and the `/analytics/journals` dashboard (mirrors NIF's #82). Separate spec → plan.
- **Prod backfill execution** — run `python -m backend.scripts.backfill_nif_bayes --refresh` in the Dokploy container after deploy (single-line command; see prod-rotation operator notes).
- **`counts_by_year` live-shape confirmation** and `K`/`ε` calibration against the real field-size distribution (flagged as spec open items).
