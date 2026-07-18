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
    _next_batch_state,
    _emit_enrichment_batch_complete,
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


#  ── enrichment.completed batch edge-trigger ─────────────────────────────────

class TestBatchCompletion:
    def test_state_increments_while_processing(self):
        assert _next_batch_state(entity_claimed=True, processed=0) == (1, None)
        assert _next_batch_state(entity_claimed=True, processed=3) == (4, None)

    def test_state_emits_once_on_drain_edge(self):
        # Queue just drained after enriching 5 → emit count 5, reset to 0.
        assert _next_batch_state(entity_claimed=False, processed=5) == (0, 5)

    def test_state_idle_when_nothing_processed_does_not_emit(self):
        assert _next_batch_state(entity_claimed=False, processed=0) == (0, None)

    def test_emit_batch_complete_calls_emit_outbound(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "backend.enrichment_worker.emit_outbound",
            lambda action, payload, db_factory: calls.append((action, payload)),
        )
        _emit_enrichment_batch_complete(7, object())
        assert calls == [("enrichment.completed", {"count": 7})]


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

    mock_wos = MagicMock(); mock_wos.is_active = False
    mock_openalex = MagicMock(); mock_openalex.is_active = True; mock_openalex.search_by_title.return_value = []
    mock_cb = MagicMock(); mock_cb.call = lambda fn, *a, **kw: fn(*a, **kw)

    with (
        patch("backend.enrichment_worker._ACTIVE_CASCADE", ["wos", "openalex"]),
        patch("backend.enrichment_worker._PROVIDER_MAP", {
            "wos": (mock_wos, mock_cb),
            "openalex": (mock_openalex, mock_cb),
        }),
        patch("backend.enrichment_worker.enrich_with_web_scrapers", return_value=False),
    ):
        result = enrich_single_record(db_session, entity)

    assert result.enrichment_status == "failed"
    failure = json.loads(result.attributes_json)["enrichment_failure"]
    assert failure["code"] == "no_provider_match"
    assert "openalex" in failure["provider_attempts"]
    assert "Some Unknown Entity" in failure["evidence"]


def test_enrich_skips_scholar_when_disabled(db_session):
    entity = make_entity(db_session, "No Scholar Fallback", status="processing")

    mock_wos = MagicMock(); mock_wos.is_active = False
    mock_openalex = MagicMock(); mock_openalex.is_active = True; mock_openalex.search_by_title.return_value = []
    mock_cb = MagicMock(); mock_cb.call = lambda fn, *a, **kw: fn(*a, **kw)

    with (
        patch("backend.enrichment_worker._ACTIVE_CASCADE", ["wos", "openalex", "scholar"]),
        patch("backend.enrichment_worker._PROVIDER_MAP", {
            "wos": (mock_wos, mock_cb),
            "openalex": (mock_openalex, mock_cb),
            "scholar": (None, mock_cb),
        }),
        patch("backend.enrichment_worker.enrich_with_web_scrapers", return_value=False),
    ):
        result = enrich_single_record(db_session, entity)

    assert result.enrichment_status == "failed"


def test_enrich_marks_completed_on_openalex_success(db_session):
    entity = make_entity(db_session, "Good Paper Title", status="processing")

    mock_result = MagicMock()
    mock_result.doi = "10.1234/test"
    mock_result.citation_count = 42
    mock_result.concepts = ["Biology", "Genetics"]
    mock_result.work_type = "article"
    mock_result.authors = ["Alice Smith", "Bob Jones"]
    mock_result.author_orcids = ["0000-0001-2345-6789", None]
    mock_result.concept_ids = []
    mock_result.funding = None
    mock_result.tldr = None
    mock_result.mesh_terms = None
    mock_result.influential_citation_count = None
    mock_result.references_count = None
    mock_result.license = None
    mock_result.venue = None
    mock_result.affiliations = None

    mock_openalex = MagicMock()
    mock_openalex.is_active = True
    mock_openalex.search_by_title.return_value = [mock_result]
    mock_cb = MagicMock()
    mock_cb.call = lambda fn, *a, **kw: fn(*a, **kw)

    with (
        patch("backend.enrichment_worker._ACTIVE_CASCADE", ["openalex"]),
        patch("backend.enrichment_worker._PROVIDER_MAP", {"openalex": (mock_openalex, mock_cb)}),
    ):
        result = enrich_single_record(db_session, entity)

    assert result.enrichment_status == "completed"
    assert result.enrichment_doi == "10.1234/test"
    assert result.enrichment_citation_count == 42
    assert "Biology" in result.enrichment_concepts
    attrs = json.loads(result.attributes_json or "{}")
    assert "enrichment_failure" not in attrs
    assert attrs["enrichment_authors"] == ["Alice Smith", "Bob Jones"]
    assert attrs["enrichment_author_orcids"] == ["0000-0001-2345-6789", None]


