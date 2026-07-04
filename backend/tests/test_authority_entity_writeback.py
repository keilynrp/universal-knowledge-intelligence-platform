"""Authority → entity identity write-back (closing the loop).

Confirming an ``AuthorityRecord`` should promote the *weak* name-derived
``canonical_id`` of matching ``author`` / ``affiliation`` graph entities to the
resolved strong external identity — without ever clobbering an already-strong
identifier or a non-matching entity.
"""
from __future__ import annotations

import json

import pytest

from backend import models
from backend.authority import entity_writeback as wb


# ── helpers ───────────────────────────────────────────────────────────────────

def _entity(db, *, label, canonical_id, entity_type="author", org_id=None):
    ent = models.RawEntity(
        org_id=org_id,
        domain="science",
        entity_type=entity_type,
        primary_label=label,
        canonical_id=canonical_id,
        attributes_json=json.dumps({"derived": True, "derived_kind": entity_type}),
        validation_status="derived",
        enrichment_status="derived",
        source="graph_materializer",
    )
    db.add(ent)
    db.flush()
    return ent


def _record(db, *, original_value, source="orcid", authority_id="0000-0002-1825-0097",
            canonical_label=None, uri="https://orcid.org/0000-0002-1825-0097",
            org_id=None, status="pending"):
    rec = models.AuthorityRecord(
        org_id=org_id,
        field_name="author_name",
        original_value=original_value,
        authority_source=source,
        authority_id=authority_id,
        canonical_label=canonical_label or original_value,
        aliases="[]",
        description="Authority profile",
        confidence=0.97,
        uri=uri,
        status=status,
        resolution_status="exact_match",
        score_breakdown="{}",
        evidence="[]",
        merged_sources="[]",
    )
    db.add(rec)
    db.flush()
    return rec


# ── pure helpers ──────────────────────────────────────────────────────────────

def test_build_authority_canonical_id():
    assert wb.build_authority_canonical_id("orcid", "0000-1") == "orcid:0000-1"
    assert wb.build_authority_canonical_id("WIKIDATA", "Q42") == "wikidata:Q42"
    assert wb.build_authority_canonical_id("internal_nil", "NIL") is None
    assert wb.build_authority_canonical_id("orcid", "NIL") is None
    assert wb.build_authority_canonical_id("", "x") is None
    assert wb.build_authority_canonical_id("orcid", "") is None


def test_is_weak_classification():
    assert wb._is_weak("author:ada-lovelace") is True
    assert wb._is_weak("affiliation:open-lab") is True
    assert wb._is_weak(None) is True
    assert wb._is_weak("") is True
    assert wb._is_weak("orcid:0000-1") is False
    assert wb._is_weak("wikidata:Q42") is False
    assert wb._is_weak("doi:10.1/x") is False


# ── write-back behavior ───────────────────────────────────────────────────────

def test_confirm_promotes_weak_author_entity(db_session):
    ent = _entity(db_session, label="Ada Lovelace", canonical_id="author:ada-lovelace")
    rec = _record(db_session, original_value="Ada Lovelace")

    n = wb.promote_confirmed_identity(db_session, rec, org_id=rec.org_id)
    db_session.flush()

    assert n == 1
    db_session.refresh(ent)
    assert ent.canonical_id == "orcid:0000-2-1825-0097" or ent.canonical_id == "orcid:0000-0002-1825-0097"
    attrs = json.loads(ent.attributes_json)
    assert attrs["authority"]["source"] == "orcid"
    assert attrs["authority"]["authority_record_id"] == rec.id
    assert attrs["authority"]["uri"] == rec.uri
    # original derived metadata preserved
    assert attrs["derived"] is True


def test_strong_id_is_never_overwritten(db_session):
    ent = _entity(db_session, label="Ada Lovelace", canonical_id="orcid:0000-9999-0000-0001")
    rec = _record(db_session, original_value="Ada Lovelace")

    n = wb.promote_confirmed_identity(db_session, rec, org_id=rec.org_id)

    assert n == 0
    db_session.refresh(ent)
    assert ent.canonical_id == "orcid:0000-9999-0000-0001"


