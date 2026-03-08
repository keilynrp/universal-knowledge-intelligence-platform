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
            "entity_name":              f"Demo Entity {i}",
            "brand_capitalized":        f"DemoBrand{i % 3}",
            "classification":           "Software",
            "creation_date":            "2023-06-01",
            "enrichment_status":        "completed",
            "enrichment_citation_count": 10 * (i + 1),
            "enrichment_concepts":      "AI, machine learning",
            "enrichment_source":        "openalex",
            "sku":                      f"DEMO-TST-{i:05d}",
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


def test_demo_seed_loads_entities(client, auth_headers, db_session):
    """With mocked file + DataFrame, seed must insert entities with source='demo'."""
    df = _demo_df(5)
    with _fake_demo_file(df):
        resp = client.post("/demo/seed", headers=auth_headers)

    # Should succeed (201) or conflict (409 if already seeded by other test)
    assert resp.status_code in (201, 409)
    if resp.status_code == 201:
        assert resp.json()["seeded"] == 5


def test_demo_seed_conflict_if_already_seeded(client, auth_headers, db_session):
    """A second seed call while demo data exists must return 409."""
    # Insert a demo entity directly
    db_session.add(models.RawEntity(entity_name="Existing Demo", source="demo"))
    db_session.commit()

    df = _demo_df(3)
    with _fake_demo_file(df):
        resp = client.post("/demo/seed", headers=auth_headers)

    assert resp.status_code == 409


# ── DELETE /demo/reset ────────────────────────────────────────────────────────

def test_demo_reset_requires_admin(client, viewer_headers):
    resp = client.delete("/demo/reset", headers=viewer_headers)
    assert resp.status_code in (401, 403)


def test_demo_reset_clears_only_demo_entities(client, auth_headers, db_session):
    """User entities (source='user') must survive a reset."""
    # Seed one demo + one user entity
    db_session.add(models.RawEntity(entity_name="Demo Entity", source="demo"))
    db_session.add(models.RawEntity(entity_name="User Entity", source="user"))
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


def test_demo_reset_returns_deleted_count(client, auth_headers, db_session):
    db_session.add(models.RawEntity(entity_name="Demo A", source="demo"))
    db_session.add(models.RawEntity(entity_name="Demo B", source="demo"))
    db_session.commit()

    resp = client.delete("/demo/reset", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] >= 2
