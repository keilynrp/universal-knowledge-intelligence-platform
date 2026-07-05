"""Tests for async authority batch resolution jobs (Phase 1, Task 3).

The batch endpoint enqueues an AuthorityResolveJob and returns immediately; a
background worker drains the queue. A ``sync=true`` flag preserves the legacy
synchronous behavior for callers that need inline results.
"""
from __future__ import annotations

from unittest.mock import patch

from backend import models
from backend.authority.base import AuthorityCandidate as _Candidate

_MOCK_CANDIDATES = [
    _Candidate(
        authority_source="wikidata",
        authority_id="Q123",
        canonical_label="Microsoft",
        aliases=["MSFT"],
        description="Technology company",
        confidence=0.92,
        uri="https://www.wikidata.org/wiki/Q123",
        resolution_status="exact_match",
        score_breakdown={},
        evidence=[],
        merged_sources=[],
    ),
]
_PATCH = "backend.routers.authority._authority_resolve_all"


def _payload(**kw):
    defaults = {"field_name": "primary_label", "entity_type": "general", "limit": 5}
    defaults.update(kw)
    return defaults


def test_batch_enqueue_returns_job_pending(client, editor_headers):
    res = client.post("/authority/resolve/batch", json=_payload(), headers=editor_headers)
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "pending"
    assert "job_id" in body


def test_job_status_endpoint(client, editor_headers):
    job_id = client.post(
        "/authority/resolve/batch", json=_payload(), headers=editor_headers
    ).json()["job_id"]
    res = client.get(f"/authority/jobs/{job_id}", headers=editor_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] in {"pending", "processing", "done", "failed"}
    assert body["job_id"] == job_id
    assert "processed" in body
    assert "total" in body


def test_job_status_404_for_unknown_id(client, editor_headers):
    res = client.get("/authority/jobs/99999999", headers=editor_headers)
    assert res.status_code == 404


def test_batch_value_source_publication_authors_enqueues_with_param(
    client, editor_headers, session_factory
):
    import json as _json

    # `field_name` is only a record tag when value_source is set (not a column),
    # so a non-column name like "author" is accepted here.
    res = client.post(
        "/authority/resolve/batch",
        json={"field_name": "author", "entity_type": "person", "limit": 5,
              "value_source": "publication_authors"},
        headers=editor_headers,
    )
    assert res.status_code == 201, res.text
    job_id = res.json()["job_id"]
    with session_factory() as db:
        job = db.query(models.AuthorityResolveJob).filter_by(id=job_id).one()
        assert job.field_name == "author"
        assert _json.loads(job.params_json)["value_source"] == "publication_authors"


def test_batch_invalid_value_source_is_422(client, editor_headers):
    res = client.post(
        "/authority/resolve/batch",
        json={"field_name": "author", "entity_type": "person",
              "value_source": "not_a_real_source"},
        headers=editor_headers,
    )
    assert res.status_code == 422


