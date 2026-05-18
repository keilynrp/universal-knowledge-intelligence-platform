"""
Community health metrics for domain analysis (Fase C).

Computes 5 metrics from existing enrichment data:
  - Gini coefficient of authorship concentration
  - International collaboration rate
  - Open Access publication rate
  - Epistemic diversity (normalized Shannon entropy)
  - Newcomer rate (first-time authors per year)
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend import models
from backend.schema_registry import registry

_MIN_ENTITIES = 3
_LOW_SAMPLE_THRESHOLD = 20
_LOW_SAMPLE_YEAR = 5


# ── Attribute parsing helpers ────────────────────────────────────────────────

def _attrs(entity) -> dict:
    try:
        parsed = json.loads(entity.attributes_json or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _get_year(entity) -> Optional[int]:
    """Extract publication year from entity (attributes_json or normalized_json)."""
    a = _attrs(entity)
    yr = a.get("year")
    if yr is not None:
        try:
            return int(yr)
        except (TypeError, ValueError):
            pass
    try:
        norm = json.loads(getattr(entity, "normalized_json", None) or "{}")
        yr = norm.get("year")
        if yr is not None:
            return int(yr)
    except (TypeError, ValueError):
        pass
    return None


def _extract_authors(entities) -> Dict[str, int]:
    """Return {author_name: publication_count} from enrichment_authors."""
    counts: Dict[str, int] = Counter()
    for e in entities:
        a = _attrs(e)
        authors = a.get("enrichment_authors") or a.get("authors")
        if isinstance(authors, list):
            for name in authors:
                if isinstance(name, str) and name.strip():
                    counts[name.strip()] += 1
        elif isinstance(authors, str) and authors.strip():
            for name in authors.split(","):
                if name.strip():
                    counts[name.strip()] += 1
    return dict(counts)


def _extract_countries(entity) -> List[str]:
    """Parse country data from attributes_json."""
    a = _attrs(entity)
    countries = a.get("countries")
    if isinstance(countries, list):
        return [c for c in countries if isinstance(c, str) and c.strip()]
    country = a.get("extracted_country") or a.get("country")
    if isinstance(country, str) and country.strip():
        return [country.strip()]
    return []


# ── Metric computations ─────────────────────────────────────────────────────

def _gini_coefficient(counts: list[int]) -> float:
    """Gini coefficient from a list of publication counts per author."""
    if not counts or len(counts) < 2:
        return 0.0
    sorted_counts = sorted(counts)
    n = len(sorted_counts)
    total = sum(sorted_counts)
    if total == 0:
        return 0.0
    cumulative = sum((i + 1) * y for i, y in enumerate(sorted_counts))
    return (2 * cumulative) / (n * total) - (n + 1) / n


def _international_collaboration_rate(entities) -> Optional[float]:
    """Fraction of entities with authors from 2+ countries."""
    with_data = 0
    multi_country = 0
    for e in entities:
        countries = _extract_countries(e)
        if countries:
            with_data += 1
            if len(set(countries)) >= 2:
                multi_country += 1
    if with_data == 0:
        return None
    return multi_country / with_data


def _open_access_rate(entities) -> Optional[float]:
    """Fraction of entities marked as Open Access."""
    with_data = 0
    oa_count = 0
    for e in entities:
        a = _attrs(e)
        oa = a.get("is_open_access")
        if oa is not None:
            with_data += 1
            if oa:
                oa_count += 1
    if with_data == 0:
        return None
    return oa_count / with_data


def _epistemic_diversity(entities, paradigm_count: int) -> Optional[float]:
    """Normalized Shannon entropy over paradigm distribution."""
    counts: Dict[str, int] = Counter()
    for e in entities:
        a = _attrs(e)
        profile = a.get("epistemic_profile")
        if isinstance(profile, dict) and profile.get("dominant"):
            counts[profile["dominant"]] += 1
    total = sum(counts.values())
    if total == 0 or paradigm_count < 2:
        return None
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    max_entropy = math.log2(paradigm_count)
    if max_entropy == 0:
        return None
    return entropy / max_entropy


def _newcomer_rate(entities, year: int) -> Optional[float]:
    """Fraction of authors in `year` whose first publication is that year."""
    # Build first-appearance year per author across all entities
    first_year: Dict[str, int] = {}
    authors_in_year: set = set()
    for e in entities:
        e_year = _get_year(e)
        if not e_year:
            continue
        a = _attrs(e)
        author_list = a.get("enrichment_authors") or a.get("authors")
        if isinstance(author_list, str):
            author_list = [n.strip() for n in author_list.split(",") if n.strip()]
        if not isinstance(author_list, list):
            continue
        for name in author_list:
            if not isinstance(name, str) or not name.strip():
                continue
            name = name.strip()
            if name not in first_year or e_year < first_year[name]:
                first_year[name] = e_year
            if e_year == year:
                authors_in_year.add(name)
    if not authors_in_year:
        return None
    newcomers = sum(1 for a in authors_in_year if first_year.get(a) == year)
    return newcomers / len(authors_in_year)


# ── Interpretation labels ────────────────────────────────────────────────────

def _interpret_gini(value: Optional[float]) -> str:
    if value is None:
        return "insufficient_data"
    if value < 0.2:
        return "low_concentration"
    if value < 0.4:
        return "moderate_concentration"
    if value < 0.6:
        return "high_concentration"
    return "very_high_concentration"


def _interpret_rate(value: Optional[float]) -> str:
    if value is None:
        return "insufficient_data"
    if value < 0.1:
        return "very_low"
    if value < 0.3:
        return "low"
    if value < 0.6:
        return "moderate"
    return "high"


def _interpret_diversity(value: Optional[float]) -> str:
    if value is None:
        return "insufficient_data"
    if value < 0.3:
        return "low_diversity"
    if value < 0.6:
        return "moderate_diversity"
    if value < 0.8:
        return "good_diversity"
    return "high_diversity"


_INTERPRETERS = {
    "gini_authorship": _interpret_gini,
    "international_collaboration_rate": _interpret_rate,
    "open_access_rate": _interpret_rate,
    "epistemic_diversity": _interpret_diversity,
    "newcomer_rate": _interpret_rate,
}


# ── Unified engine ───────────────────────────────────────────────────────────

def _build_metric(value: Optional[float], metric_id: str,
                  low_sample: bool = False) -> Dict[str, Any]:
    interpret = _INTERPRETERS.get(metric_id, _interpret_rate)
    result: Dict[str, Any] = {
        "value": round(value, 4) if value is not None else None,
        "label": interpret(value),
    }
    if low_sample:
        result["low_sample"] = True
    return result


def compute_health_metrics(db: Session, domain_id: str) -> Dict[str, Any]:
    """Compute all 5 community health metrics for a domain."""
    entities = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.domain == domain_id)
        .filter(models.RawEntity.enrichment_status == "completed")
        .all()
    )

    n = len(entities)
    too_few = n < _MIN_ENTITIES
    low_sample = 0 < n < _LOW_SAMPLE_THRESHOLD

    # Determine paradigm count from domain config
    domain = registry.get_domain(domain_id)
    paradigm_count = 0
    if domain and domain.epistemology:
        paradigm_count = len(domain.epistemology.paradigms)

    # Aggregate metrics
    if too_few:
        agg = {
            "gini_authorship": None,
            "international_collaboration_rate": None,
            "open_access_rate": None,
            "epistemic_diversity": None,
            "newcomer_rate": None,
        }
    else:
        author_counts = _extract_authors(entities)
        agg = {
            "gini_authorship": _gini_coefficient(list(author_counts.values())),
            "international_collaboration_rate": _international_collaboration_rate(entities),
            "open_access_rate": _open_access_rate(entities),
            "epistemic_diversity": _epistemic_diversity(entities, paradigm_count),
            "newcomer_rate": None,  # aggregate newcomer_rate uses latest year
        }
        # Newcomer rate for the most recent year
        years = sorted({_get_year(e) for e in entities if _get_year(e)})
        if years:
            agg["newcomer_rate"] = _newcomer_rate(entities, years[-1])

    result: Dict[str, Any] = {}
    for metric_id, value in agg.items():
        result[metric_id] = _build_metric(value, metric_id, low_sample=low_sample)

    # Temporal breakdown
    years_map: Dict[int, list] = defaultdict(list)
    for e in entities:
        yr = _get_year(e)
        if yr:
            years_map[yr].append(e)

    for metric_id in agg:
        by_year = []
        for yr in sorted(years_map.keys()):
            yr_entities = years_map[yr]
            yr_n = len(yr_entities)
            yr_low = yr_n < _LOW_SAMPLE_YEAR

            if yr_n < _MIN_ENTITIES:
                val = None
            elif metric_id == "gini_authorship":
                ac = _extract_authors(yr_entities)
                val = _gini_coefficient(list(ac.values()))
            elif metric_id == "international_collaboration_rate":
                val = _international_collaboration_rate(yr_entities)
            elif metric_id == "open_access_rate":
                val = _open_access_rate(yr_entities)
            elif metric_id == "epistemic_diversity":
                val = _epistemic_diversity(yr_entities, paradigm_count)
            elif metric_id == "newcomer_rate":
                val = _newcomer_rate(entities, yr)  # needs full entity set for first_year
            else:
                val = None

            entry: Dict[str, Any] = {
                "year": yr,
                "value": round(val, 4) if val is not None else None,
            }
            if yr_low:
                entry["low_sample"] = True
            by_year.append(entry)

        result[metric_id]["by_year"] = by_year

    return result
