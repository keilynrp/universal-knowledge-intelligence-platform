"""
Trend Topics analyzer — temporal frequency analysis of concepts with slope-based
trend classification (emerging / declining / stable).

Uses the same concept extraction infrastructure as topic_modeling.py.
"""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Any

import numpy as np

from backend.analyzers.topic_modeling import (
    _extract_record_year,
    _load_concepts_timeseries_df,
    _parse_record_concepts,
    _validate_domain,
)

logger = logging.getLogger(__name__)

# Thresholds for trend classification (papers/year slope)
DEFAULT_EMERGING_THRESHOLD = 0.5
DEFAULT_DECLINING_THRESHOLD = 0.5
DEFAULT_MIN_YEARS = 3


class TrendAnalyzer:
    """Analyze concept frequency trends over time for a given domain."""

    def trends(
        self,
        domain_id: str,
        *,
        limit: int = 20,
        min_year: int | None = None,
        max_year: int | None = None,
        min_years: int = DEFAULT_MIN_YEARS,
        emerging_threshold: float = DEFAULT_EMERGING_THRESHOLD,
        declining_threshold: float = DEFAULT_DECLINING_THRESHOLD,
        org_id: int | None = None,
    ) -> dict[str, Any]:
        _validate_domain(domain_id, org_id=org_id)
        df = _load_concepts_timeseries_df(domain_id, org_id=org_id)

        # Build concept × year matrix
        concept_year: dict[str, Counter[int]] = defaultdict(Counter)
        total_with_year = 0

        for row in df.itertuples(index=False):
            year = _extract_record_year(
                getattr(row, "attributes_json", None),
                getattr(row, "primary_label", None),
                getattr(row, "secondary_label", None),
            )
            if year is None:
                continue
            if min_year is not None and year < min_year:
                continue
            if max_year is not None and year > max_year:
                continue

            concepts = _parse_record_concepts(
                getattr(row, "enrichment_concepts", None),
                getattr(row, "attributes_json", None),
            )
            if not concepts:
                continue

            total_with_year += 1
            for concept in set(concepts):
                concept_year[concept][year] += 1

        # Compute slopes and classify
        trends: list[dict[str, Any]] = []
        skipped_count = 0

        for concept, year_counts in concept_year.items():
            distinct_years = sorted(year_counts.keys())
            if len(distinct_years) < min_years:
                skipped_count += 1
                continue

            years_arr = np.array(distinct_years, dtype=float)
            counts_arr = np.array([year_counts[y] for y in distinct_years], dtype=float)

            # Linear regression: slope = frequency change per year
            slope, _ = np.polyfit(years_arr, counts_arr, 1)
            slope = float(slope)

            if slope > emerging_threshold:
                classification = "emerging"
            elif slope < -declining_threshold:
                classification = "declining"
            else:
                classification = "stable"

            total_count = int(sum(year_counts.values()))
            yearly_counts = {y: year_counts[y] for y in distinct_years}

            trends.append({
                "concept": concept,
                "slope": round(slope, 4),
                "classification": classification,
                "total_count": total_count,
                "yearly_counts": yearly_counts,
            })

        # Sort by absolute slope magnitude (most dynamic trends first)
        trends.sort(key=lambda t: abs(t["slope"]), reverse=True)
        trends = trends[:limit]

        return {
            "domain_id": domain_id,
            "total_analyzed": total_with_year,
            "total_concepts": len(concept_year),
            "skipped_count": skipped_count,
            "trends": trends,
        }
