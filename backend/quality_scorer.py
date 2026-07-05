"""
Entity Quality Score — Sprint 72.

Scoring dimensions and weights:
  Field completeness  40%  (primary_label 15, secondary_label 10, canonical_id 10, entity_type 5)
  Enrichment          30%  (completed 25 + doi bonus 5)
  Authority           20%  (has confirmed authority record for primary_label)
  Relationships       10%  (has at least one edge in entity_relationships)
"""
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from backend import models

# Individual weights (sum = 1.0 when all present)
_W = {
    "primary_label":   0.15,
    "secondary_label": 0.10,
    "canonical_id":    0.10,
    "entity_type":     0.05,
    "enrichment":      0.25,
    "enrichment_doi":  0.05,   # bonus: only when enrichment completed
    "authority":       0.20,
    "relationships":   0.10,
}


def _present(val) -> bool:
    return val is not None and str(val).strip() != ""


def _has_canonical_authors(entity: "models.UniversalEntity") -> bool:
    """True when a publication has a non-empty ``attrs["canonical_authors"]``.

    That map is written by the authority publication write-back on confirm, so
    for the OpenAlex model (authors live inside publication attributes, not as
    their own entities) it is the meaningful "authority confirmed" signal — the
    publication's own primary_label (the paper title) can never match an
    author-name authority record.
    """
    raw = getattr(entity, "attributes_json", None)
    if not raw:
        return False
    try:
        attrs = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return False
    ca = attrs.get("canonical_authors") if isinstance(attrs, dict) else None
    return isinstance(ca, dict) and len(ca) > 0


def score_entity(
    entity: models.UniversalEntity,
    confirmed_labels: set[str],
    entities_with_rels: set[int],
) -> tuple[float, dict]:
    """
    Compute quality score for one entity using pre-fetched lookup sets.

    confirmed_labels  — set of original_value strings that have a confirmed AuthorityRecord
    entities_with_rels — set of entity IDs that appear in entity_relationships
    """
    s = 0.0
    bd: dict = {}

    # ── Field completeness ────────────────────────────────────────────────
    for field in ("primary_label", "secondary_label", "canonical_id", "entity_type"):
        w = _W[field]
        ok = _present(getattr(entity, field, None))
        contrib = w if ok else 0.0
        s += contrib
        bd[field] = {"weight": w, "present": ok, "contribution": round(contrib, 4)}

    # ── Enrichment ────────────────────────────────────────────────────────
    status = entity.enrichment_status or "none"
    completed = status == "completed"
    e_contrib = _W["enrichment"] if completed else 0.0
    s += e_contrib
    bd["enrichment_status"] = {
        "weight": _W["enrichment"], "value": status, "contribution": round(e_contrib, 4)
    }
    doi_ok = completed and _present(entity.enrichment_doi)
    doi_contrib = _W["enrichment_doi"] if doi_ok else 0.0
    s += doi_contrib
    bd["enrichment_doi"] = {
        "weight": _W["enrichment_doi"], "present": doi_ok, "contribution": round(doi_contrib, 4)
    }

    # ── Authority ─────────────────────────────────────────────────────────
    # Publications never carry an authority record for their own label (a paper
    # title), so for them "authority confirmed" means their authors have been
    # reconciled — i.e. attrs["canonical_authors"] is populated by the write-back.
    # Every other entity type keeps the original label-match semantics.
    if (entity.entity_type or "") == "publication":
        auth_ok = _has_canonical_authors(entity)
        auth_mode = "canonical_authors"
    else:
        auth_ok = bool(entity.primary_label and entity.primary_label in confirmed_labels)
        auth_mode = "label_match"
    a_contrib = _W["authority"] if auth_ok else 0.0
    s += a_contrib
    bd["authority_confirmed"] = {
        "weight": _W["authority"], "confirmed": auth_ok,
        "mode": auth_mode, "contribution": round(a_contrib, 4),
    }

    # ── Relationships ─────────────────────────────────────────────────────
    rel_ok = entity.id in entities_with_rels
    r_contrib = _W["relationships"] if rel_ok else 0.0
    s += r_contrib
    bd["relationships"] = {
        "weight": _W["relationships"], "has_relationships": rel_ok, "contribution": round(r_contrib, 4)
    }

    return round(min(1.0, s), 4), bd


def _fetch_lookups(db: Session) -> tuple[set[str], set[int]]:
    """Pre-fetch authority + relationship data in 3 queries."""
    confirmed_labels: set[str] = {
        row[0]
        for row in db.query(models.AuthorityRecord.original_value)
        .filter(models.AuthorityRecord.status == "confirmed")
        .all()
        if row[0]
    }
    source_ids = {row[0] for row in db.query(models.EntityRelationship.source_id).all()}
    target_ids = {row[0] for row in db.query(models.EntityRelationship.target_id).all()}
    return confirmed_labels, source_ids | target_ids


def compute_one(entity: models.UniversalEntity, db: Session) -> dict:
    """Compute quality score for a single entity (fetches lookups fresh)."""
    confirmed_labels, entities_with_rels = _fetch_lookups(db)
    score, breakdown = score_entity(entity, confirmed_labels, entities_with_rels)
    return {"score": score, "breakdown": breakdown}


def compute_all(db: Session) -> int:
    """Batch-compute and persist quality_score for every entity. Returns count."""
    confirmed_labels, entities_with_rels = _fetch_lookups(db)
    entities = db.query(models.UniversalEntity).all()
    for entity in entities:
        score, _ = score_entity(entity, confirmed_labels, entities_with_rels)
        entity.quality_score = score
    db.commit()
    return len(entities)
