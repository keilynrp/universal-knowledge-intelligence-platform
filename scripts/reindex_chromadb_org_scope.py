"""
One-time (post-deploy) re-index of the ChromaDB catalog so every document
carries the ``org_id`` metadata introduced by issue #32.

Why this is required
--------------------
Before #32, indexed ChromaDB documents had no ``org_id`` in their metadata.
After #32 the retrieval path filters by ``org_id`` (``where`` clause), so a
document missing that key is *excluded* from any org-scoped query. Until the
catalog is re-indexed, RAG / agentic-chat returns empty results for every
org-scoped user. Re-indexing upserts each enriched entity with the new
metadata (org_id is read from ``entity.org_id``; legacy-global entities are
stored with the -1 sentinel).

Idempotent: ``index_entity`` upserts by ``doc_id = entity-<id>``, so running
this repeatedly only refreshes existing documents.

Usage:
    python -m scripts.reindex_chromadb_org_scope [--dry-run] [--wipe] [--batch-size 200]

Requirements:
    - DATABASE_URL (or POSTGRES_* env) pointing at the target DB
    - An ACTIVE AI integration configured (provides the embedding adapter)
    - chromadb installed and CHROMADB_PATH writable
"""
import argparse
import logging
import sys
from collections import Counter

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("reindex_chromadb")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-index ChromaDB so documents carry org_id metadata (issue #32)."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Count entities that would be indexed; do not touch ChromaDB.")
    parser.add_argument("--wipe", action="store_true",
                        help="Delete the entire collection before re-indexing (removes stale docs).")
    parser.add_argument("--batch-size", type=int, default=200,
                        help="Log progress every N entities (default: 200).")
    args = parser.parse_args()

    # Import after arg parsing so --help works without env/deps.
    from backend.database import SessionLocal
    from backend.routers.deps import _get_active_integration
    from backend.analytics import rag_engine
    from backend.analytics.vector_store import VectorStoreService
    from backend import models

    db = SessionLocal()
    try:
        entities = (
            db.query(models.RawEntity)
            .filter(models.RawEntity.enrichment_status.in_(rag_engine.ENRICHED_STATUSES))
            .all()
        )
        total = len(entities)
        org_dist = Counter(
            (e.org_id if e.org_id is not None else "legacy_global") for e in entities
        )
        logger.info("Enriched entities eligible for indexing: %d", total)
        logger.info("Org distribution: %s", dict(org_dist))

        if args.dry_run:
            logger.info("--dry-run: no changes made.")
            return 0

        integration = _get_active_integration(db)
        if not integration:
            logger.error(
                "No ACTIVE AI integration configured. Activate a provider "
                "(Integrations -> AI Language Models) before re-indexing."
            )
            return 2

        if args.wipe:
            logger.warning("--wipe: clearing the entire ChromaDB collection first.")
            VectorStoreService.clear_all()

        indexed = skipped = errors = 0
        for i, entity in enumerate(entities, start=1):
            result = rag_engine.index_entity(entity, integration)
            status = result.get("status")
            if status == "indexed":
                indexed += 1
            elif status == "skipped":
                skipped += 1
            else:
                errors += 1
                logger.warning("entity %s: %s", entity.id, result.get("message"))
            if i % args.batch_size == 0:
                logger.info("progress: %d/%d (indexed=%d skipped=%d errors=%d)",
                            i, total, indexed, skipped, errors)

        logger.info("DONE. indexed=%d skipped=%d errors=%d (total=%d)",
                    indexed, skipped, errors, total)
        return 1 if errors and not indexed else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
