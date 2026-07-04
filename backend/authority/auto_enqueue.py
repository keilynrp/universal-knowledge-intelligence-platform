"""Automatic authority-resolution enqueue on ingest (closing the loop, front B).

After the scientific-import graph is materialized, freshly created ``author`` /
``affiliation`` nodes carry only a *weak* name-derived ``canonical_id``. This
module enqueues async :class:`~backend.models.AuthorityResolveJob` rows so those
labels flow into the authority review queue automatically, instead of requiring
an operator to trigger a batch job by hand. The heavy lifting (external calls,
circuit breaking, caching) is done by the existing batch worker — here we only
insert de-duplicated job rows, so the ingest path stays non-blocking.

Opt-in: gated behind ``UKIP_AUTO_RESOLVE_ON_INGEST`` (default OFF) because it
drives outbound calls to external authority sources.
"""
from __future__ import annotations

import json
import logging
import os

from sqlalchemy.orm import Session

from backend import models
from backend.authority.batch_resolution import (
    VALUE_SOURCE_PUB_AFFILIATIONS,
    VALUE_SOURCE_PUB_AUTHORS,
    _distinct_values_from_publication_attrs,
)
from backend.tenant_access import persisted_org_id, scope_query_to_org

logger = logging.getLogger(__name__)

# (entity_type_filter on raw_entities  ->  authority entity_type to resolve as)
_ENTITY_TYPE_PLAN: tuple[tuple[str, str], ...] = (
    ("author", "person"),
    ("affiliation", "institution"),
)

# The raw_entities column whose distinct values are resolved.
_FIELD = "primary_label"

_DEFAULT_LIMIT = 500


def auto_resolve_enabled() -> bool:
    """Feature flag — defaults OFF. Set ``UKIP_AUTO_RESOLVE_ON_INGEST=1`` to enable."""
    return os.environ.get("UKIP_AUTO_RESOLVE_ON_INGEST", "0").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _has_open_job(db: Session, org_id, entity_type: str, field: str = _FIELD) -> bool:
    """True when a pending/processing job for this (field, entity_type) exists."""
    return (
        db.query(models.AuthorityResolveJob.id)
        .filter(
            models.AuthorityResolveJob.org_id == persisted_org_id(org_id),
            models.AuthorityResolveJob.field_name == field,
            models.AuthorityResolveJob.entity_type == entity_type,
            models.AuthorityResolveJob.status.in_(["pending", "processing"]),
        )
        .first()
        is not None
    )


def _has_unresolved_values(db: Session, org_id, entity_type_filter: str) -> bool:
    """True when at least one label of ``entity_type_filter`` lacks a
    pending/confirmed AuthorityRecord — i.e. there is real work to do.

    Cheap ``NOT EXISTS`` probe (LIMIT 1) that mirrors the worker's
    ``skip_existing`` logic, so we never enqueue a no-op job.
    """
    covered = (
        scope_query_to_org(
            db.query(models.AuthorityRecord.id), models.AuthorityRecord, org_id
        )
        .filter(
            models.AuthorityRecord.field_name == _FIELD,
            models.AuthorityRecord.original_value == models.RawEntity.primary_label,
            models.AuthorityRecord.status.in_(["pending", "confirmed"]),
        )
        .exists()
    )
    row = (
        scope_query_to_org(db.query(models.RawEntity.id), models.RawEntity, org_id)
        .filter(
            models.RawEntity.entity_type == entity_type_filter,
            models.RawEntity.primary_label.isnot(None),
            models.RawEntity.primary_label != "",
            ~covered,
        )
        .first()
    )
    return row is not None


