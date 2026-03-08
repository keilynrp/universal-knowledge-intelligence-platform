"""
Entity Linker — TF-IDF cosine similarity for duplicate/near-duplicate detection.

Uses only numpy (already a dependency). No external model or network required.
Algorithm:
  1. Tokenize key fields of every entity.
  2. Build a TF-IDF matrix (smoothed IDF, L2-normalized rows).
  3. Cosine similarity via matrix dot-product (vectorized, fast).
  4. Return pairs above threshold, skipping dismissed pairs.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session

from . import models

# ── Tokenizer ─────────────────────────────────────────────────────────────────

_SPLIT_RE = re.compile(r"[\s\-_/.,;:()\[\]{}|]+")

def _tokenize(text: str) -> list[str]:
    return [t for t in _SPLIT_RE.split(text.lower()) if len(t) > 1]

def _entity_text(e: models.RawEntity) -> str:
    parts = [
        e.entity_name or "",
        e.brand_capitalized or "",
        e.model or "",
        e.classification or "",
        e.variant or "",
        e.sku or "",
    ]
    return " ".join(p for p in parts if p)

def _entity_dict(e: models.RawEntity) -> dict:
    return {
        "id":                  e.id,
        "entity_name":         e.entity_name,
        "brand_capitalized":   e.brand_capitalized,
        "model":               e.model,
        "sku":                 e.sku,
        "gtin":                e.gtin,
        "barcode":             e.barcode,
        "classification":      e.classification,
        "variant":             e.variant,
        "unit_of_measure":     e.unit_of_measure,
        "enrichment_status":   e.enrichment_status,
        "validation_status":   e.validation_status,
    }

# ── TF-IDF engine ──────────────────────────────────────────────────────────────

def _build_tfidf(docs: list[list[str]]) -> np.ndarray:
    N = len(docs)
    vocab: dict[str, int] = {}
    df: dict[str, int] = defaultdict(int)

    for doc in docs:
        for t in set(doc):
            if t not in vocab:
                vocab[t] = len(vocab)
            df[t] += 1

    V = len(vocab)
    matrix = np.zeros((N, V), dtype=np.float32)

    for i, doc in enumerate(docs):
        if not doc:
            continue
        tf = Counter(doc)
        doc_len = len(doc)
        for t, cnt in tf.items():
            j = vocab.get(t)
            if j is not None:
                idf = math.log((N + 1) / (df[t] + 1)) + 1.0  # smoothed IDF
                matrix[i, j] = (cnt / doc_len) * idf

    # L2-normalize each row
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return matrix / norms

# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class LinkCandidate:
    entity_a:      dict
    entity_b:      dict
    similarity:    float
    common_tokens: list[str]

# ── Public API ─────────────────────────────────────────────────────────────────

_MAX_RESULTS = 200   # cap on pairs returned to the UI

def find_candidates(
    db: Session,
    threshold: float = 0.82,
    limit: int = 500,
    dismissed_pairs: set[tuple[int, int]] | None = None,
) -> list[LinkCandidate]:
    """
    Scan up to `limit` entities, return pairs whose cosine similarity ≥ threshold.
    Already-dismissed pairs are excluded.
    """
    entities = db.query(models.RawEntity).limit(limit).all()
    if len(entities) < 2:
        return []

    tokenized = [_tokenize(_entity_text(e)) for e in entities]

    # Keep only entities that yield at least one token
    valid = [(e, tok) for e, tok in zip(entities, tokenized) if tok]
    if len(valid) < 2:
        return []

    valid_entities, valid_toks = zip(*valid)
    matrix = _build_tfidf(list(valid_toks))
    sim_matrix: np.ndarray = matrix @ matrix.T  # shape (N, N)

    dismissed = dismissed_pairs or set()
    candidates: list[LinkCandidate] = []
    n = len(valid_entities)

    for i in range(n):
        for j in range(i + 1, n):
            sim = float(sim_matrix[i, j])
            if sim < threshold:
                continue
            ea_id = valid_entities[i].id
            eb_id = valid_entities[j].id
            pair = (min(ea_id, eb_id), max(ea_id, eb_id))
            if pair in dismissed:
                continue
            common = sorted(set(valid_toks[i]) & set(valid_toks[j]))[:12]
            candidates.append(LinkCandidate(
                entity_a      = _entity_dict(valid_entities[i]),
                entity_b      = _entity_dict(valid_entities[j]),
                similarity    = round(sim, 4),
                common_tokens = common,
            ))

    candidates.sort(key=lambda c: c.similarity, reverse=True)
    return candidates[:_MAX_RESULTS]


_MERGE_FIELDS = [
    "entity_name", "brand_capitalized", "brand_lower", "model",
    "sku", "gtin", "barcode", "classification", "variant",
    "unit_of_measure", "entity_type", "creation_date",
    "enrichment_doi", "enrichment_source", "enrichment_concepts",
]


def merge_entities(
    db: Session,
    primary_id: int,
    secondary_ids: list[int],
    strategy: str = "keep_non_empty",
) -> models.RawEntity:
    """
    Merge secondary entities into primary according to `strategy`, then delete them.

    Strategies:
      keep_primary    — primary fields always win (ignore secondary values)
      keep_non_empty  — if primary field is null/empty, take from secondary (default)
      keep_longest    — keep whichever string value is longer
    """
    primary = db.query(models.RawEntity).filter(models.RawEntity.id == primary_id).first()
    if not primary:
        raise ValueError(f"Primary entity {primary_id} not found")

    secondaries = db.query(models.RawEntity).filter(
        models.RawEntity.id.in_(secondary_ids)
    ).all()

    if not secondaries:
        raise ValueError("No secondary entities found")

    for field_name in _MERGE_FIELDS:
        primary_val = getattr(primary, field_name, None)
        for sec in secondaries:
            sec_val = getattr(sec, field_name, None)
            if not sec_val:
                continue
            if strategy == "keep_primary":
                break                              # primary always wins — skip all secondaries
            elif strategy == "keep_non_empty":
                if not primary_val:
                    setattr(primary, field_name, sec_val)
                    primary_val = sec_val
            elif strategy == "keep_longest":
                if len(str(sec_val)) > len(str(primary_val or "")):
                    setattr(primary, field_name, sec_val)
                    primary_val = sec_val

    # Enrichment: take the maximum citation count
    max_citations = max(
        [primary.enrichment_citation_count or 0]
        + [s.enrichment_citation_count or 0 for s in secondaries]
    )
    primary.enrichment_citation_count = max_citations

    # Promote enrichment_status if any secondary is "completed"
    all_statuses = {primary.enrichment_status} | {s.enrichment_status for s in secondaries}
    if "completed" in all_statuses:
        primary.enrichment_status = "completed"

    # Remove secondaries
    for sec in secondaries:
        db.delete(sec)

    db.commit()
    db.refresh(primary)
    return primary
