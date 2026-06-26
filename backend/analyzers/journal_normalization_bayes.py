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
