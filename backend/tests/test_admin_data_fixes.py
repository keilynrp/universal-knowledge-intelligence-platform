"""Tests for ``POST /admin/data-fixes/legacy-affiliations``.

Covers RBAC, payload validation, dry-run safety, and counter shape.
"""

from __future__ import annotations

import json
from typing import Iterable

import pytest

from backend import models


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_session_local(monkeypatch, session_factory):
    """The endpoint delegates to ``backend.scripts.fix_legacy_affiliations.run``,
    which constructs its own session via the module-level SessionLocal. Bind it
    to the test factory so the work happens on the in-memory test DB."""
    import backend.scripts.fix_legacy_affiliations as script

    monkeypatch.setattr(script, "SessionLocal", session_factory)
    yield


def _seed_affected(session_factory, *, doi: str, attrs: dict, source: str = "openalex") -> int:
    with session_factory() as db:
        entity = models.RawEntity(
            primary_label="Admin Fix Test",
            domain="science",
            source="test",
            enrichment_doi=doi,
            enrichment_source=source,
            enrichment_status="completed",
            attributes_json=json.dumps(attrs, ensure_ascii=False),
        )
        db.add(entity)
        db.commit()
        return entity.id


def _cleanup(session_factory, ids: Iterable[int]) -> None:
    with session_factory() as db:
        db.query(models.RawEntity).filter(
            models.RawEntity.id.in_(list(ids))
        ).delete(synchronize_session=False)
        db.commit()


# ── 1. RBAC ──────────────────────────────────────────────────────────────────


class TestAuth:
    def test_unauthenticated_returns_401(self, client):
        resp = client.post("/admin/data-fixes/legacy-affiliations", json={})
        assert resp.status_code == 401

    def test_viewer_is_forbidden(self, client, viewer_headers):
        resp = client.post(
            "/admin/data-fixes/legacy-affiliations",
            json={"dry_run": True},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_editor_is_forbidden(self, client, editor_headers):
        resp = client.post(
            "/admin/data-fixes/legacy-affiliations",
            json={"dry_run": True},
            headers=editor_headers,
        )
        assert resp.status_code == 403


# ── 2. Payload validation ────────────────────────────────────────────────────


class TestPayloadValidation:
    def test_empty_body_uses_safe_defaults(self, client, auth_headers, session_factory):
        # Without any inputs the call should still succeed (dry_run defaults to True).
        resp = client.post(
            "/admin/data-fixes/legacy-affiliations",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "dry-run"
        assert body["requeue_enrichment"] is False
        assert "scanned" in body and "matched" in body and "fixed" in body

    def test_unknown_field_rejected(self, client, auth_headers):
        resp = client.post(
            "/admin/data-fixes/legacy-affiliations",
            json={"dry_run": True, "unknown_param": "x"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_org_id_must_be_positive(self, client, auth_headers):
        resp = client.post(
            "/admin/data-fixes/legacy-affiliations",
            json={"org_id": 0},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_limit_must_be_positive(self, client, auth_headers):
        resp = client.post(
            "/admin/data-fixes/legacy-affiliations",
            json={"limit": 0},
            headers=auth_headers,
        )
        assert resp.status_code == 422


# ── 3. Behavior ──────────────────────────────────────────────────────────────


class TestBehavior:
    def test_dry_run_does_not_mutate(self, client, auth_headers, session_factory):
        eid = _seed_affected(
            session_factory,
            doi="10.0001/admin-dry",
            attrs={"affiliation": "Some Journal Name"},
        )
        try:
            resp = client.post(
                "/admin/data-fixes/legacy-affiliations",
                json={"dry_run": True},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["mode"] == "dry-run"
            assert resp.json()["fixed"] >= 1
            with session_factory() as db:
                attrs = json.loads(
                    db.query(models.RawEntity).filter_by(id=eid).one().attributes_json
                )
                # Untouched: rollback path inside the script.
                assert attrs["affiliation"] == "Some Journal Name"
                assert "_legacy_affiliation_backup" not in attrs
        finally:
            _cleanup(session_factory, [eid])

    def test_apply_mode_clears_legacy_value(self, client, auth_headers, session_factory):
        eid = _seed_affected(
            session_factory,
            doi="10.0001/admin-apply",
            attrs={"affiliation": "Another Journal"},
        )
        try:
            resp = client.post(
                "/admin/data-fixes/legacy-affiliations",
                json={"dry_run": False},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["mode"] == "applied"
            assert body["fixed"] >= 1
            with session_factory() as db:
                attrs = json.loads(
                    db.query(models.RawEntity).filter_by(id=eid).one().attributes_json
                )
                assert "affiliation" not in attrs
                assert attrs["_legacy_affiliation_backup"]["affiliation"] == "Another Journal"
        finally:
            _cleanup(session_factory, [eid])

    def test_requeue_enrichment_flag(self, client, auth_headers, session_factory):
        eid = _seed_affected(
            session_factory,
            doi="10.0001/admin-requeue",
            attrs={"affiliation": "Yet Another Journal"},
        )
        try:
            resp = client.post(
                "/admin/data-fixes/legacy-affiliations",
                json={"dry_run": False, "requeue_enrichment": True},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["requeue_enrichment"] is True
            with session_factory() as db:
                entity = db.query(models.RawEntity).filter_by(id=eid).one()
                assert entity.enrichment_status == "pending"
        finally:
            _cleanup(session_factory, [eid])

    def test_dry_run_never_advertises_requeue(self, client, auth_headers):
        # Even if caller asks for requeue, dry_run=True must not promise it.
        resp = client.post(
            "/admin/data-fixes/legacy-affiliations",
            json={"dry_run": True, "requeue_enrichment": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["requeue_enrichment"] is False
