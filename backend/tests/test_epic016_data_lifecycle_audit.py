"""EPIC-016 US-070 — lifecycle audit foundation.

Pins that lifecycle events are recorded, completed with evidence, persisted
legacy-global correctly, and isolated per tenant.
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest

from backend import models
from backend.services.data_lifecycle import complete_event, record_event
from backend.tenant_access import LEGACY_GLOBAL_ORG_ID, scope_query_to_org


def _org(db) -> tuple[int, int]:
    suffix = uuid4().hex[:8]
    owner = models.User(
        username=f"owner_{suffix}", password_hash="x", role="admin", is_active=True
    )
    db.add(owner)
    db.flush()
    org = models.Organization(
        name=f"Org {suffix}", slug=f"org-{suffix}", owner_id=owner.id,
        plan="pro", is_active=True,
    )
    db.add(org)
    db.flush()
    return org.id, owner.id


def test_record_event_persists_scoped(db_session):
    org_id, owner_id = _org(db_session)
    db_session.commit()

    event = record_event(
        db_session,
        org_id=org_id,
        action="export",
        subject_type="org",
        subject_ref=str(org_id),
        requested_by=owner_id,
        scope={"include": "all"},
    )

    assert event.id is not None
    assert event.org_id == org_id
    assert event.action == "export"
    assert event.status == "started"
    assert json.loads(event.scope_json) == {"include": "all"}
    assert event.created_at is not None
    assert event.completed_at is None


def test_complete_event_attaches_evidence(db_session):
    org_id, owner_id = _org(db_session)
    db_session.commit()

    event = record_event(
        db_session, org_id=org_id, action="deletion", subject_type="user",
        subject_ref="42", requested_by=owner_id,
    )
    complete_event(db_session, event, status="completed", evidence={"raw_entities": 7})

    assert event.status == "completed"
    assert json.loads(event.evidence_json) == {"raw_entities": 7}
    assert event.completed_at is not None


def test_legacy_global_persists_null(db_session):
    # LEGACY_GLOBAL_ORG_ID (-1) must persist as NULL (consistent with tenant_access).
    event = record_event(
        db_session, org_id=LEGACY_GLOBAL_ORG_ID, action="purge",
        subject_type="entity_owner", subject_ref="legacy", requested_by=None,
    )
    assert event.org_id is None


def test_events_scoped_by_org(db_session):
    org_a, owner_a = _org(db_session)
    org_b, owner_b = _org(db_session)
    db_session.commit()

    record_event(db_session, org_id=org_a, action="export", subject_type="org",
                 subject_ref=str(org_a), requested_by=owner_a)
    record_event(db_session, org_id=org_b, action="export", subject_type="org",
                 subject_ref=str(org_b), requested_by=owner_b)

    a_events = scope_query_to_org(
        db_session.query(models.DataLifecycleEvent), models.DataLifecycleEvent, org_a
    ).all()
    assert len(a_events) == 1
    assert a_events[0].org_id == org_a


def test_invalid_action_rejected(db_session):
    with pytest.raises(ValueError):
        record_event(db_session, org_id=None, action="bogus", subject_type="org",
                     subject_ref="x", requested_by=None)
