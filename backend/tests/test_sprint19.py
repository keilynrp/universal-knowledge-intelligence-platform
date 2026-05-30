"""
Sprint 19 — ARL Phase 2: Batch Resolution & Review Queue

Endpoints tested:
  POST /authority/resolve/batch
  GET  /authority/queue/summary
  POST /authority/records/bulk-confirm
  POST /authority/records/bulk-reject
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend import models
from backend.authority.base import AuthorityCandidate as _Candidate


# ── Fixtures & helpers ────────────────────────────────────────────────────────

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


def _seed_entities(db_session, brands: list[str]):
    for brand in brands:
        db_session.add(models.RawEntity(primary_label=brand))
    db_session.commit()


def _seed_pending_record(db_session, field="primary_label", value="Acme", source="wikidata"):
    rec = models.AuthorityRecord(
        field_name=field,
        original_value=value,
        authority_source=source,
        authority_id="Q999",
        canonical_label="Acme Corp",
        aliases="[]",
        confidence=0.8,
        status="pending",
        resolution_status="probable_match",
        score_breakdown="{}",
        evidence="[]",
        merged_sources="[]",
    )
    db_session.add(rec)
    db_session.commit()
    db_session.refresh(rec)
    return rec


# ── POST /authority/resolve/batch ─────────────────────────────────────────────

class TestBatchResolve:
    # Phase 1, Task 3: the default endpoint is now async (enqueues a job).
    # These legacy tests assert the synchronous record shape, so they pin sync=true.
    _URL = "/authority/resolve/batch?sync=true"

    def _payload(self, **kw):
        defaults = {"field_name": "primary_label", "entity_type": "general", "limit": 10}
        defaults.update(kw)
        return defaults

    def test_unauthenticated_returns_401(self, client):
        assert client.post(self._URL, json=self._payload()).status_code == 401

    def test_viewer_returns_403(self, client, viewer_headers):
        assert client.post(self._URL, json=self._payload(), headers=viewer_headers).status_code == 403

    def test_editor_can_batch_resolve(self, client, editor_headers, db_session):
        _seed_entities(db_session, ["Microsoft", "Apple"])
        with patch(_PATCH, return_value=_MOCK_CANDIDATES):
            resp = client.post(self._URL, json=self._payload(), headers=editor_headers)
        assert resp.status_code == 201

    def test_response_shape(self, client, editor_headers, db_session):
        _seed_entities(db_session, ["Microsoft", "Apple"])
        with patch(_PATCH, return_value=_MOCK_CANDIDATES):
            resp = client.post(self._URL, json=self._payload(), headers=editor_headers)
        data = resp.json()
        for key in ("field_name", "entity_type", "resolved_count", "skipped_count",
                    "already_existed_count", "records_created", "records"):
            assert key in data

    def test_resolved_count_matches_distinct_values(self, client, editor_headers, db_session):
        _seed_entities(db_session, ["BrandX", "BrandY", "BrandZ"])
        with patch(_PATCH, return_value=_MOCK_CANDIDATES):
            resp = client.post(self._URL, json=self._payload(limit=10), headers=editor_headers)
        assert resp.json()["resolved_count"] >= 1  # at least the seeded ones

    def test_skip_existing_skips_pending_records(self, client, editor_headers, db_session):
        _seed_entities(db_session, ["Acme"])
        _seed_pending_record(db_session, value="Acme")
        with patch(_PATCH, return_value=_MOCK_CANDIDATES):
            resp = client.post(self._URL, json=self._payload(skip_existing=True), headers=editor_headers)
        assert resp.json()["already_existed_count"] >= 1

    def test_skip_existing_false_resolves_all(self, client, auth_headers, db_session):
        _seed_entities(db_session, ["Acme"])
        _seed_pending_record(db_session, value="Acme")
        with patch(_PATCH, return_value=_MOCK_CANDIDATES):
            resp = client.post(
                self._URL,
                json=self._payload(skip_existing=False),
                headers=auth_headers,
            )
        assert resp.json()["already_existed_count"] == 0

    def test_limit_caps_resolved_count(self, client, editor_headers, db_session):
        _seed_entities(db_session, [f"Brand{i}" for i in range(10)])
        with patch(_PATCH, return_value=_MOCK_CANDIDATES):
            resp = client.post(self._URL, json=self._payload(limit=3), headers=editor_headers)
        assert resp.json()["resolved_count"] <= 3

    def test_invalid_field_returns_422(self, client, editor_headers):
        with patch(_PATCH, return_value=[]):
            resp = client.post(
                self._URL,
                json=self._payload(field_name="invalid field!"),
                headers=editor_headers,
            )
        assert resp.status_code == 422

    def test_nonexistent_field_returns_422(self, client, editor_headers):
        with patch(_PATCH, return_value=[]):
            resp = client.post(
                self._URL,
                json=self._payload(field_name="nonexistent_column_xyz"),
                headers=editor_headers,
            )
        assert resp.status_code == 422

    def test_records_are_persisted_as_pending(self, client, editor_headers, db_session):
        _seed_entities(db_session, ["TestBrand"])
        with patch(_PATCH, return_value=_MOCK_CANDIDATES):
            client.post(self._URL, json=self._payload(limit=5), headers=editor_headers)
        # Verify at least one pending record in DB for the field
        count = db_session.query(models.AuthorityRecord).filter(
            models.AuthorityRecord.field_name == "primary_label",
            models.AuthorityRecord.status == "pending",
        ).count()
        assert count >= 1


# ── GET /authority/queue/summary ──────────────────────────────────────────────

class TestQueueSummary:
    _URL = "/authority/queue/summary"

    def test_unauthenticated_returns_401(self, client):
        assert client.get(self._URL).status_code == 401

    def test_viewer_can_access(self, client, viewer_headers):
        assert client.get(self._URL, headers=viewer_headers).status_code == 200

    def test_response_shape(self, client, auth_headers):
        resp = client.get(self._URL, headers=auth_headers)
        data = resp.json()
        assert "total_pending" in data
        assert "total_confirmed" in data
        assert "total_rejected" in data
        assert "by_field" in data
        assert isinstance(data["by_field"], list)

    def test_by_field_entries_have_required_keys(self, client, auth_headers, db_session):
        _seed_pending_record(db_session)
        resp = client.get(self._URL, headers=auth_headers)
        for entry in resp.json()["by_field"]:
            for key in ("field_name", "pending", "confirmed", "rejected", "avg_confidence"):
                assert key in entry

    def test_totals_are_non_negative(self, client, auth_headers):
        resp = client.get(self._URL, headers=auth_headers)
        data = resp.json()
        assert data["total_pending"] >= 0
        assert data["total_confirmed"] >= 0
        assert data["total_rejected"] >= 0

    def test_pending_count_reflects_seeded_record(self, client, auth_headers, db_session):
        _seed_pending_record(db_session, field="entity_type", value="TypeA")
        resp = client.get(self._URL, headers=auth_headers)
        total_pending = resp.json()["total_pending"]
        assert total_pending >= 1


# ── POST /authority/records/bulk-confirm ─────────────────────────────────────

class TestBulkConfirm:
    _URL = "/authority/records/bulk-confirm"

    def test_unauthenticated_returns_401(self, client):
        assert client.post(self._URL, json={"ids": [1]}).status_code == 401

    def test_viewer_returns_403(self, client, viewer_headers):
        assert client.post(self._URL, json={"ids": [1]}, headers=viewer_headers).status_code == 403

    def test_confirm_pending_record(self, client, editor_headers, db_session):
        rec = _seed_pending_record(db_session)
        resp = client.post(self._URL, json={"ids": [rec.id]}, headers=editor_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed"] == 1

    def test_creates_rule_when_also_create_rules_true(self, client, editor_headers, db_session):
        rec = _seed_pending_record(db_session, value="RuleMe")
        resp = client.post(
            self._URL,
            json={"ids": [rec.id], "also_create_rules": True},
            headers=editor_headers,
        )
        assert resp.json()["rules_created"] >= 1

    def test_no_rule_when_also_create_rules_false(self, client, editor_headers, db_session):
        rec = _seed_pending_record(db_session, value="NoRule")
        resp = client.post(
            self._URL,
            json={"ids": [rec.id], "also_create_rules": False},
            headers=editor_headers,
        )
        assert resp.json()["rules_created"] == 0

    def test_already_confirmed_not_double_counted(self, client, editor_headers, db_session):
        rec = _seed_pending_record(db_session, value="AlreadyConfirmed")
        # Confirm once
        client.post(self._URL, json={"ids": [rec.id]}, headers=editor_headers)
        # Confirm again — should not increment
        resp = client.post(self._URL, json={"ids": [rec.id]}, headers=editor_headers)
        assert resp.json()["confirmed"] == 0

    def test_nonexistent_ids_are_silently_skipped(self, client, editor_headers):
        resp = client.post(self._URL, json={"ids": [999999]}, headers=editor_headers)
        assert resp.status_code == 200
        assert resp.json()["confirmed"] == 0

    def test_empty_ids_returns_422(self, client, editor_headers):
        resp = client.post(self._URL, json={"ids": []}, headers=editor_headers)
        assert resp.status_code == 422


# ── POST /authority/records/bulk-reject ──────────────────────────────────────

class TestBulkReject:
    _URL = "/authority/records/bulk-reject"

    def test_unauthenticated_returns_401(self, client):
        assert client.post(self._URL, json={"ids": [1]}).status_code == 401

    def test_viewer_returns_403(self, client, viewer_headers):
        assert client.post(self._URL, json={"ids": [1]}, headers=viewer_headers).status_code == 403

    def test_reject_pending_record(self, client, editor_headers, db_session):
        rec = _seed_pending_record(db_session, value="RejectMe")
        resp = client.post(self._URL, json={"ids": [rec.id]}, headers=editor_headers)
        assert resp.status_code == 200
        assert resp.json()["rejected"] == 1

    def test_record_status_is_rejected(self, client, editor_headers, db_session):
        rec = _seed_pending_record(db_session, value="StatusCheck")
        client.post(self._URL, json={"ids": [rec.id]}, headers=editor_headers)
        db_session.refresh(rec)
        assert rec.status == "rejected"

    def test_already_rejected_not_double_counted(self, client, editor_headers, db_session):
        rec = _seed_pending_record(db_session, value="AlreadyRejected")
        client.post(self._URL, json={"ids": [rec.id]}, headers=editor_headers)
        resp = client.post(self._URL, json={"ids": [rec.id]}, headers=editor_headers)
        assert resp.json()["rejected"] == 0

    def test_nonexistent_ids_silently_skipped(self, client, editor_headers):
        resp = client.post(self._URL, json={"ids": [888888]}, headers=editor_headers)
        assert resp.status_code == 200
        assert resp.json()["rejected"] == 0
