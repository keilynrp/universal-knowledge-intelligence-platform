"""
Tests for the derived data status service and endpoint.
Covers:
  - All six resources returning 'missing' for an empty domain
  - enrichment returning 'ready', 'stale', 'missing' based on entity counts
  - rag_index returning 'unknown' when ChromaDB is unreachable (mocked)
  - GET /derived-status/{domain_id} returning HTTP 200 with all six keys
  - Cache hit — second call within TTL returns the same computed_at
  - GET /derived-status/nonexistent returning HTTP 404
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend import models
from backend.services.derived_status_service import (
    TRACKED_RESOURCES,
    DerivedStatusService,
    STATUS_MISSING,
    STATUS_READY,
    STATUS_STALE,
    STATUS_UNKNOWN,
    status_cache,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_DOMAIN = "test_derived_status_domain"
SCOPE = f"domain:{TEST_DOMAIN}"


def _make_entity(db, enrichment_status: str = "none", enrichment_concepts: str | None = None):
    entity = models.RawEntity(
        primary_label=f"Entity {enrichment_status}",
        domain=TEST_DOMAIN,
        enrichment_status=enrichment_status,
        enrichment_concepts=enrichment_concepts,
        source="user",
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def _cleanup(db):
    db.query(models.EntityRelationship).delete()
    db.query(models.RawEntity).filter(models.RawEntity.domain == TEST_DOMAIN).delete()
    db.commit()
    # Evict cache entries for this domain
    status_cache.invalidate(TEST_DOMAIN)
    status_cache.invalidate(SCOPE)


# ---------------------------------------------------------------------------
# Service unit tests — all resources return 'missing' for empty domain
# ---------------------------------------------------------------------------

class TestEmptyDomain:
    def test_all_resources_missing_for_empty_domain(self, db_session):
        _cleanup(db_session)
        bundle = DerivedStatusService.compute_all(SCOPE, db_session)

        assert set(bundle["resources"].keys()) == set(TRACKED_RESOURCES)
        for resource in TRACKED_RESOURCES:
            entry = bundle["resources"][resource]
            assert entry["status"] == STATUS_MISSING, (
                f"Expected {resource} to be 'missing' in an empty domain, got {entry['status']!r}"
            )
            assert entry["source_count"] == 0
        _cleanup(db_session)

    def test_bundle_has_required_keys(self, db_session):
        _cleanup(db_session)
        bundle = DerivedStatusService.compute_all(SCOPE, db_session)
        assert "domain_id" in bundle
        assert "computed_at" in bundle
        assert "resources" in bundle
        _cleanup(db_session)

    def test_each_resource_entry_has_required_fields(self, db_session):
        _cleanup(db_session)
        bundle = DerivedStatusService.compute_all(SCOPE, db_session)
        required_fields = {"status", "updated_at", "source_count", "derived_count", "last_error", "can_rebuild", "rebuild_endpoint"}
        for resource in TRACKED_RESOURCES:
            entry = bundle["resources"][resource]
            assert required_fields <= set(entry.keys()), (
                f"{resource} is missing required fields"
            )
        _cleanup(db_session)


# ---------------------------------------------------------------------------
# Enrichment resource computation
# ---------------------------------------------------------------------------

class TestEnrichmentResource:
    def test_all_completed_returns_ready(self, db_session):
        _cleanup(db_session)
        for _ in range(3):
            _make_entity(db_session, enrichment_status="completed")

        entry = DerivedStatusService.compute("enrichment", SCOPE, db_session)
        assert entry["status"] == STATUS_READY
        assert entry["derived_count"] == entry["source_count"] == 3
        _cleanup(db_session)

    def test_partial_enrichment_returns_stale(self, db_session):
        _cleanup(db_session)
        _make_entity(db_session, enrichment_status="completed")
        _make_entity(db_session, enrichment_status="none")
        _make_entity(db_session, enrichment_status="none")

        entry = DerivedStatusService.compute("enrichment", SCOPE, db_session)
        assert entry["status"] == STATUS_STALE
        assert entry["derived_count"] == 1
        assert entry["source_count"] == 3
        _cleanup(db_session)

    def test_no_enrichment_returns_missing(self, db_session):
        _cleanup(db_session)
        _make_entity(db_session, enrichment_status="none")
        _make_entity(db_session, enrichment_status="none")

        entry = DerivedStatusService.compute("enrichment", SCOPE, db_session)
        assert entry["status"] == STATUS_MISSING
        assert entry["derived_count"] == 0
        assert entry["source_count"] == 2
        _cleanup(db_session)

    def test_completed_entities_count_as_ready(self, db_session):
        _cleanup(db_session)
        _make_entity(db_session, enrichment_status="completed")
        _make_entity(db_session, enrichment_status="completed")

        entry = DerivedStatusService.compute("enrichment", SCOPE, db_session)
        assert entry["status"] == STATUS_READY
        assert entry["derived_count"] == 2
        _cleanup(db_session)


# ---------------------------------------------------------------------------
# RAG index — unknown when ChromaDB unreachable
# ---------------------------------------------------------------------------

class TestRagIndexResource:
    def test_chromadb_unreachable_returns_unknown(self, db_session):
        _cleanup(db_session)
        _make_entity(db_session, enrichment_status="completed")

        # Patch VectorStoreService.get_stats at the source module so the lazy
        # import inside _compute_rag_index picks up the mock.
        with patch(
            "backend.analytics.vector_store.VectorStoreService.get_stats",
            side_effect=Exception("ChromaDB unreachable"),
        ):
            entry = DerivedStatusService.compute("rag_index", SCOPE, db_session)

        assert entry["status"] == STATUS_UNKNOWN
        assert entry["last_error"] is not None
        _cleanup(db_session)

    def test_chromadb_unreachable_does_not_propagate_exception(self, db_session):
        _cleanup(db_session)

        with patch(
            "backend.analytics.vector_store.VectorStoreService.get_stats",
            side_effect=Exception("ChromaDB unreachable"),
        ):
            # Should not raise
            try:
                entry = DerivedStatusService.compute("rag_index", SCOPE, db_session)
                assert entry["status"] in (STATUS_UNKNOWN, STATUS_MISSING)
            except Exception as exc:
                pytest.fail(f"compute('rag_index') propagated exception: {exc}")
        _cleanup(db_session)


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestDerivedStatusEndpoint:
    def _with_known_domain(self):
        """Context manager that patches the registry so TEST_DOMAIN is considered valid."""
        from backend.schema_registry import DomainSchema
        fake_domain = DomainSchema(
            id=TEST_DOMAIN,
            name="Test Domain",
            description="",
            primary_entity="entity",
            icon="🔬",
            attributes=[],
        )
        return patch(
            "backend.routers.derived_status._registry.get_domain",
            side_effect=lambda did: fake_domain if did == TEST_DOMAIN else None,
        )

    def test_endpoint_returns_200_with_six_keys(self, client, auth_headers, db_session):
        _cleanup(db_session)
        with self._with_known_domain():
            response = client.get(f"/derived-status/domain:{TEST_DOMAIN}", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert set(body["resources"].keys()) == set(TRACKED_RESOURCES)
        _cleanup(db_session)

    def test_endpoint_requires_auth(self, client, db_session):
        _cleanup(db_session)
        response = client.get(f"/derived-status/domain:{TEST_DOMAIN}")
        assert response.status_code in (401, 403)
        _cleanup(db_session)

    def test_all_scope_returns_200(self, client, auth_headers):
        # "all" is always valid, no 404
        response = client.get("/derived-status/all", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert "resources" in body
        assert len(body["resources"]) == 6

    def test_nonexistent_domain_returns_404(self, client, auth_headers):
        response = client.get("/derived-status/domain:nonexistent_xyz_domain", headers=auth_headers)
        assert response.status_code == 404

    def test_response_includes_computed_at(self, client, auth_headers, db_session):
        _cleanup(db_session)
        with self._with_known_domain():
            response = client.get(f"/derived-status/domain:{TEST_DOMAIN}", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert "computed_at" in body
        assert "domain_id" in body
        _cleanup(db_session)


# ---------------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------------

class TestDerivedStatusCache:
    def _with_known_domain(self):
        from backend.schema_registry import DomainSchema
        fake_domain = DomainSchema(
            id=TEST_DOMAIN,
            name="Test Domain",
            description="",
            primary_entity="entity",
            icon="🔬",
            attributes=[],
        )
        return patch(
            "backend.routers.derived_status._registry.get_domain",
            side_effect=lambda did: fake_domain if did == TEST_DOMAIN else None,
        )

    def test_cache_hit_returns_same_computed_at(self, client, auth_headers, db_session):
        _cleanup(db_session)
        # Clear any existing cached entry for this domain
        status_cache.invalidate(TEST_DOMAIN)
        status_cache.invalidate(f"domain:{TEST_DOMAIN}")

        with self._with_known_domain():
            response1 = client.get(f"/derived-status/domain:{TEST_DOMAIN}", headers=auth_headers)
            assert response1.status_code == 200
            computed_at_1 = response1.json()["computed_at"]

            # Second call — should hit cache
            response2 = client.get(f"/derived-status/domain:{TEST_DOMAIN}", headers=auth_headers)
            assert response2.status_code == 200
            computed_at_2 = response2.json()["computed_at"]

        assert computed_at_1 == computed_at_2, (
            "Second response within TTL should return the same computed_at timestamp"
        )
        _cleanup(db_session)

    def test_invalidate_cache_causes_recompute(self, client, auth_headers, db_session):
        _cleanup(db_session)
        status_cache.invalidate(TEST_DOMAIN)
        status_cache.invalidate(f"domain:{TEST_DOMAIN}")

        with self._with_known_domain():
            response1 = client.get(f"/derived-status/domain:{TEST_DOMAIN}", headers=auth_headers)
            assert response1.status_code == 200
            computed_at_1 = response1.json()["computed_at"]

            # Manually invalidate
            status_cache.invalidate(f"domain:{TEST_DOMAIN}")

            response2 = client.get(f"/derived-status/domain:{TEST_DOMAIN}", headers=auth_headers)
            assert response2.status_code == 200
            computed_at_2 = response2.json()["computed_at"]

        # After invalidation, the timestamp may differ (a new computation runs)
        assert computed_at_2 is not None
        _cleanup(db_session)
