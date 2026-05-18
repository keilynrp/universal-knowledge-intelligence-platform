"""
Epistemic classifier — assigns paradigm affinity scores to enriched entities.

Uses weighted term-frequency matching against configurable paradigm indicators
(terms, document types, journal affinities) defined in domain YAML files.
"""
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend import models
from backend.schema_registry import EpistemologyConfig, Paradigm, registry

logger = logging.getLogger(__name__)

_MIN_ABSTRACT_LENGTH = 50
_TERM_WEIGHT = 0.60
_DOCTYPE_WEIGHT = 0.25
_JOURNAL_WEIGHT = 0.15
_BATCH_CHUNK = 500


def _build_term_pattern(term: str) -> re.Pattern:
    escaped = re.escape(term.lower())
    return re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)


def _score_entity(
    abstract: str,
    concepts: str,
    document_type: str,
    journal: str,
    paradigms: list[Paradigm],
) -> dict[str, float]:
    """
    Score an entity against each paradigm.
    Returns a dict of paradigm_id → raw score (not yet normalized).
    """
    text_blob = f"{abstract} {concepts}".lower()
    doc_type_lower = document_type.lower() if document_type else ""
    journal_lower = journal.lower() if journal else ""

    scores: dict[str, float] = {}

    for paradigm in paradigms:
        ind = paradigm.indicators

        # Term score: fraction of indicator terms found in text
        if ind.terms:
            hits = sum(
                1 for term in ind.terms
                if _build_term_pattern(term).search(text_blob)
            )
            term_score = hits / len(ind.terms)
        else:
            term_score = 0.0

        # Document type score
        if ind.document_types and doc_type_lower:
            type_score = 1.0 if any(
                dt.lower() in doc_type_lower
                for dt in ind.document_types
            ) else 0.0
        else:
            type_score = 0.0

        # Journal affinity score
        if ind.journals_affinity and journal_lower:
            journal_score = 1.0 if any(
                j.lower() in journal_lower or journal_lower in j.lower()
                for j in ind.journals_affinity
            ) else 0.0
        else:
            journal_score = 0.0

        # Weighted combination with dynamic renormalization
        active_weight = 0.0
        raw = 0.0
        if ind.terms:
            active_weight += _TERM_WEIGHT
            raw += _TERM_WEIGHT * term_score
        if ind.document_types:
            active_weight += _DOCTYPE_WEIGHT
            raw += _DOCTYPE_WEIGHT * type_score
        if ind.journals_affinity:
            active_weight += _JOURNAL_WEIGHT
            raw += _JOURNAL_WEIGHT * journal_score

        scores[paradigm.id] = raw / active_weight if active_weight > 0 else 0.0

    return scores


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Normalize scores to sum to 1.0. Returns empty dict if all zero."""
    total = sum(scores.values())
    if total == 0:
        return {}
    return {k: round(v / total, 4) for k, v in scores.items()}


def _extract_fields(entity: models.RawEntity) -> tuple[str, str, str, str]:
    """Extract abstract, concepts, document_type, journal from entity."""
    attrs = {}
    try:
        attrs = json.loads(entity.attributes_json or "{}") or {}
    except (TypeError, ValueError):
        pass

    abstract = attrs.get("abstract", "") or ""
    # Also check normalized_json for abstract
    if not abstract:
        try:
            norm = json.loads(entity.normalized_json or "{}") or {}
            abstract = norm.get("abstract", "") or ""
        except (TypeError, ValueError):
            pass

    concepts = entity.enrichment_concepts or ""
    document_type = attrs.get("document_type", "") or ""
    journal = attrs.get("journal", "") or ""
    # Journal might also be on normalized_json
    if not journal:
        try:
            norm = json.loads(entity.normalized_json or "{}") or {}
            journal = norm.get("journal", "") or ""
        except (TypeError, ValueError):
            pass

    return abstract, concepts, document_type, journal


def classify_entity(
    db: Session,
    entity: models.RawEntity,
    paradigms: list[Paradigm],
    *,
    commit: bool = True,
) -> Optional[dict]:
    """
    Classify a single entity and persist the epistemic profile.
    Returns the profile dict, or None if unclassifiable.
    """
    abstract, concepts, document_type, journal = _extract_fields(entity)

    if len(abstract.strip()) < _MIN_ABSTRACT_LENGTH:
        return None

    raw_scores = _score_entity(abstract, concepts, document_type, journal, paradigms)
    normalized = _normalize_scores(raw_scores)

    if not normalized:
        return None

    dominant = max(normalized, key=normalized.get)
    profile = {
        "paradigms": normalized,
        "dominant": dominant,
        "classified_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist into attributes_json
    try:
        attrs = json.loads(entity.attributes_json or "{}") or {}
    except (TypeError, ValueError):
        attrs = {}

    attrs["epistemic_profile"] = profile
    entity.attributes_json = json.dumps(attrs, ensure_ascii=False)

    if commit:
        db.commit()

    return profile


def classify_batch(
    db: Session,
    domain_id: str,
    chunk_size: int = _BATCH_CHUNK,
) -> dict:
    """
    Classify all enriched entities in a domain that lack an epistemic profile.
    Returns stats: {classified, skipped, unclassified}.
    """
    domain = registry.get_domain(domain_id)
    if not domain or not domain.epistemology:
        return {"classified": 0, "skipped": 0, "unclassified": 0, "error": "no_config"}

    paradigms = domain.epistemology.paradigms
    if not paradigms:
        return {"classified": 0, "skipped": 0, "unclassified": 0, "error": "no_paradigms"}

    classified = 0
    skipped = 0
    unclassified = 0

    offset = 0
    while True:
        entities = (
            db.query(models.RawEntity)
            .filter(
                models.RawEntity.domain == domain_id,
                models.RawEntity.enrichment_status == "completed",
            )
            .offset(offset)
            .limit(chunk_size)
            .all()
        )

        if not entities:
            break

        for entity in entities:
            # Check if already classified
            try:
                attrs = json.loads(entity.attributes_json or "{}") or {}
            except (TypeError, ValueError):
                attrs = {}

            if "epistemic_profile" in attrs:
                skipped += 1
                continue

            result = classify_entity(db, entity, paradigms, commit=False)
            if result:
                classified += 1
            else:
                unclassified += 1

        db.commit()
        offset += chunk_size

    return {"classified": classified, "skipped": skipped, "unclassified": unclassified}
