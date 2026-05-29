"""Merge-suggestion producer.

Scans existing authors, groups them by the family-name component of their
name_key, and runs the deterministic classifier on each candidate pair. Pairs
the classifier rates 'ambiguous' (same family name + initial-vs-full first name,
e.g. ``smith_j`` vs ``smith_john``) are enqueued into ``author_merge_suggestions``
for human review — never auto-merged. This is the producer that fills the review
queue the classifier (F2.2) and the API/UI (F4a.2/F4b.3/F4c.3) consume.

Idempotent: a pair already present in author_merge_suggestions (any status) is
skipped, so re-running never duplicates and never resurrects a rejected pair.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from itertools import combinations

from backend import models
from backend.coauthorship.identity import classify_merge

logger = logging.getLogger(__name__)

# Skip pathologically large family-name groups (e.g. a parsing artifact bucket)
# so one bad group can't blow the scan up into millions of pair comparisons.
_MAX_GROUP_SIZE = 200


def _family_name(name_key: str) -> str:
    return name_key.split("_", 1)[0] if "_" in name_key else name_key


def generate_merge_suggestions(db, *, max_group_size: int = _MAX_GROUP_SIZE) -> dict:
    """Enqueue 'ambiguous' author pairs for review. Returns scan counters."""
    stats = {
        "authors_scanned": 0,
        "groups_compared": 0,
        "groups_skipped_too_large": 0,
        "pairs_compared": 0,
        "suggestions_created": 0,
    }

    authors = db.query(models.Author).all()
    stats["authors_scanned"] = len(authors)

    groups: dict[str, list] = defaultdict(list)
    for a in authors:
        groups[_family_name(a.name_key)].append(a)

    # Pairs already recorded (any status) — never duplicate or revive rejections.
    existing: set[tuple[int, int]] = set()
    for a_id, b_id in db.query(
        models.AuthorMergeSuggestion.author_a_id, models.AuthorMergeSuggestion.author_b_id
    ).all():
        existing.add((min(a_id, b_id), max(a_id, b_id)))

    for members in groups.values():
        if len(members) < 2:
            continue
        if len(members) > max_group_size:
            stats["groups_skipped_too_large"] += 1
            continue
        stats["groups_compared"] += 1
        for a, b in combinations(members, 2):
            stats["pairs_compared"] += 1
            key = (min(a.id, b.id), max(a.id, b.id))
            if key in existing:
                continue
            decision = classify_merge(db, a, b)
            if decision.tier == "ambiguous":
                db.add(models.AuthorMergeSuggestion(
                    author_a_id=key[0],
                    author_b_id=key[1],
                    reason=decision.reason,
                    evidence=json.dumps(decision.evidence, ensure_ascii=False),
                    status="pending",
                ))
                existing.add(key)
                stats["suggestions_created"] += 1

    db.commit()
    logger.info("generate_merge_suggestions stats=%s", stats)
    return stats
