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
    import backend.scripts.backfill_canonical_id_entity_type as canonical_script
    import backend.scripts.backfill_coauthor_edges as coauthor_script

    monkeypatch.setattr(script, "SessionLocal", session_factory)
    monkeypatch.setattr(canonical_script, "SessionLocal", session_factory)
    monkeypatch.setattr(coauthor_script, "SessionLocal", session_factory)
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


def _seed_missing_canonical_identity(session_factory, *, normalized: dict, domain: str = "science") -> int:
    with session_factory() as db:
        entity = models.RawEntity(
            primary_label="Canonical Identity Fix Test",
            domain=domain,
            source="test",
            canonical_id=None,
            entity_type=None,
            normalized_json=json.dumps(normalized, ensure_ascii=False),
            attributes_json="{}",
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

    def test_canonical_identity_empty_body_uses_safe_defaults(self, client, auth_headers):
        resp = client.post(
            "/admin/data-fixes/canonical-identity",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "dry-run"
        assert "scanned" in body
        assert "fixed_canonical_id" in body
        assert "fixed_entity_type" in body
        assert "skipped_duplicates" in body

    def test_canonical_identity_rejects_invalid_only(self, client, auth_headers):
        resp = client.post(
            "/admin/data-fixes/canonical-identity",
            json={"only": "bad_field"},
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

    def test_canonical_identity_dry_run_does_not_mutate(self, client, auth_headers, session_factory):
        eid = _seed_missing_canonical_identity(
            session_factory,
            normalized={"DOI": "10.0001/admin-canonical-dry", "Tipo": "article"},
        )
        try:
            resp = client.post(
                "/admin/data-fixes/canonical-identity",
                json={"dry_run": True},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            assert resp.json()["mode"] == "dry-run"
            assert resp.json()["fixed_canonical_id"] >= 1
            assert resp.json()["fixed_entity_type"] >= 1
            with session_factory() as db:
                entity = db.query(models.RawEntity).filter_by(id=eid).one()
                assert entity.canonical_id is None
                assert entity.entity_type is None
        finally:
            _cleanup(session_factory, [eid])

    def test_canonical_identity_apply_populates_existing_records(self, client, auth_headers, session_factory):
        eid = _seed_missing_canonical_identity(
            session_factory,
            normalized={"Identificador único": "ID-ADMIN-42", "Tipo de entidad": "dataset"},
        )
        try:
            resp = client.post(
                "/admin/data-fixes/canonical-identity",
                json={"dry_run": False},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["mode"] == "applied"
            assert body["fixed_canonical_id"] >= 1
            assert body["fixed_entity_type"] >= 1
            with session_factory() as db:
                entity = db.query(models.RawEntity).filter_by(id=eid).one()
                assert entity.canonical_id == "ID-ADMIN-42"
                assert entity.entity_type == "dataset"
                attrs = json.loads(entity.attributes_json)
                assert attrs["_canonical_backfill"]["canonical_id"].startswith("normalized_json.")
                assert attrs["_canonical_backfill"]["entity_type"].startswith("normalized_json.")
        finally:
            _cleanup(session_factory, [eid])


# ── Coauthor edge backfill ──────────────────────────────────────────────────


class TestCoauthorBackfillRBAC:
    def test_unauthenticated_returns_401(self, client):
        resp = client.post("/admin/data-fixes/coauthor-edges", json={})
        assert resp.status_code == 401

    def test_viewer_is_forbidden(self, client, viewer_headers):
        resp = client.post(
            "/admin/data-fixes/coauthor-edges",
            json={"dry_run": True},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_editor_is_forbidden(self, client, editor_headers):
        resp = client.post(
            "/admin/data-fixes/coauthor-edges",
            json={"dry_run": True},
            headers=editor_headers,
        )
        assert resp.status_code == 403


class TestCoauthorBackfillBehavior:
    def test_empty_db_returns_zero_counters(self, client, auth_headers):
        resp = client.post(
            "/admin/data-fixes/coauthor-edges",
            json={"dry_run": False, "domain": "__coauth_admin_empty__"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "applied"
        assert body["scanned"] == 0
        assert body["with_authors"] == 0
        assert body["edges_generated"] == 0
        assert body["errors"] == 0

    def test_apply_populates_edges(self, client, auth_headers, session_factory):
        # Seed two multi-author entities in a unique domain.
        with session_factory() as db:
            for authors in [["Alice", "Bob", "Carol"], ["Alice", "Bob"]]:
                db.add(models.RawEntity(
                    primary_label="Co-author seed",
                    domain="__coauth_admin_apply__",
                    enrichment_status="completed",
                    attributes_json=json.dumps({"enrichment_authors": authors}),
                ))
            db.commit()

        resp = client.post(
            "/admin/data-fixes/coauthor-edges",
            json={"dry_run": False, "domain": "__coauth_admin_apply__"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "applied"
        assert body["scanned"] == 2
        assert body["with_authors"] == 2
        assert body["edges_generated"] >= 2

        # Verify rows were actually persisted.
        with session_factory() as db:
            count = (
                db.query(models.EntityRelationship)
                .filter(models.EntityRelationship.relation_type == "CO_AUTHOR")
                .count()
            )
            assert count >= 3  # ≥ 3 pairs from one 3-author + one 2-author paper

    def test_dry_run_does_not_write(self, client, auth_headers, session_factory):
        with session_factory() as db:
            db.add(models.RawEntity(
                primary_label="Dry-run seed",
                domain="__coauth_admin_dryrun__",
                enrichment_status="completed",
                attributes_json=json.dumps(
                    {"enrichment_authors": ["X", "Y", "Z"]},
                ),
            ))
            db.commit()

        resp = client.post(
            "/admin/data-fixes/coauthor-edges",
            json={"dry_run": True, "domain": "__coauth_admin_dryrun__"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["mode"] == "dry-run"

        with session_factory() as db:
            count = (
                db.query(models.EntityRelationship)
                .filter(models.EntityRelationship.relation_type == "CO_AUTHOR")
                .filter(models.EntityRelationship.notes.like("X%||%"))
                .count()
            )
            assert count == 0

    def test_unknown_field_rejected(self, client, auth_headers):
        resp = client.post(
            "/admin/data-fixes/coauthor-edges",
            json={"dry_run": True, "garbage": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 422

