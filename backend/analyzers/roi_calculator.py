"""
ROI Calculator — Monte Carlo projection for R&D investments.
Uses numpy for vectorized simulation (no external stats dependencies).
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import List


@dataclass
class ROIParams:
    investment: float           # Initial investment (USD / any currency unit)
    horizon_years: int          # Projection horizon: 3, 5, or 10
    base_adoption_rate: float   # Expected annual adoption rate (0.0–1.0)
    adoption_volatility: float  # Std-dev of annual adoption rate
    revenue_per_unit: float     # Revenue per adopted unit per year
    market_size: int            # Total addressable market (units)
    annual_cost: float          # Ongoing operating cost per year
    n_simulations: int = 2_000  # Monte Carlo iterations


@dataclass
class YearStats:
    year: int
    optimistic: float   # p90
    median: float       # p50
    pessimistic: float  # p10


@dataclass
class ROIResult:
    # Summary percentiles of final ROI %
    p5:  float
    p10: float
    p25: float
    p50: float   # median
    p75: float
    p90: float
    p95: float

    # Net-value percentiles (same order as ROI %)
    net_p10: float
    net_p50: float
    net_p90: float

    # Scenario labels (final-year net value)
    pessimistic_roi:  float   # p10
    base_roi:         float   # p50
    optimistic_roi:   float   # p90

    breakeven_prob:   float   # fraction of simulations with positive net value
    breakeven_year:   float   # median year when cumulative net > 0 (NaN if never)

    # Year-by-year trajectory (median + bands)
    trajectory: List[YearStats]

    # Histogram buckets for distribution chart
    histogram: List[dict]     # [{"bucket": label, "count": n}, ...]

    n_simulations: int
    params: dict              # echo-back of input params


def simulate(params: ROIParams) -> ROIResult:
    rng = np.random.default_rng()
    N = params.n_simulations
    H = params.horizon_years

    # Sample annual adoption rates: shape (N, H), clipped to [0, 1]
    rates = np.clip(
        rng.normal(params.base_adoption_rate, params.adoption_volatility, (N, H)),
        0.0, 1.0,
    )

    # Annual revenue per simulation: adoption_rate * market_size * revenue_per_unit
    annual_revenue = rates * params.market_size * params.revenue_per_unit  # (N, H)

    # Cumulative net value at each year (subtract investment once + annual costs)
    annual_net = annual_revenue - params.annual_cost                       # (N, H)
    cumulative = np.cumsum(annual_net, axis=1) - params.investment         # (N, H)

    # Final ROI %
    final_net = cumulative[:, -1]                                          # (N,)
    roi_pct = final_net / max(params.investment, 1) * 100.0               # (N,)

    # Percentiles
    p5, p10, p25, p50, p75, p90, p95 = np.percentile(roi_pct, [5, 10, 25, 50, 75, 90, 95])
    np10, np50, np90 = np.percentile(final_net, [10, 50, 90])

    # Break-even probability
    breakeven_prob = float(np.mean(final_net > 0))

    # Median break-even year: first year cumulative > 0 for each simulation
    be_years = []
    for sim in range(N):
        crossing = np.argmax(cumulative[sim] > 0)  # first index where > 0
        if cumulative[sim, crossing] > 0:
            be_years.append(crossing + 1)  # 1-indexed year
    breakeven_year = float(np.median(be_years)) if be_years else float("nan")

    # Year-by-year trajectory (percentiles across simulations)
    trajectory = []
    for y in range(H):
        col = cumulative[:, y] / max(params.investment, 1) * 100.0
        trajectory.append(YearStats(
            year=y + 1,
            optimistic=round(float(np.percentile(col, 90)), 2),
            median=round(float(np.percentile(col, 50)), 2),
            pessimistic=round(float(np.percentile(col, 10)), 2),
        ))

    # Histogram (20 equal-width buckets)
    hist_counts, bin_edges = np.histogram(roi_pct, bins=20)
    histogram = [
        {"bucket": f"{bin_edges[i]:.0f}%", "count": int(hist_counts[i])}
        for i in range(len(hist_counts))
    ]

    return ROIResult(
        p5=round(p5, 2), p10=round(p10, 2), p25=round(p25, 2),
        p50=round(p50, 2), p75=round(p75, 2), p90=round(p90, 2), p95=round(p95, 2),
        net_p10=round(np10, 2), net_p50=round(np50, 2), net_p90=round(np90, 2),
        pessimistic_roi=round(p10, 2),
        base_roi=round(p50, 2),
        optimistic_roi=round(p90, 2),
        breakeven_prob=round(breakeven_prob, 4),
        breakeven_year=round(breakeven_year, 1) if not np.isnan(breakeven_year) else -1,
        trajectory=trajectory,
        histogram=histogram,
        n_simulations=N,
        params={
            "investment": params.investment,
            "horizon_years": params.horizon_years,
            "base_adoption_rate": params.base_adoption_rate,
            "adoption_volatility": params.adoption_volatility,
            "revenue_per_unit": params.revenue_per_unit,
            "market_size": params.market_size,
            "annual_cost": params.annual_cost,
        },
    )