def test_purge_deletes_pending_not_confirmed(client, auth_headers, session_factory):
    with session_factory() as db:
        def _rec(val, status):
            return models.AuthorityRecord(
                org_id=None, field_name="author", original_value=val,
                authority_source="orcid", authority_id=f"A-{val}", canonical_label=val,
                aliases="[]", description="", confidence=0.5, uri=None, status=status,
                resolution_status="ambiguous", score_breakdown="{}", evidence="[]",
                merged_sources="[]",
            )
        db.add_all([_rec("p1", "pending"), _rec("p2", "pending"), _rec("c1", "confirmed")])
        db.commit()

    # super_admin (auth_headers) required — purge is admin-only.
    res = client.post("/authority/records/purge?field_name=author&status=pending",
                      headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["deleted"] >= 2

    with session_factory() as db:
        remaining = {
            r.original_value
            for r in db.query(models.AuthorityRecord)
            .filter(models.AuthorityRecord.field_name == "author").all()
        }
    assert "c1" in remaining          # confirmed untouched
    assert "p1" not in remaining and "p2" not in remaining  # pending purged


def test_purge_requires_admin(client, editor_headers):
    # editor is below admin → forbidden
    res = client.post("/authority/records/purge?status=pending", headers=editor_headers)
    assert res.status_code in (401, 403)


def _author_rec(val, conf, status="pending", evidence="[]", source="openalex", aid="A1"):
    return models.AuthorityRecord(
        org_id=None, field_name="author", original_value=val,
        authority_source=source, authority_id=aid, canonical_label=val,
        aliases="[]", description="", confidence=conf, uri=None, status=status,
        resolution_status="exact_match", score_breakdown="{}",
        evidence=evidence, merged_sources="[]",
    )


def test_auto_confirm_groups_by_value_and_confirms_best(client, editor_headers, session_factory):
    with session_factory() as db:
        # Author "Ada" has 3 candidates; best (orcid 1.0) should win, others rejected.
        db.add_all([
            _author_rec("Ada Lovelace", 1.0, evidence='["orcid_hint_matched"]', source="orcid", aid="0000-1"),
            _author_rec("Ada Lovelace", 0.6, aid="A2"),
            _author_rec("Ada Lovelace", 0.5, aid="A3"),
            # Author "Bob" only has a weak candidate → left pending.
            _author_rec("Bob Weak", 0.6, aid="B1"),
        ])
        db.commit()

    res = client.post("/authority/records/auto-confirm?field_name=author&min_confidence=0.95",
                      headers=editor_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["confirmed"] == 1  # only Ada's best
    assert body["rejected"] == 2   # Ada's two losers

    with session_factory() as db:
        rows = {(r.original_value, r.authority_id): r.status
                for r in db.query(models.AuthorityRecord)
                .filter(models.AuthorityRecord.field_name == "author").all()}
    assert rows[("Ada Lovelace", "0000-1")] == "confirmed"
    assert rows[("Ada Lovelace", "A2")] == "rejected"
    assert rows[("Ada Lovelace", "A3")] == "rejected"
    assert rows[("Bob Weak", "B1")] == "pending"   # below threshold, no orcid → untouched


def test_auto_confirm_orcid_match_below_threshold_still_confirms(client, editor_headers, session_factory):
    with session_factory() as db:
        # confidence 0.65 but orcid matched → confirmable regardless of threshold.
        db.add(_author_rec("Curie", 0.65, evidence='["orcid_hint_matched"]', source="orcid", aid="0000-9"))
        db.commit()
    res = client.post("/authority/records/auto-confirm?field_name=author&min_confidence=0.95&reject_losers=false",
                      headers=editor_headers)
    assert res.json()["confirmed"] == 1


def test_grouped_records_one_row_per_value(client, editor_headers, session_factory):
    with session_factory() as db:
        db.add_all([
            _author_rec("Grace Hopper", 1.0, evidence='["orcid_hint_matched"]', source="orcid", aid="0000-2"),
            _author_rec("Grace Hopper", 0.6, aid="G2"),
            _author_rec("Alan Turing", 0.62, aid="T1"),
        ])
        db.commit()

    res = client.get("/authority/records/grouped?field_name=author", headers=editor_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    by_val = {g["original_value"]: g for g in body["groups"]}
    # Grace has 2 candidates, top is the orcid 1.0 and is auto_confirmable.
    assert by_val["Grace Hopper"]["candidate_count"] == 2
    assert by_val["Grace Hopper"]["auto_confirmable"] is True
    assert by_val["Grace Hopper"]["best"]["authority_id"] == "0000-2"
    # Ordered by best_confidence desc → Grace (1.0) before Alan (0.62).
    assert body["groups"][0]["original_value"] == "Grace Hopper"
    assert by_val["Alan Turing"]["auto_confirmable"] is False


def test_sync_flag_preserves_legacy_behavior(client, editor_headers, db_session):
    db_session.add(models.RawEntity(primary_label="Microsoft"))
    db_session.commit()
    with patch(_PATCH, return_value=_MOCK_CANDIDATES):
        res = client.post(
            "/authority/resolve/batch?sync=true",
            json=_payload(limit=1),
            headers=editor_headers,
        )
    assert res.status_code == 201
    assert "records" in res.json()  # legacy synchronous shape
