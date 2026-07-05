"""Phase 3 — write a confirmed author identity into publication attributes.

On confirm, the resolved identity is stamped into each matching publication's
`attrs["canonical_authors"]` (keyed by original author name), non-destructively.
"""
from __future__ import annotations

import json

from backend import models
from backend.authority import publication_writeback as pw


def _publication(db, *, title, author_names, org_id=None):
    attrs = {
        "author_affiliations": [{"author_name": n, "institutions": []} for n in author_names],
    }
    ent = models.RawEntity(
        org_id=org_id, domain="science", entity_type="publication",
        primary_label=title, canonical_id=f"doi:{title}",
        attributes_json=json.dumps(attrs), validation_status="pending",
        enrichment_status="completed", source="openalex",
    )
    db.add(ent)
    db.flush()
    return ent


def _record(db, *, value, source="orcid", authority_id="0000-0002-1825-0097",
            field_name="author", org_id=None):
    rec = models.AuthorityRecord(
        org_id=org_id, field_name=field_name, original_value=value,
        authority_source=source, authority_id=authority_id, canonical_label=value,
        aliases="[]", description="", confidence=1.0,
        uri=f"https://orcid.org/{authority_id}", status="confirmed",
        resolution_status="exact_match", score_breakdown="{}", evidence="[]",
        merged_sources="[]",
    )
    db.add(rec)
    db.flush()
    return rec


def test_stamps_identity_into_matching_publications(db_session):
    p1 = _publication(db_session, title="P1", author_names=["Ada Lovelace", "Charles Babbage"])
    p2 = _publication(db_session, title="P2", author_names=["Ada Lovelace"])
    _publication(db_session, title="P3", author_names=["Grace Hopper"])  # no match
    rec = _record(db_session, value="Ada Lovelace")
    db_session.flush()

    n = pw.promote_confirmed_author_to_publications(db_session, rec, org_id=rec.org_id)
    db_session.flush()

    assert n == 2  # p1 + p2
    for p in (p1, p2):
        db_session.refresh(p)
        ca = json.loads(p.attributes_json)["canonical_authors"]
        assert ca["Ada Lovelace"]["source"] == "orcid"
        assert ca["Ada Lovelace"]["authority_id"] == "0000-0002-1825-0097"
        assert ca["Ada Lovelace"]["canonical_id"] == "orcid:0000-0002-1825-0097"


def test_non_destructive_merge_multiple_authors(db_session):
    p = _publication(db_session, title="P", author_names=["Ada Lovelace", "Charles Babbage"])
    r1 = _record(db_session, value="Ada Lovelace", authority_id="0000-1")
    r2 = _record(db_session, value="Charles Babbage", authority_id="0000-2")
    db_session.flush()

    pw.promote_confirmed_author_to_publications(db_session, r1, org_id=None)
    db_session.flush()
    pw.promote_confirmed_author_to_publications(db_session, r2, org_id=None)
    db_session.flush()

    db_session.refresh(p)
    ca = json.loads(p.attributes_json)["canonical_authors"]
    assert set(ca) == {"Ada Lovelace", "Charles Babbage"}  # both preserved
    # original author_affiliations untouched
    assert len(json.loads(p.attributes_json)["author_affiliations"]) == 2


def test_only_author_field_and_real_identity(db_session):
    p = _publication(db_session, title="P", author_names=["Ada Lovelace"])
    # affiliation-field record → ignored
    aff = _record(db_session, value="Ada Lovelace", field_name="affiliation")
    n1 = pw.promote_confirmed_author_to_publications(db_session, aff, org_id=None)
    # NIL record → ignored
    nil = _record(db_session, value="Ada Lovelace", source="internal_nil", authority_id="NIL")
    n2 = pw.promote_confirmed_author_to_publications(db_session, nil, org_id=None)

    assert n1 == 0 and n2 == 0
    db_session.refresh(p)
    assert "canonical_authors" not in json.loads(p.attributes_json)


def test_idempotent(db_session):
    p = _publication(db_session, title="P", author_names=["Ada Lovelace"])
    rec = _record(db_session, value="Ada Lovelace")
    db_session.flush()
    first = pw.promote_confirmed_author_to_publications(db_session, rec, org_id=None)
    db_session.flush()
    second = pw.promote_confirmed_author_to_publications(db_session, rec, org_id=None)
    assert first == 1
    assert second == 0  # same entry → no-op


def test_disabled_flag_skips(db_session, monkeypatch):
    monkeypatch.setenv("UKIP_AUTHORITY_WRITEBACK", "0")
    p = _publication(db_session, title="P", author_names=["Ada Lovelace"])
    rec = _record(db_session, value="Ada Lovelace")
    n = pw.promote_confirmed_author_to_publications(db_session, rec, org_id=None)
    assert n == 0


def test_reapply_backfill_endpoint(client, auth_headers, session_factory):
    with session_factory() as db:
        ent = models.RawEntity(
            org_id=None, domain="science", entity_type="publication",
            primary_label="BF", canonical_id="doi:bf",
            attributes_json=json.dumps({"author_affiliations": [{"author_name": "Marie Curie"}]}),
            validation_status="pending", enrichment_status="completed", source="openalex",
        )
        db.add(ent)
        db.add(models.AuthorityRecord(
            org_id=None, field_name="author", original_value="Marie Curie",
            authority_source="wikidata", authority_id="Q7186", canonical_label="Marie Curie",
            aliases="[]", description="", confidence=1.0, uri=None, status="confirmed",
            resolution_status="exact_match", score_breakdown="{}", evidence="[]", merged_sources="[]",
        ))
        db.commit()
        ent_id = ent.id

    res = client.post("/authority/records/reapply-publication-writeback?field_name=author",
                      headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["publications_updated"] >= 1

    with session_factory() as db:
        p = db.query(models.RawEntity).filter(models.RawEntity.id == ent_id).first()
        ca = json.loads(p.attributes_json)["canonical_authors"]
        assert ca["Marie Curie"]["authority_id"] == "Q7186"