def enqueue_entity_authority_jobs(
    db: Session, *, org_id, limit: int = _DEFAULT_LIMIT
) -> list[int]:
    """Enqueue de-duplicated authority jobs for author/affiliation labels.

    Returns the ids of jobs created (empty when disabled or all already queued).
    The caller owns the surrounding transaction: jobs are ``flush``-ed (so ids
    are assigned and visible for intra-call de-dup) but not committed here.
    Best-effort: never raises, so a failure here cannot break ingest.
    """
    if not auto_resolve_enabled():
        return []
    created: list[int] = []
    try:
        record_org_id = persisted_org_id(org_id)
        for entity_type_filter, resolve_as in _ENTITY_TYPE_PLAN:
            if _has_open_job(db, org_id, resolve_as):
                continue
            if not _has_unresolved_values(db, org_id, entity_type_filter):
                continue
            job = models.AuthorityResolveJob(
                org_id=record_org_id,
                field_name=_FIELD,
                entity_type=resolve_as,
                params_json=json.dumps({
                    "limit": limit,
                    "skip_existing": True,
                    "entity_type_filter": entity_type_filter,
                }),
                status="pending",
            )
            db.add(job)
            db.flush()
            created.append(job.id)
        if created:
            logger.info(
                "auto-enqueued %d authority job(s) for org=%s after ingest",
                len(created), record_org_id,
            )
        return created
    except Exception as exc:  # defensive: ingest must not break on enqueue
        logger.warning("auto-enqueue of authority jobs failed for org=%s: %s", org_id, exc)
        return []


# (value_source, field tag, authority entity_type) for the OpenAlex/api_import
# path, where authors/affiliations live inside publication attributes_json rather
# than as derived RawEntity nodes.
_PUBLICATION_PLAN: tuple[tuple[str, str, str], ...] = (
    (VALUE_SOURCE_PUB_AUTHORS, "author", "person"),
    (VALUE_SOURCE_PUB_AFFILIATIONS, "affiliation", "institution"),
)


def _uncovered_publication_values(db: Session, org_id, value_source: str, field: str) -> int:
    """Count distinct publication-attribute values lacking a pending/confirmed record."""
    values = _distinct_values_from_publication_attrs(db, org_id, value_source)
    if not values:
        return 0
    covered = {
        r.original_value
        for r in scope_query_to_org(
            db.query(models.AuthorityRecord.original_value), models.AuthorityRecord, org_id
        )
        .filter(
            models.AuthorityRecord.field_name == field,
            models.AuthorityRecord.status.in_(["pending", "confirmed"]),
        )
        .all()
    }
    return sum(1 for v in values if v not in covered)


def enqueue_publication_authority_jobs(
    db: Session, *, org_id, limit: int = _DEFAULT_LIMIT
) -> list[int]:
    """Enqueue authority jobs for authors/affiliations held in publication attrs.

    This is the OpenAlex/api_import counterpart to
    :func:`enqueue_entity_authority_jobs`: it resolves the author/affiliation
    names stored inside publication ``attributes_json`` (no derived nodes exist
    for that path). De-duplicated, guard-gated, caller owns the transaction,
    never raises.
    """
    if not auto_resolve_enabled():
        return []
    created: list[int] = []
    try:
        record_org_id = persisted_org_id(org_id)
        for value_source, field, resolve_as in _PUBLICATION_PLAN:
            if _has_open_job(db, org_id, resolve_as, field=field):
                continue
            if _uncovered_publication_values(db, org_id, value_source, field) == 0:
                continue
            job = models.AuthorityResolveJob(
                org_id=record_org_id,
                field_name=field,
                entity_type=resolve_as,
                params_json=json.dumps({
                    "limit": limit,
                    "skip_existing": True,
                    "value_source": value_source,
                }),
                status="pending",
            )
            db.add(job)
            db.flush()
            created.append(job.id)
        if created:
            logger.info(
                "auto-enqueued %d publication authority job(s) for org=%s",
                len(created), record_org_id,
            )
        return created
    except Exception as exc:  # defensive: ingest must not break on enqueue
        logger.warning(
            "auto-enqueue of publication authority jobs failed for org=%s: %s", org_id, exc
        )
        return []
