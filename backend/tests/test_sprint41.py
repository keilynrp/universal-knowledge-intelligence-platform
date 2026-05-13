"""
Sprint 41 regression tests — Demo Mode (seed / reset / status).
"""
import io
import pytest
from unittest.mock import MagicMock, patch

import pandas as pd

from backend import models


# ── Helpers ───────────────────────────────────────────────────────────────────

def _demo_df(n: int = 5) -> pd.DataFrame:
    """Minimal demo DataFrame matching demo_entities.xlsx schema."""
    return pd.DataFrame([
        {
            "primary_label":            f"Demo Entity {i}",
            "secondary_label":          f"DemoBrand{i % 3}",
            "entity_type":              "software",
            "enrichment_status":        "completed",
            "enrichment_citation_count": 10 * (i + 1),
            "enrichment_concepts":      "AI, machine learning",
            "enrichment_source":        "openalex",
        }
        for i in range(n)
    ])


def _legacy_demo_df(n: int = 5) -> pd.DataFrame:
    """Legacy demo DataFrame matching the pre-normalized spreadsheet schema."""
    return pd.DataFrame([
        {
            "entity_name": f"Legacy Demo Entity {i}",
            "brand_capitalized": f"DemoBrand{i % 3}",
            "brand_lower": f"demobrand{i % 3}",
            "classification": "Simulation Software",
            "entity_type": "Science",
            "sku": f"DEMO-SCI-{i:05d}",
            "creation_date": "2024-05-10",
            "status": "active",
            "validation_status": "valid",
            "enrichment_status": "completed",
            "enrichment_citation_count": 10 * (i + 1),
            "enrichment_concepts": "AI, machine learning",
            "enrichment_source": "openalex",
        }
        for i in range(n)
    ])


import contextlib
from unittest.mock import patch as _patch


@contextlib.contextmanager
def _fake_demo_file(df: pd.DataFrame):
    """Patch _DEMO_FILE.exists() → True and pd.read_excel → df."""
    with _patch("backend.routers.demo._DEMO_FILE") as mp, \
         _patch("backend.routers.demo.pd.read_excel", return_value=df):
        mp.exists.return_value = True
        yield


# ── GET /demo/status ──────────────────────────────────────────────────────────

def test_demo_status_requires_auth(client):
    resp = client.get("/demo/status")
    assert resp.status_code in (401, 403)


