"""
Weighted scoring engine for the Authority Resolution Layer.

Signal weights (proposal §9):
  0.35  identifiers  — source quality + ORCID hint match
  0.25  name         — fuzzy with diacritic stripping + format variants
  0.20  affiliation  — partial fuzzy vs. candidate description (0 if no context)
  0.10  coauthorship — not yet implemented (always 0; reserved)
  0.10  topic        — not yet implemented (always 0; reserved)

Resolution thresholds (proposal §9):
  >= 0.85  exact_match
  0.65-0.84  probable_match
  0.45-0.64  ambiguous
  < 0.45   unresolved
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from thefuzz import fuzz

from backend.authority.normalize import normalize_name, reformat_surname_first

# ── Signal weights ────────────────────────────────────────────────────────────

_W_ID     = 0.35
_W_NAME   = 0.25
_W_AFFIL  = 0.20
_W_COAUTH = 0.10   # reserved
_W_TOPIC  = 0.10   # reserved

# ── Source quality priors for the identifier signal ───────────────────────────

_SOURCE_QUALITY: dict[str, float] = {
    "orcid":    0.90,   # persistent researcher identifier
    "openalex": 0.70,   # rich academic graph
    "viaf":     0.65,   # bibliographic authority file
    "wikidata": 0.55,   # broad semantic web
    "dbpedia":  0.40,   # derived from Wikipedia
}

# ── Resolution thresholds ─────────────────────────────────────────────────────

_T_EXACT    = 0.85
_T_PROBABLE = 0.65
_T_AMBIGUOUS = 0.45


def _score_identifiers(
    source: str,
    authority_id: str,
    orcid_hint: Optional[str],
    evidence: List[str],
) -> float:
    """
    Base score from source quality.
    Returns 1.0 when an ORCID hint from the original record matches the
    candidate's ORCID ID — the strongest possible signal.
    """
    base = _SOURCE_QUALITY.get(source, 0.30)
    evidence.append(f"source_quality:{source}={base:.2f}")

    if orcid_hint and source == "orcid":
        hint = orcid_hint.strip().removeprefix("https://orcid.org/")
        if hint and hint in authority_id:
            evidence.append("orcid_hint_matched")
            return 1.0

    return base


def _score_name(
    query: str,
    canonical_label: str,
    evidence: List[str],
) -> float:
    """
    Best fuzzy similarity across normalised name variants:
      - normalised query vs. normalised canonical label
      - normalised query vs. canonical label reformatted to 'Firstname Surname'
    Includes a small bonus when all tokens match regardless of order.
    """
    qn = normalize_name(query)
    variants = [
        normalize_name(canonical_label),
        normalize_name(reformat_surname_first(canonical_label)),
    ]

    best = max(fuzz.token_sort_ratio(qn, v) / 100.0 for v in variants)

    # Bonus for complete token overlap (all words present)
    if fuzz.token_set_ratio(qn, variants[0]) == 100:
        best = min(1.0, best + 0.05)
        evidence.append("token_set_exact")

    evidence.append(f"name_score:{best:.3f}")
    return round(best, 3)


def _score_affiliation(
    description: Optional[str],
    affiliation: Optional[str],
    evidence: List[str],
) -> float:
    """
    Partial fuzzy match between the contextual affiliation string and the
    candidate's description (OpenAlex/ORCID descriptions contain the institution).
    Returns 0.0 when either input is absent.
    """
    if not affiliation or not description:
        return 0.0
    score = fuzz.partial_ratio(
        normalize_name(affiliation),
        normalize_name(description),
    ) / 100.0
    if score > 0.6:
        evidence.append(f"affiliation_match:{score:.2f}")
    return round(score, 3)


def compute_score(
    value: str,
    authority_source: str,
    authority_id: str,
    canonical_label: str,
    description: Optional[str],
    orcid_hint: Optional[str] = None,
    affiliation: Optional[str] = None,
    coauthors_overlap: Optional[float] = None,
) -> Tuple[float, dict, List[str], str]:
    """
    Compute the weighted authority score for a single candidate.

    Weights are dynamically renormalised so that unavailable context signals
    (affiliation when not supplied, coauthorship/topic not yet implemented)
    do not penalise the score.  The breakdown always shows raw signal values
    on a 0-1 scale, matching the proposal's example JSON format (§15).

    Returns:
        (total_score, score_breakdown, evidence_list, resolution_status)
    """
    evidence: List[str] = []

    s_id    = _score_identifiers(authority_source, authority_id, orcid_hint, evidence)
    s_name  = _score_name(value, canonical_label, evidence)
    s_affil = _score_affiliation(description, affiliation, evidence)
    # Coauthorship: Jaccard overlap (0–1) of shared collaborators. Only counts
    # toward the score when supplied (entity_type == person with a coauthor ctx).
    has_coauth = coauthors_overlap is not None
    s_coauth = max(0.0, min(1.0, coauthors_overlap)) if has_coauth else 0.0
    if has_coauth:
        evidence.append(f"coauthorship overlap={s_coauth:.2f}")
    s_topic  = 0.0

    # Dynamic weight normalization: when a signal is unavailable its weight
    # is redistributed proportionally among the available signals, so the
    # maximum achievable score is always 1.0 regardless of context supplied.
    nominal_weights = {
        "identifiers":  _W_ID,
        "name":         _W_NAME,
        "affiliation":  _W_AFFIL if affiliation else 0.0,
        "coauthorship": _W_COAUTH if has_coauth else 0.0,
        "topic":        0.0,   # reserved — not yet implemented
    }
    total_w = sum(nominal_weights.values()) or 1.0
    eff = {k: v / total_w for k, v in nominal_weights.items()}

    total = round(
        eff["identifiers"]  * s_id    +
        eff["name"]         * s_name  +
        eff["affiliation"]  * s_affil +
        eff["coauthorship"] * s_coauth +
        eff["topic"]        * s_topic,
        3,
    )

    breakdown = {
        "identifiers":  round(s_id, 3),
        "name":         round(s_name, 3),
        "affiliation":  round(s_affil, 3),
        "coauthorship": s_coauth,
        "topic":        s_topic,
    }

    if total >= _T_EXACT:
        resolution_status = "exact_match"
    elif total >= _T_PROBABLE:
        resolution_status = "probable_match"
    elif total >= _T_AMBIGUOUS:
        resolution_status = "ambiguous"
    else:
        resolution_status = "unresolved"

    return total, breakdown, evidence, resolution_status
