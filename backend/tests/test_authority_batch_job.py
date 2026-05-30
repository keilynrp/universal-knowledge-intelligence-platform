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
