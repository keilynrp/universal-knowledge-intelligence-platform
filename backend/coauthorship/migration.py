"""One-shot conversion of legacy entity_relationships(CO_AUTHOR) -> V2 tables.

Strategy: walk ``raw_entities`` with author payloads (the source of truth), NOT
the lossy ``notes`` field. The legacy table is consulted only for the audit
count. The F3 worker write path (``write_coauthor_artifacts``) is reused so the
migration produces exactly the shape the runtime would — a single code path.

Idempotent: re-running produces identical row counts (publications keyed by PK,
contributions deduplicated, edge weight contributed exactly once per triple).
"""
from __future__ import annotations

import logging

from backend import models
from backend.analyzers.coauthorship import authors_from_attrs
from backend.coauthorship.identity import get_or_create_author, name_key

logger = logging.getLogger(__name__)


def migrate_coauthor_graph(db, *, dry_run: bool = True, domain: str | None = None) -> dict:
    """Convert legacy coauthorship data into the V2 tables.

    Args:
        dry_run: when True, scan + report counts without any writes.
        domain: restrict to a single domain_id; None scans all domains.
    """
    stats = {
        "legacy_edges_found": 0,
        "entities_scanned": 0,
        "entities_with_authors": 0,
        "authors_created": 0,
        "publications_created": 0,
        "edges_created": 0,
        "self_pairs_skipped": 0,
    }

    # 1. Count legacy CO_AUTHOR edges for the audit trail.
    legacy_q = db.query(models.EntityRelationship).filter_by(relation_type="CO_AUTHOR")
    if domain:
        legacy_q = legacy_q.join(
            models.RawEntity, models.RawEntity.id == models.EntityRelationship.source_id
        ).filter(models.RawEntity.domain == domain)
    stats["legacy_edges_found"] = legacy_q.count()

    # 2. Walk eligible entities. Materialize up-front so per-entity commits don't
    #    invalidate a streaming cursor (the classic yield_per + mid-loop-commit
    #    footgun on PostgreSQL). UKIP corpora fit comfortably in memory.
    ent_q = db.query(models.RawEntity)
    if domain:
        ent_q = ent_q.filter(models.RawEntity.domain == domain)
    entities = ent_q.all()

    initial_author_count = db.query(models.Author).count()

    from backend.enrichment_worker import write_coauthor_artifacts

    for ent in entities:
        stats["entities_scanned"] += 1
        authors = authors_from_attrs(ent.attributes_json)
        if len(authors) < 2:
            continue
        stats["entities_with_authors"] += 1
        if dry_run:
            continue

        # Detect self-pairs: multiple surface forms collapsing to one name_key
        # (e.g. "Smith, John" + "John Smith"). These are one person, not a real
        # coauthor edge — record the publication(s) but skip the edge path.
        keys = {name_key(a) for a in authors if name_key(a)}
        if len(keys) < 2:
            stats["self_pairs_skipped"] += 1
            for name in authors:
                a = get_or_create_author(db, name)
                exists = (
                    db.query(models.AuthorPublication)
                    .filter_by(author_id=a.id, entity_id=ent.id)
                    .first()
                )
                if not exists:
                    db.add(models.AuthorPublication(
                        author_id=a.id, entity_id=ent.id,
                        org_id=ent.org_id if ent.org_id is not None else 0,
                        domain_id=ent.domain or "default", position=1))
            db.commit()
            continue

        # force=True: orchestrate writes regardless of the runtime flag.
        write_coauthor_artifacts(db, ent, force=True)
        db.commit()  # migration owns the transaction boundary (see F3.3 docstring)

    if not dry_run:
        stats["authors_created"] = db.query(models.Author).count() - initial_author_count
        stats["publications_created"] = db.query(models.AuthorPublication).count()
        stats["edges_created"] = db.query(models.CoauthorEdge).count()
        # Populate the review queue with ambiguous (last+initial) pairs so the
        # hybrid-identity workflow is live immediately after migration.
        from backend.coauthorship.suggestions import generate_merge_suggestions

        sug = generate_merge_suggestions(db)
        stats["suggestions_created"] = sug["suggestions_created"]

    logger.info(
        "migrate_coauthor_graph dry_run=%s domain=%s stats=%s", dry_run, domain, stats
    )
    return stats