def test_enrich_completion_syncs_dashboard_workflows_and_rag(db_session):
    entity = make_entity(db_session, "Sync Paper", status="processing")
    entity.domain = "sync_domain"
    db_session.commit()

    mock_result = MagicMock()
    mock_result.doi = "10.5555/sync"
    mock_result.citation_count = 7
    mock_result.concepts = ["Knowledge Graphs"]
    mock_result.work_type = "article"
    mock_result.authors = []
    mock_result.author_orcids = []
    mock_result.concept_ids = []
    mock_result.funding = None
    mock_result.tldr = None
    mock_result.mesh_terms = None
    mock_result.influential_citation_count = None
    mock_result.references_count = None
    mock_result.license = None
    mock_result.venue = None
    mock_result.affiliations = None

    mock_openalex = MagicMock()
    mock_openalex.is_active = True
    mock_openalex.search_by_title.return_value = [mock_result]
    mock_cb = MagicMock()
    mock_cb.call = lambda fn, *a, **kw: fn(*a, **kw)
    integration = MagicMock()

    with (
        patch("backend.enrichment_worker._ACTIVE_CASCADE", ["openalex"]),
        patch("backend.enrichment_worker._PROVIDER_MAP", {"openalex": (mock_openalex, mock_cb)}),
        patch("backend.routers.analytics.invalidate_analytics_for_domain") as invalidate,
        patch("backend.workflow_engine.fire_trigger") as fire_trigger,
        patch("backend.routers.deps._get_active_integration", return_value=integration),
        patch("backend.analytics.rag_engine.index_entity") as index_entity,
        patch("backend.services.semantic_keyword_signal_engine.materialize_keyword_signals") as materialize_signals,
    ):
        result = enrich_single_record(db_session, entity)

    assert result.enrichment_status == "completed"
    invalidate.assert_called_once_with("sync_domain")
    fire_trigger.assert_called_once()
    assert fire_trigger.call_args.args[:2] == ("entity.enriched", result)
    index_entity.assert_called_once_with(result, integration)
    materialize_signals.assert_called_once()
    assert materialize_signals.call_args.args[1] == "sync_domain"


def test_enrich_marks_failed_on_unexpected_exception(db_session):
    entity = make_entity(db_session, "Crash Entity", status="processing")

    mock_openalex = MagicMock()
    mock_openalex.is_active = True
    mock_openalex.search_by_title.side_effect = RuntimeError("network down")
    mock_cb = MagicMock()
    mock_cb.call = lambda fn, *a, **kw: fn(*a, **kw)

    with (
        patch("backend.enrichment_worker._ACTIVE_CASCADE", ["openalex"]),
        patch("backend.enrichment_worker._PROVIDER_MAP", {"openalex": (mock_openalex, mock_cb)}),
    ):
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


def test_trigger_bulk_can_return_queued_ids(db_session):
    first = make_entity(db_session, "Queued 1", status="none")
    second = make_entity(db_session, "Queued 2", status="failed")
    completed = make_entity(db_session, "Already Done", status="completed")

    queued_ids = trigger_enrichment_bulk(db_session, return_ids=True)

    assert queued_ids == [first.id, second.id]
    assert completed.id not in queued_ids
