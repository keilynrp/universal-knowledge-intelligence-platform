"""Tests for backend.scripts.backfill_canonical_id_entity_type and the
expanded COLUMN_MAPPING synonyms (ES/EN + vendor IDs)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from backend import models
from backend.routers.column_maps import COLUMN_MAPPING
from backend.scripts import backfill_canonical_id_entity_type as backfill


# ── COLUMN_MAPPING expansion ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "header",
    [
        "Tipo de Identificador",
        "Identificador",
        "Identificador único",
        "Identificador unico",
        "ID único",
        "PMID",
        "PubMed ID",
        "WOS ID",
        "WoS ID",
        "Scopus ID",
        "EID",
        "OpenAlex ID",
        "ORCID ID",
        "ROR ID",
        "DOI Number",
        "Código",
        "Codigo",
        "UID",
        "Local ID",
    ],
)
def test_canonical_id_header_synonyms_are_recognised(header):
    assert COLUMN_MAPPING.get(header) == "canonical_id"


@pytest.mark.parametrize(
    "header",
    [
        "Tipo",
        "Tipo de entidad",
        "Categoría",
        "Categoria",
        "Clase",
        "Class",
        "Document Type",
        "Tipo de documento",
        "Publication Type",
        "Tipo de publicación",
        "Subtype",
    ],
)
def test_entity_type_header_synonyms_are_recognised(header):
    assert COLUMN_MAPPING.get(header) == "entity_type"


# ── Backfill — pure-function resolvers ──────────────────────────────────────


def test_resolve_canonical_id_uses_enrichment_doi_first():
    entity = models.RawEntity(enrichment_doi="10.1000/xyz", domain="science")
    value, source = backfill._resolve_canonical_id(entity, {"doi": "ignored"}, {})
    assert value == "10.1000/xyz"
    assert source == "enrichment_doi"


def test_resolve_canonical_id_falls_through_to_attrs():
    entity = models.RawEntity(enrichment_doi=None, domain="science")
    attrs = {"orcid": "0000-0002-1234-5678"}
    value, source = backfill._resolve_canonical_id(entity, attrs, {})
    assert value == "0000-0002-1234-5678"
    assert source == "attributes_json.orcid"


def test_resolve_canonical_id_reads_normalized_with_spanish_header():
    entity = models.RawEntity(enrichment_doi=None, domain="default")
    normalized = {"Identificador único": "ABC-123"}
    value, source = backfill._resolve_canonical_id(entity, {}, normalized)
    assert value == "ABC-123"
    assert source == "normalized_json.Identificador único"


def test_resolve_canonical_id_returns_none_when_nothing_to_recover():
    entity = models.RawEntity(enrichment_doi=None, domain="default")
    value, source = backfill._resolve_canonical_id(entity, {}, {"foo": "bar"})
    assert value is None
    assert source is None


def test_resolve_entity_type_prefers_document_type():
    entity = models.RawEntity(domain="default")
    attrs = {"document_type": "article", "_entry_type": "book"}
    value, source = backfill._resolve_entity_type(entity, attrs, {})
    assert value == "article"
    assert source == "attributes_json.document_type"


def test_resolve_entity_type_reads_normalized_with_spanish_header():
    entity = models.RawEntity(domain="default")
    normalized = {"Tipo de entidad": "publication"}
    value, source = backfill._resolve_entity_type(entity, {}, normalized)
    assert value == "publication"
    assert source == "normalized_json.Tipo de entidad"


def test_resolve_entity_type_falls_back_to_publication_for_science():
    entity = models.RawEntity(domain="science", enrichment_source="openalex")
    value, source = backfill._resolve_entity_type(entity, {}, {})
    assert value == "publication"
    assert source == "fallback:science"


def test_resolve_entity_type_no_fallback_for_non_science():
    entity = models.RawEntity(domain="default", enrichment_source=None)
    value, source = backfill._resolve_entity_type(entity, {}, {})
    assert value is None
    assert source is None


# ── Backfill — end-to-end against the test DB ───────────────────────────────


def _seed_entity(db_session, **kwargs):
    entity = models.RawEntity(**kwargs)
    db_session.add(entity)
    db_session.commit()
    db_session.refresh(entity)
    return entity


def test_backfill_populates_both_fields_from_normalized_json(db_session):
    entity = _seed_entity(
        db_session,
        primary_label="Some title",
        domain="default",
        canonical_id=None,
        entity_type=None,
        normalized_json=json.dumps(
            {"Identificador único": "ID-42", "Tipo de entidad": "dataset"},
            ensure_ascii=False,
        ),
    )
    entity_id = entity.id

    with patch.object(backfill, "SessionLocal", return_value=db_session) as _:
        # Patch SessionLocal so the script reuses the test session. Disable
        # the auto-close inside ``run()`` by monkeypatching db.close to a noop.
        original_close = db_session.close
        db_session.close = lambda: None
        try:
            result = backfill.run(dry_run=False, only=None, org_id=None, limit=None)
        finally:
            db_session.close = original_close

    assert result["fixed_canonical_id"] >= 1
    assert result["fixed_entity_type"] >= 1

    refreshed = db_session.query(models.RawEntity).filter_by(id=entity_id).one()
    assert refreshed.canonical_id == "ID-42"
    assert refreshed.entity_type == "dataset"
    attrs = json.loads(refreshed.attributes_json or "{}")
    assert attrs["_canonical_backfill"]["canonical_id"].startswith("normalized_json.")
    assert attrs["_canonical_backfill"]["entity_type"].startswith("normalized_json.")


def test_backfill_does_not_overwrite_existing_values(db_session):
    entity = _seed_entity(
        db_session,
        primary_label="Existing",
        domain="default",
        canonical_id="EXISTING-ID",
        entity_type=None,
        normalized_json=json.dumps({"DOI": "10.1000/never", "Tipo": "report"}),
    )
    entity_id = entity.id

    original_close = db_session.close
    db_session.close = lambda: None
    try:
        with patch.object(backfill, "SessionLocal", return_value=db_session):
            backfill.run(dry_run=False, only=None, org_id=None, limit=None)
    finally:
        db_session.close = original_close

    refreshed = db_session.query(models.RawEntity).filter_by(id=entity_id).one()
    assert refreshed.canonical_id == "EXISTING-ID"  # untouched
    assert refreshed.entity_type == "report"  # filled


def test_backfill_dry_run_does_not_persist(db_session):
    entity = _seed_entity(
        db_session,
        primary_label="Dry",
        domain="default",
        canonical_id=None,
        entity_type=None,
        normalized_json=json.dumps({"DOI": "10.1000/dry", "Tipo": "article"}),
    )
    entity_id = entity.id

    original_close = db_session.close
    db_session.close = lambda: None
    try:
        with patch.object(backfill, "SessionLocal", return_value=db_session):
            result = backfill.run(dry_run=True, only=None, org_id=None, limit=None)
    finally:
        db_session.close = original_close

    assert result["fixed_canonical_id"] >= 1
    db_session.expire_all()
    refreshed = db_session.query(models.RawEntity).filter_by(id=entity_id).one()
    assert refreshed.canonical_id is None
    assert refreshed.entity_type is None


def test_backfill_only_filter(db_session):
    entity = _seed_entity(
        db_session,
        primary_label="Only filter",
        domain="default",
        canonical_id=None,
        entity_type=None,
        normalized_json=json.dumps({"DOI": "10.1000/only", "Tipo": "article"}),
    )
    entity_id = entity.id

    original_close = db_session.close
    db_session.close = lambda: None
    try:
        with patch.object(backfill, "SessionLocal", return_value=db_session):
            backfill.run(dry_run=False, only="canonical_id", org_id=None, limit=None)
    finally:
        db_session.close = original_close

    refreshed = db_session.query(models.RawEntity).filter_by(id=entity_id).one()
    assert refreshed.canonical_id == "10.1000/only"
    assert refreshed.entity_type is None
