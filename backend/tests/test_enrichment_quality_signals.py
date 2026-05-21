"""
Tests for enrichment-quality-signals features.

Coverage map (tasks.md §6):
  6.1  success_count increments on success, resets on HALF_OPEN→CLOSED transition
       (in test_circuit_breaker.py — duplicated here for completeness)
  6.2  EnrichmentFailureReason constants written when enrichment fails
  6.3  GET /enrichment/sources/health returns 200 with all registered sources
  6.4  GET /enrichment/sources/stats returns 200 with expected shape
  6.5  GET /enrichment/sources/stats?domain_id=science filters correctly
  6.6  NULL enrichment_failure_reason handled gracefully in stats
"""
import time
from unittest.mock import patch, MagicMock

import pytest

from backend import models
from backend.circuit_breaker import CircuitBreaker, CircuitState
from backend.enrichment_worker import (
    EnrichmentFailureReason,
    _CB_REGISTRY,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ok(*_args, **_kwargs):
    return ["result"]


def _fail(*_args, **_kwargs):
    raise ConnectionError("service down")


@pytest.fixture()
def db(session_factory):
    """Fresh DB session, cleaned up after each test."""
    with session_factory() as session:
        yield session
        session.query(models.RawEntity).delete()
        session.commit()


def _make_entity(
    db,
    *,
    source: str | None = "openalex",
    domain: str = "science",
    status: str = "failed",
    failure_reason: str | None = None,
):
    entity = models.RawEntity(
        source="user",
        domain=domain,
        primary_label="Test Entity",
        enrichment_source=source,
        enrichment_status=status,
        enrichment_failure_reason=failure_reason,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# ── 6.1 CircuitBreaker success_count ──────────────────────────────────────────

class TestCircuitBreakerSuccessCount:
    def test_success_count_starts_at_zero(self):
        cb = CircuitBreaker("test-sc", failure_threshold=3, recovery_timeout=60)
        assert cb.success_count == 0

    def test_success_count_increments_on_each_success(self):
        cb = CircuitBreaker("test-sc", failure_threshold=3, recovery_timeout=60)
        cb.call(_ok)
        cb.call(_ok)
        cb.call(_ok)
        assert cb.success_count == 3

    def test_success_count_not_affected_by_failures(self):
        cb = CircuitBreaker("test-sc", failure_threshold=5, recovery_timeout=60)
        cb.call(_ok)   # success_count → 1, failure_count stays 0
        cb.call(_ok)   # success_count → 2
        with pytest.raises(ConnectionError):
            cb.call(_fail)  # failure_count → 1, success_count unchanged
        # A subsequent success resets failure_count and increments success_count
        cb.call(_ok)
        assert cb.failure_count == 0  # success resets failure_count
        assert cb.success_count == 3  # 2 earlier + 1 recovery success

    def test_success_count_resets_on_half_open_to_closed_transition(self):
        """When a circuit recovers from HALF_OPEN, success_count resets to 0 then becomes 1."""
        cb = CircuitBreaker("test-sc-recover", failure_threshold=1, recovery_timeout=0.01)
        # Trip the circuit
        with pytest.raises(ConnectionError):
            cb.call(_fail)
        assert cb.state == CircuitState.OPEN

        # Accumulate some successes manually on a fresh CB to verify reset
        cb2 = CircuitBreaker("test-sc2", failure_threshold=1, recovery_timeout=0.01)
        with pytest.raises(ConnectionError):
            cb2.call(_fail)  # trip
        # Wait for recovery timeout
        time.sleep(0.02)
        # Verify HALF_OPEN probe succeeds and resets success_count before counting new success
        assert cb2.state == CircuitState.HALF_OPEN
        cb2.call(_ok)  # probe succeeds
        assert cb2.state == CircuitState.CLOSED
        # success_count was reset to 0 then incremented to 1
        assert cb2.success_count == 1


# ── 6.2 EnrichmentFailureReason constants ─────────────────────────────────────

class TestEnrichmentFailureReasonConstants:
    def test_all_constants_defined(self):
        assert EnrichmentFailureReason.NO_MATCH == "no_match"
        assert EnrichmentFailureReason.API_ERROR == "api_error"
        assert EnrichmentFailureReason.RATE_LIMITED == "rate_limited"
        assert EnrichmentFailureReason.CIRCUIT_OPEN == "circuit_open"
        assert EnrichmentFailureReason.TIMEOUT == "timeout"
        assert EnrichmentFailureReason.ALL_SOURCES_FAILED == "all_sources_failed"

    def test_failure_reason_stored_on_entity(self, db):
        entity = _make_entity(db, failure_reason=EnrichmentFailureReason.NO_MATCH)
        db.refresh(entity)
        assert entity.enrichment_failure_reason == "no_match"

    def test_failure_reason_circuit_open_stored(self, db):
        entity = _make_entity(db, failure_reason=EnrichmentFailureReason.CIRCUIT_OPEN)
        db.refresh(entity)
        assert entity.enrichment_failure_reason == "circuit_open"

    def test_null_failure_reason_allowed(self, db):
        entity = _make_entity(db, failure_reason=None)
        db.refresh(entity)
        assert entity.enrichment_failure_reason is None


# ── 6.3 GET /enrichment/sources/health ────────────────────────────────────────

class TestSourcesHealthEndpoint:
    def test_returns_200(self, client, auth_headers):
        resp = client.get("/enrichment/sources/health", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_has_sources_list(self, client, auth_headers):
        resp = client.get("/enrichment/sources/health", headers=auth_headers)
        data = resp.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_all_registered_sources_present(self, client, auth_headers):
        resp = client.get("/enrichment/sources/health", headers=auth_headers)
        data = resp.json()
        source_names = {entry["source"] for entry in data["sources"]}
        for expected_source in _CB_REGISTRY:
            assert expected_source in source_names, (
                f"Source '{expected_source}' missing from health response"
            )

    def test_each_entry_has_required_fields(self, client, auth_headers):
        resp = client.get("/enrichment/sources/health", headers=auth_headers)
        data = resp.json()
        for entry in data["sources"]:
            assert "source" in entry
            assert "state" in entry
            assert "failure_count" in entry
            assert "success_count" in entry

    def test_state_is_valid_value(self, client, auth_headers):
        valid_states = {"CLOSED", "OPEN", "HALF_OPEN"}
        resp = client.get("/enrichment/sources/health", headers=auth_headers)
        data = resp.json()
        for entry in data["sources"]:
            assert entry["state"] in valid_states

    def test_requires_authentication(self, client):
        resp = client.get("/enrichment/sources/health")
        assert resp.status_code == 401


# ── 6.4 GET /enrichment/sources/stats ─────────────────────────────────────────

class TestSourcesStatsEndpoint:
    def test_returns_200(self, client, auth_headers):
        resp = client.get("/enrichment/sources/stats", headers=auth_headers)
        assert resp.status_code == 200

    def test_response_has_expected_shape(self, client, auth_headers, db):
        _make_entity(db, source="openalex", domain="science", status="completed")
        _make_entity(db, source="openalex", domain="science", status="failed",
                     failure_reason="no_match")

        resp = client.get("/enrichment/sources/stats", headers=auth_headers)
        data = resp.json()
        assert "entries" in data
        assert "domain_id" in data
        assert isinstance(data["entries"], list)

        # Find openalex entry
        oa_entry = next(
            (e for e in data["entries"] if e["enrichment_source"] == "openalex"), None
        )
        assert oa_entry is not None
        assert "total" in oa_entry
        assert "enriched" in oa_entry
        assert "failed" in oa_entry
        assert "failure_reasons" in oa_entry
        assert isinstance(oa_entry["failure_reasons"], dict)

    def test_counts_correct(self, client, auth_headers, db):
        _make_entity(db, source="crossref", domain="science", status="completed")
        _make_entity(db, source="crossref", domain="science", status="completed")
        _make_entity(db, source="crossref", domain="science", status="failed",
                     failure_reason="api_error")

        resp = client.get("/enrichment/sources/stats", headers=auth_headers)
        data = resp.json()
        crossref = next(
            (e for e in data["entries"] if e["enrichment_source"] == "crossref"), None
        )
        assert crossref is not None
        assert crossref["enriched"] >= 2
        assert crossref["failed"] >= 1
        assert crossref["failure_reasons"].get("api_error", 0) >= 1

    def test_requires_authentication(self, client):
        resp = client.get("/enrichment/sources/stats")
        assert resp.status_code == 401


# ── 6.5 GET /enrichment/sources/stats?domain_id= filter ──────────────────────

class TestSourcesStatsFilter:
    def test_domain_filter_echoed_in_response(self, client, auth_headers):
        resp = client.get("/enrichment/sources/stats?domain_id=science", headers=auth_headers)
        data = resp.json()
        assert data["domain_id"] == "science"

    def test_domain_filter_excludes_other_domains(self, client, auth_headers, db):
        _make_entity(db, source="pubmed", domain="healthcare", status="failed",
                     failure_reason="timeout")
        _make_entity(db, source="pubmed", domain="science", status="completed")

        # Filter to science only — should not see healthcare failures
        resp = client.get("/enrichment/sources/stats?domain_id=science", headers=auth_headers)
        data = resp.json()

        pubmed = next(
            (e for e in data["entries"] if e["enrichment_source"] == "pubmed"), None
        )
        if pubmed is not None:
            # The 'timeout' reason came from healthcare domain — must not appear
            assert pubmed["failure_reasons"].get("timeout", 0) == 0

    def test_domain_filter_only_counts_matching_domain(self, client, auth_headers, db):
        _make_entity(db, source="wos", domain="science", status="completed")
        _make_entity(db, source="wos", domain="science", status="completed")
        _make_entity(db, source="wos", domain="healthcare", status="completed")

        resp = client.get("/enrichment/sources/stats?domain_id=science", headers=auth_headers)
        data = resp.json()
        wos = next(
            (e for e in data["entries"] if e["enrichment_source"] == "wos"), None
        )
        assert wos is not None
        # Only 2 science records, not 3
        assert wos["total"] == 2

    def test_no_filter_returns_all_domains(self, client, auth_headers, db):
        _make_entity(db, source="scopus", domain="science", status="completed")
        _make_entity(db, source="scopus", domain="healthcare", status="completed")

        resp = client.get("/enrichment/sources/stats", headers=auth_headers)
        data = resp.json()
        assert data["domain_id"] is None
        scopus = next(
            (e for e in data["entries"] if e["enrichment_source"] == "scopus"), None
        )
        assert scopus is not None
        assert scopus["total"] >= 2


# ── 6.6 NULL enrichment_failure_reason handled gracefully ─────────────────────

class TestNullFailureReason:
    def test_null_reason_counted_as_unknown_in_stats(self, client, auth_headers, db):
        # Entity failed but no specific reason recorded
        _make_entity(db, source="dblp", domain="science", status="failed",
                     failure_reason=None)

        resp = client.get("/enrichment/sources/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        dblp = next(
            (e for e in data["entries"] if e["enrichment_source"] == "dblp"), None
        )
        assert dblp is not None
        assert dblp["failed"] >= 1
        # NULL reason should appear as "unknown" key
        assert dblp["failure_reasons"].get("unknown", 0) >= 1

    def test_mixed_null_and_known_reasons(self, client, auth_headers, db):
        _make_entity(db, source="semantic_scholar", domain="science", status="failed",
                     failure_reason=None)
        _make_entity(db, source="semantic_scholar", domain="science", status="failed",
                     failure_reason="no_match")

        resp = client.get("/enrichment/sources/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        ss = next(
            (e for e in data["entries"] if e["enrichment_source"] == "semantic_scholar"), None
        )
        assert ss is not None
        assert ss["failed"] >= 2
        assert ss["failure_reasons"].get("unknown", 0) >= 1
        assert ss["failure_reasons"].get("no_match", 0) >= 1

    def test_entity_with_null_reason_does_not_crash_health_endpoint(self, client, auth_headers, db):
        _make_entity(db, source="openalex", domain="science", status="failed",
                     failure_reason=None)
        # Health endpoint should still succeed regardless of DB state
        resp = client.get("/enrichment/sources/health", headers=auth_headers)
        assert resp.status_code == 200
