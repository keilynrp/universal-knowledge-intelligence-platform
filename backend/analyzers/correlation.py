"""
Correlation analyzer — Cramér's V between categorical fields using numpy.
No sklearn required.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from backend.database import engine
from backend.schema_registry import registry

logger = logging.getLogger(__name__)

# Fields that carry too many unique values or are free text — skip them
_SKIP_FIELDS = frozenset({
    "entity_name", "title", "sku", "gtin", "doi", "nct_id",
    "enrichment_concepts", "normalized_json", "enrichment_doi",
    "id", "enrichment_citation_count", "enrichment_status", "enrichment_source",
    "validation_status", "creation_date", "barcode", "branches",
    "gtin_reason", "gtin_empty_reason_1", "gtin_empty_reason_2",
    "gtin_empty_reason_3", "gtin_entity_reason", "gtin_reason_lower",
    "gtin_empty_reason_typo", "equipment", "measure", "union_type",
    "entity_code_universal_1", "entity_code_universal_2",
    "entity_code_universal_3", "entity_code_universal_4",
    "brand_lower", "model", "unit_of_measure", "entity_key",
    "variant_status", "variant", "taxes", "branches",
    "allow_sales_without_stock", "control_stock", "is_decimal_sellable",
})

# Categorical fields — must have fewer than this many distinct values
_MAX_CARDINALITY = 50


def _cramers_v(x: np.ndarray, y: np.ndarray) -> float:
    """
    Compute Cramér's V association between two 1-D categorical arrays.
    Returns a float in [0, 1]; 0 = no association, 1 = perfect association.
    """
    # Build contingency table
    x_cats = np.unique(x)
    y_cats = np.unique(y)
    # Fast contingency using pandas crosstab
    ct = np.zeros((len(x_cats), len(y_cats)), dtype=np.int64)
    x_idx = {v: i for i, v in enumerate(x_cats)}
    y_idx = {v: i for i, v in enumerate(y_cats)}
    for xi, yi in zip(x, y):
        ct[x_idx[xi], y_idx[yi]] += 1

    n = ct.sum()
    if n == 0:
        return 0.0

    # Chi-squared statistic
    row_sums = ct.sum(axis=1, keepdims=True)
    col_sums = ct.sum(axis=0, keepdims=True)
    expected = row_sums * col_sums / n
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = np.where(expected > 0, (ct - expected) ** 2 / expected, 0.0).sum()

    k = min(ct.shape[0], ct.shape[1])
    if k <= 1 or n <= 1:
        return 0.0

    v = math.sqrt(chi2 / (n * (k - 1)))  # type: ignore[name-defined]
    return round(float(min(v, 1.0)), 4)


# Use math.sqrt from stdlib — numpy sqrt is fine too, but avoid the need for extra import
import math  # noqa: E402


class CorrelationAnalyzer:
    """Compute pairwise Cramér's V between categorical fields."""

    def top_correlations(
        self, domain_id: str, top_n: int = 20
    ) -> dict[str, Any]:
        """
        Compute Cramér's V for all valid field pairs in the domain.

        Returns:
            {
              "domain_id": str,
              "n_entities": int,
              "fields_analyzed": int,
              "correlations": [
                {"field_a": str, "field_b": str, "cramers_v": float,
                 "strength": "weak"|"moderate"|"strong"}
              ]
            }
        """
        domain = registry.get_domain(domain_id)
        if domain is None:
            raise ValueError(f"Domain '{domain_id}' not found")

        # Which fields to analyze — from domain schema, not _SKIP_FIELDS
        candidate_fields = [
            attr.name
            for attr in domain.attributes
            if attr.name not in _SKIP_FIELDS
        ]

        with engine.connect() as conn:
            cols_sql = ", ".join(f'"{f}"' for f in candidate_fields)
            df = pd.read_sql(
                f"SELECT {cols_sql} FROM raw_entities",  # noqa: S608
                conn,
            )

        n_entities = len(df)

        # Filter to low-cardinality, non-null columns
        usable: list[str] = []
        for col in candidate_fields:
            if col not in df.columns:
                continue
            series = df[col].dropna().astype(str)
            if series.empty:
                continue
            if series.nunique() > _MAX_CARDINALITY:
                continue
            usable.append(col)

        correlations: list[dict] = []
        for a, b in combinations_sorted(usable):
            mask = df[a].notna() & df[b].notna()
            x = df.loc[mask, a].astype(str).values
            y = df.loc[mask, b].astype(str).values
            if len(x) < 5:
                continue
            v = _cramers_v(x, y)
            if v < 0.05:
                continue  # Skip near-zero associations
            strength = (
                "strong" if v >= 0.5
                else "moderate" if v >= 0.2
                else "weak"
            )
            correlations.append({
                "field_a": a,
                "field_b": b,
                "cramers_v": v,
                "strength": strength,
            })

        correlations.sort(key=lambda x: x["cramers_v"], reverse=True)
        correlations = correlations[:top_n]

        return {
            "domain_id": domain_id,
            "n_entities": n_entities,
            "fields_analyzed": len(usable),
            "correlations": correlations,
        }


def combinations_sorted(fields: list[str]):
    """Yield all (a, b) pairs with a < b (sorted)."""
    from itertools import combinations
    yield from combinations(fields, 2)