def test_non_matching_label_untouched(db_session):
    ent = _entity(db_session, label="Grace Hopper", canonical_id="author:grace-hopper")
    rec = _record(db_session, original_value="Ada Lovelace")

    n = wb.promote_confirmed_identity(db_session, rec, org_id=rec.org_id)

    assert n == 0
    db_session.refresh(ent)
    assert ent.canonical_id == "author:grace-hopper"


def test_nil_record_is_noop(db_session):
    ent = _entity(db_session, label="Ada Lovelace", canonical_id="author:ada-lovelace")
    rec = _record(db_session, original_value="Ada Lovelace",
                  source="internal_nil", authority_id="NIL", uri=None)

    n = wb.promote_confirmed_identity(db_session, rec, org_id=rec.org_id)

    assert n == 0
    db_session.refresh(ent)
    assert ent.canonical_id == "author:ada-lovelace"


def test_promotion_is_idempotent(db_session):
    ent = _entity(db_session, label="Ada Lovelace", canonical_id="author:ada-lovelace")
    rec = _record(db_session, original_value="Ada Lovelace", authority_id="A1", source="openalex")

    first = wb.promote_confirmed_identity(db_session, rec, org_id=rec.org_id)
    db_session.flush()
    second = wb.promote_confirmed_identity(db_session, rec, org_id=rec.org_id)

    assert first == 1
    assert second == 0
    db_session.refresh(ent)
    assert ent.canonical_id == "openalex:A1"


def test_affiliation_entity_is_eligible(db_session):
    ent = _entity(db_session, label="Open Science Lab",
                  canonical_id="affiliation:open-science-lab", entity_type="affiliation")
    rec = _record(db_session, original_value="Open Science Lab",
                  source="wikidata", authority_id="Q123", uri="https://www.wikidata.org/wiki/Q123")

    n = wb.promote_confirmed_identity(db_session, rec, org_id=rec.org_id)
    db_session.flush()

    assert n == 1
    db_session.refresh(ent)
    assert ent.canonical_id == "wikidata:Q123"


def test_work_entity_type_is_ignored(db_session):
    # A 'work' entity sharing the label must not be touched (only author/affiliation).
    ent = _entity(db_session, label="Ada Lovelace", canonical_id="author:ada-lovelace",
                  entity_type="work")
    rec = _record(db_session, original_value="Ada Lovelace")

    n = wb.promote_confirmed_identity(db_session, rec, org_id=rec.org_id)

    assert n == 0
    db_session.refresh(ent)
    assert ent.canonical_id == "author:ada-lovelace"


def test_confirm_endpoint_promotes_and_reports_count(client, editor_headers, session_factory):
    """End-to-end: POST /authority/records/{id}/confirm promotes the entity."""
    with session_factory() as db:
        ent = models.RawEntity(
            org_id=None, domain="science", entity_type="author",
            primary_label="Marie Curie", canonical_id="author:marie-curie",
            attributes_json=json.dumps({"derived": True}),
            validation_status="derived", enrichment_status="derived",
            source="graph_materializer",
        )
        db.add(ent)
        rec = models.AuthorityRecord(
            org_id=None, field_name="author_name", original_value="Marie Curie",
            authority_source="wikidata", authority_id="Q7186",
            canonical_label="Marie Curie", aliases="[]", description="",
            confidence=0.95, uri="https://www.wikidata.org/wiki/Q7186",
            status="pending", resolution_status="exact_match",
            score_breakdown="{}", evidence="[]", merged_sources="[]",
        )
        db.add(rec)
        db.commit()
        ent_id, rec_id = ent.id, rec.id

    resp = client.post(f"/authority/records/{rec_id}/confirm", headers=editor_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["entities_updated"] == 1

    with session_factory() as db:
        refreshed = db.query(models.RawEntity).filter(models.RawEntity.id == ent_id).first()
        assert refreshed.canonical_id == "wikidata:Q7186"


def test_disabled_flag_skips_writeback(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_AUTHORITY_WRITEBACK", "0")
    ent = _entity(db_session, label="Ada Lovelace", canonical_id="author:ada-lovelace")
    rec = _record(db_session, original_value="Ada Lovelace")

    n = wb.promote_confirmed_identity(db_session, rec, org_id=rec.org_id)

    assert n == 0
    db_session.refresh(ent)
    assert ent.canonical_id == "author:ada-lovelace"