def test_demo_status_false_when_empty(client, auth_headers):
    resp = client.get("/demo/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "demo_seeded" in data
    assert "demo_entity_count" in data
    assert data["demo_entity_count"] >= 0


# ── POST /demo/seed ───────────────────────────────────────────────────────────

def test_demo_seed_requires_admin(client, viewer_headers):
    """Viewers must not be able to seed."""
    resp = client.post("/demo/seed", headers=viewer_headers)
    assert resp.status_code in (401, 403)


def test_demo_seed_loads_entities_via_legacy_excel(client, auth_headers, db_session):
    """With mocked file + DataFrame (legacy path), seed must insert entities and publish a demo portal."""
    df = _demo_df(5)
    with _fake_demo_file(df), \
         _patch("backend.routers.demo._try_openalex_live", side_effect=RuntimeError("offline")), \
         _patch("backend.routers.demo._load_openalex_snapshot", side_effect=FileNotFoundError("no snapshot")):
        resp = client.post("/demo/seed", headers=auth_headers)

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["seeded"] == 5
    assert payload["source"] == "legacy_excel"
    assert payload["catalog_portal"]["url"].startswith("/catalogs/")


def test_demo_seed_idempotent_reseed(client, auth_headers, db_session):
    """A second seed call while demo data exists should clear old data and re-seed (idempotent)."""
    db_session.add(models.RawEntity(primary_label="Existing Demo", source="demo"))
    db_session.commit()

    df = _demo_df(3)
    with _fake_demo_file(df), \
         _patch("backend.routers.demo._try_openalex_live", side_effect=RuntimeError("offline")), \
         _patch("backend.routers.demo._load_openalex_snapshot", side_effect=FileNotFoundError("no snapshot")):
        resp = client.post("/demo/seed", headers=auth_headers)

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["seeded"] == 3
    # Old demo entity should have been cleared
    old = db_session.query(models.RawEntity).filter_by(primary_label="Existing Demo").first()
    assert old is None


def test_demo_seed_uses_snapshot_fallback(client, auth_headers, db_session):
    """When live OpenAlex fails, seed should use bundled snapshot JSON."""
    from backend.schemas_enrichment import EnrichedRecord
    fake_records = [
        EnrichedRecord(
            id=f"snap-{i}", doi=f"10.snap/{i}", title=f"Snapshot Paper {i}",
            authors=["Author A"], citation_count=i * 10, publication_year=2023,
            concepts=["KM"], source_api="OpenAlex",
        )
        for i in range(3)
    ]
    with _patch("backend.routers.demo._try_openalex_live", side_effect=RuntimeError("offline")), \
         _patch("backend.routers.demo._load_openalex_snapshot", return_value=(fake_records, "openalex_snapshot")):
        resp = client.post("/demo/seed", headers=auth_headers)

    assert resp.status_code == 201
    payload = resp.json()
    assert payload["source"] == "openalex_snapshot"
    assert payload["seeded"] == 3


def test_demo_seed_maps_legacy_demo_columns(client, auth_headers, db_session):
    df = _legacy_demo_df(3)
    with _fake_demo_file(df), \
         _patch("backend.routers.demo._try_openalex_live", side_effect=RuntimeError("offline")), \
         _patch("backend.routers.demo._load_openalex_snapshot", side_effect=FileNotFoundError("no snapshot")):
        resp = client.post("/demo/seed", headers=auth_headers)

    assert resp.status_code == 201

    rows = db_session.query(models.RawEntity).filter(models.RawEntity.source == "demo").all()
    assert len(rows) == 3
    assert rows[0].primary_label.startswith("Legacy Demo Entity")
    assert rows[0].secondary_label.startswith("DemoBrand")
    assert rows[0].canonical_id.startswith("DEMO-SCI-")
    assert rows[0].domain == "science"

    status = client.get("/demo/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["catalog_portal"]["url"].startswith("/catalogs/")


# ── DELETE /demo/reset ────────────────────────────────────────────────────────

def test_demo_reset_requires_admin(client, viewer_headers):
    resp = client.delete("/demo/reset", headers=viewer_headers)
    assert resp.status_code in (401, 403)


def test_demo_reset_clears_only_demo_entities(client, auth_headers, db_session):
    """User entities (source='user') must survive a reset."""
    # Seed one demo + one user entity
    db_session.add(models.RawEntity(primary_label="Demo Entity", source="demo"))
    db_session.add(models.RawEntity(primary_label="User Entity", source="user"))
    db_session.commit()

    resp = client.delete("/demo/reset", headers=auth_headers)
    assert resp.status_code == 200

    user_count = (
        db_session.query(models.RawEntity)
        .filter(models.RawEntity.source == "user")
        .count()
    )
    demo_count = (
        db_session.query(models.RawEntity)
        .filter(models.RawEntity.source == "demo")
        .count()
    )
    assert demo_count == 0
    assert user_count >= 1


def test_demo_reset_clears_demo_portal_and_batch_only(client, auth_headers, db_session):
    demo_batch = models.ImportBatch(
        domain_id="science",
        source_type="demo",
        source_label="UKIP Demo Dataset",
        total_rows=1,
    )
    user_batch = models.ImportBatch(
        domain_id="science",
        source_type="science_upload",
        source_label="User Import",
        total_rows=1,
    )
    db_session.add_all([demo_batch, user_batch])
    db_session.flush()
    demo_batch_id = demo_batch.id
    user_batch_id = user_batch.id
    db_session.add_all(
        [
            models.CatalogPortal(
                title="Demo Portal",
                slug="demo-portal-reset",
                domain_id="science",
                source_batch_id=demo_batch.id,
                source_label="UKIP Demo Dataset",
            ),
            models.CatalogPortal(
                title="User Portal",
                slug="user-portal-reset",
                domain_id="science",
                source_batch_id=user_batch.id,
                source_label="User Import",
            ),
            models.RawEntity(primary_label="Demo Entity", source="demo", import_batch_id=demo_batch.id),
            models.RawEntity(primary_label="User Entity", source="user", import_batch_id=user_batch.id),
        ]
    )
    db_session.commit()

    resp = client.delete("/demo/reset", headers=auth_headers)
    assert resp.status_code == 200

    assert db_session.query(models.CatalogPortal).filter_by(slug="demo-portal-reset").first() is None
    assert db_session.query(models.ImportBatch).filter_by(id=demo_batch_id).first() is None
    assert db_session.query(models.CatalogPortal).filter_by(slug="user-portal-reset").first() is not None
    assert db_session.query(models.ImportBatch).filter_by(id=user_batch_id).first() is not None
    assert db_session.query(models.RawEntity).filter_by(source="user").count() == 1


def test_demo_reset_returns_deleted_count(client, auth_headers, db_session):
    db_session.add(models.RawEntity(primary_label="Demo A", source="demo"))
    db_session.add(models.RawEntity(primary_label="Demo B", source="demo"))
    db_session.commit()

    resp = client.delete("/demo/reset", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] >= 2
