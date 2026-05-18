"""
Tests for backend/enrichment_worker.py — atomic claim logic,
stale record reset, and error handling.
"""
import json

import pytest
from unittest.mock import MagicMock, patch

from backend import models
from backend.enrichment_worker import (
    _atomic_claim_next,
    reset_stale_processing_records,
    enrich_single_record,
    trigger_enrichment_bulk,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_entity(db, name="Test Entity", status="pending"):
    entity = models.RawEntity(primary_label=name, enrichment_status=status)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# ── reset_stale_processing_records ───────────────────────────────────────────

def test_reset_stale_records_resets_processing_to_pending(db_session):
    e1 = make_entity(db_session, "Stuck Entity 1", status="processing")
    e2 = make_entity(db_session, "Stuck Entity 2", status="processing")
    completed = make_entity(db_session, "Done", status="completed")

    count = reset_stale_processing_records(db_session)

    assert count == 2
    db_session.refresh(e1)
    db_session.refresh(e2)
    db_session.refresh(completed)
    assert e1.enrichment_status == "pending"
    assert e2.enrichment_status == "pending"
    assert completed.enrichment_status == "completed"  # untouched


def test_reset_stale_no_records_returns_zero(db_session):
    make_entity(db_session, "Normal", status="pending")
    count = reset_stale_processing_records(db_session)
    assert count == 0


# ── _atomic_claim_next ───────────────────────────────────────────────────────

def test_atomic_claim_returns_entity_id(db_session):
    entity = make_entity(db_session, "ClaimMe", status="pending")
    claimed_id = _atomic_claim_next(db_session)
    assert claimed_id == entity.id
    db_session.refresh(entity)
    assert entity.enrichment_status == "processing"


def test_atomic_claim_returns_none_when_no_pending(db_session):
    make_entity(db_session, "Done", status="completed")
    claimed_id = _atomic_claim_next(db_session)
    assert claimed_id is None


def test_atomic_claim_does_not_double_claim(db_session):
    """Simulates two concurrent workers — only one should claim the record."""
    entity = make_entity(db_session, "RaceTarget", status="pending")

    # First claim succeeds
    first_claim = _atomic_claim_next(db_session)
    assert first_claim == entity.id

    # Second claim on the same session finds no more pending records
    second_claim = _atomic_claim_next(db_session)
    assert second_claim is None  # already processing

    db_session.refresh(entity)
    assert entity.enrichment_status == "processing"


# ── enrich_single_record error handling ──────────────────────────────────────

def test_enrich_marks_failed_on_empty_name(db_session):
    entity = make_entity(db_session, status="processing")
    entity.primary_label = None
    db_session.commit()

    result = enrich_single_record(db_session, entity)
    assert result.enrichment_status == "failed"
    failure = json.loads(result.attributes_json)["enrichment_failure"]
    assert failure["code"] == "missing_title"
    assert failure["recommendations"]


def test_enrich_marks_failed_when_all_adapters_return_nothing(db_session):
    entity = make_entity(db_session, "Some Unknown Entity", status="processing")

    with (
        patch("backend.enrichment_worker.adapter_wos") as mock_wos,
        patch("backend.enrichment_worker.adapter_openalex") as mock_openalex,
        patch("backend.enrichment_worker.adapter_scholar") as mock_scholar,
    ):
        mock_wos.is_active = False
        mock_openalex.search_by_title.return_value = []
        mock_scholar.search_by_title.return_value = []

        result = enrich_single_record(db_session, entity)

    assert result.enrichment_status == "failed"
    failure = json.loads(result.attributes_json)["enrichment_failure"]
    assert failure["code"] == "no_provider_match"
    assert "OpenAlex" in failure["provider_attempts"]
    assert "Some Unknown Entity" in failure["evidence"]


def test_enrich_skips_scholar_when_disabled(db_session):
    entity = make_entity(db_session, "No Scholar Fallback", status="processing")

    with (
        patch("backend.enrichment_worker.adapter_wos") as mock_wos,
        patch("backend.enrichment_worker.adapter_openalex") as mock_openalex,
        patch("backend.enrichment_worker.adapter_scholar", None),
    ):
        mock_wos.is_active = False
        mock_openalex.search_by_title.return_value = []

        result = enrich_single_record(db_session, entity)

    assert result.enrichment_status == "failed"


def test_enrich_marks_completed_on_openalex_success(db_session):
    entity = make_entity(db_session, "Good Paper Title", status="processing")

    mock_result = MagicMock()
    mock_result.doi = "10.1234/test"
    mock_result.citation_count = 42
    mock_result.concepts = ["Biology", "Genetics"]
    mock_result.authors = ["Alice Smith", "Bob Jones"]
    mock_result.author_orcids = ["0000-0001-2345-6789", None]

    with (
        patch("backend.enrichment_worker.adapter_wos") as mock_wos,
        patch("backend.enrichment_worker.adapter_openalex") as mock_openalex,
    ):
        mock_wos.is_active = False
        mock_openalex.search_by_title.return_value = [mock_result]

        result = enrich_single_record(db_session, entity)

    assert result.enrichment_status == "completed"
    assert result.enrichment_doi == "10.1234/test"
    assert result.enrichment_citation_count == 42
    assert "Biology" in result.enrichment_concepts
    attrs = json.loads(result.attributes_json or "{}")
    assert "enrichment_failure" not in attrs
    assert attrs["enrichment_authors"] == ["Alice Smith", "Bob Jones"]
    assert attrs["enrichment_author_orcids"] == ["0000-0001-2345-6789", None]


def test_enrich_marks_failed_on_unexpected_exception(db_session):
    entity = make_entity(db_session, "Crash Entity", status="processing")

    with patch("backend.enrichment_worker.adapter_openalex") as mock_openalex:
        mock_openalex.search_by_title.side_effect = RuntimeError("network down")
        with patch("backend.enrichment_worker.adapter_wos") as mock_wos:
            mock_wos.is_active = False
            result = enrich_single_record(db_session, entity)

    assert result.enrichment_status == "failed"
    failure = json.loads(result.attributes_json)["enrichment_failure"]
    assert failure["code"] == "unexpected_error"
    assert failure["exception_type"] == "RuntimeError"


# ── trigger_enrichment_bulk ──────────────────────────────────────────────────

def test_trigger_bulk_marks_none_and_failed_as_pending(db_session):
    e_none = make_entity(db_session, "E1", status="none")
    e_fail = make_entity(db_session, "E2", status="failed")
    e_fail.attributes_json = json.dumps({"enrichment_failure": {"code": "no_provider_match"}})
    e_done = make_entity(db_session, "E3", status="completed")
    e_proc = make_entity(db_session, "E4", status="processing")
    db_session.commit()

    count = trigger_enrichment_bulk(db_session)

    assert count == 2
    db_session.refresh(e_none)
    db_session.refresh(e_fail)
    db_session.refresh(e_done)
    db_session.refresh(e_proc)
    assert e_none.enrichment_status == "pending"
    assert e_fail.enrichment_status == "pending"
    assert "enrichment_failure" not in json.loads(e_fail.attributes_json or "{}")
    assert e_done.enrichment_status == "completed"  # untouched
    assert e_proc.enrichment_status == "processing"  # untouched


def test_trigger_bulk_can_scope_to_domain(db_session):
    target = models.RawEntity(primary_label="Domain Target", domain="science", enrichment_status="none")
    other = models.RawEntity(primary_label="Other Domain", domain="business", enrichment_status="none")
    db_session.add_all([target, other])
    db_session.commit()

    count = trigger_enrichment_bulk(db_session, domain_id="science")

    assert count == 1
    db_session.refresh(target)
    db_session.refresh(other)
    assert target.enrichment_status == "pending"
    assert other.enrichment_status == "none"
