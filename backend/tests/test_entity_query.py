"""
Tests for backend.services.entity_query — the centralised RawEntity base-query factory.

Coverage map (tasks.md §6):
  6.1  entity_base_q excludes graph_materializer rows
  6.2  entity_base_q with scope "domain:X" filters to domain X only
  6.3  count_total returns 0 for empty domain
  6.4  count_by_status counts only entities with the given status
  6.5  count_enriched == count_by_status(..., EnrichmentStatus.completed)
  6.6  importing entity_query has no side effects (no DB connection required)
"""
import importlib

import pytest

from backend import models
from backend.schemas import EnrichmentStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(session_factory):
    """Fresh DB session, cleaned up after each test."""
    with session_factory() as session:
        yield session
        # Clean up any RawEntity rows created by this test
        session.query(models.RawEntity).delete()
        session.commit()


def _make_entity(db, *, source="test", domain="science", status=EnrichmentStatus.none, **kwargs):
    """Create and persist a minimal RawEntity for testing."""
    entity = models.RawEntity(
        source=source,
        domain=domain,
        primary_label=kwargs.get("primary_label", "Test Entity"),
        enrichment_status=status,
        **{k: v for k, v in kwargs.items() if k != "primary_label"},
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# ── 6.1: graph_materializer rows are excluded ─────────────────────────────────

class TestGraphMaterializerExclusion:
    def test_real_entity_is_included(self, db):
        from backend.services.entity_query import entity_base_q

        _make_entity(db, source="openalex", domain="science")
        count = entity_base_q(db, "all").count()
        assert count >= 1

    def test_graph_materializer_entity_is_excluded(self, db):
        from backend.services.entity_query import entity_base_q

        _make_entity(db, source="graph_materializer", domain="science",
                     primary_label="Synth Entity")
        # Base query should not count graph_materializer rows
        real_count = entity_base_q(db, "all").count()
        total_count = db.query(models.RawEntity).count()
        assert real_count < total_count, (
            "entity_base_q must exclude source='graph_materializer' rows"
        )

    def test_graph_materializer_not_in_results(self, db):
        from backend.services.entity_query import entity_base_q

        _make_entity(db, source="graph_materializer", primary_label="Ghost")
        rows = entity_base_q(db, "all").all()
        sources = {r.source for r in rows}
        assert "graph_materializer" not in sources


# ── 6.2: domain scope filters to the right domain ─────────────────────────────

class TestDomainScopeFilter:
    def test_domain_scope_excludes_other_domains(self, db):
        from backend.services.entity_query import entity_base_q

        _make_entity(db, domain="science", primary_label="Science Paper")
        _make_entity(db, domain="healthcare", primary_label="Health Record")

        science_count = entity_base_q(db, "domain:science").count()
        health_count = entity_base_q(db, "domain:healthcare").count()

        assert science_count >= 1
        assert health_count >= 1
        # Science query must not include the healthcare row
        science_rows = entity_base_q(db, "domain:science").all()
        domains_seen = {r.domain for r in science_rows}
        assert "healthcare" not in domains_seen

    def test_all_scope_includes_all_domains(self, db):
        from backend.services.entity_query import entity_base_q

        _make_entity(db, domain="science", primary_label="S")
        _make_entity(db, domain="healthcare", primary_label="H")

        all_count = entity_base_q(db, "all").count()
        science_count = entity_base_q(db, "domain:science").count()
        health_count = entity_base_q(db, "domain:healthcare").count()

        assert all_count >= science_count + health_count


# ── 6.3: count_total returns 0 for empty domain ───────────────────────────────

class TestCountTotal:
    def test_count_total_returns_zero_for_empty_domain(self, db):
        from backend.services.entity_query import count_total

        # Use a domain that definitely has no rows in this test session
        count = count_total(db, "domain:__nonexistent_test_domain__")
        assert count == 0

    def test_count_total_counts_real_entities(self, db):
        from backend.services.entity_query import count_total

        _make_entity(db, domain="testdom", primary_label="E1")
        _make_entity(db, domain="testdom", primary_label="E2")
        # graph_materializer must not be counted
        _make_entity(db, domain="testdom", source="graph_materializer", primary_label="Ghost")

        count = count_total(db, "domain:testdom")
        assert count == 2


# ── 6.4: count_by_status counts only the given status ─────────────────────────

class TestCountByStatus:
    def test_counts_only_matching_status(self, db):
        from backend.services.entity_query import count_by_status

        _make_entity(db, domain="cbs_dom", status=EnrichmentStatus.completed,
                     primary_label="Done1")
        _make_entity(db, domain="cbs_dom", status=EnrichmentStatus.completed,
                     primary_label="Done2")
        _make_entity(db, domain="cbs_dom", status=EnrichmentStatus.pending,
                     primary_label="Pending1")
        _make_entity(db, domain="cbs_dom", status=EnrichmentStatus.failed,
                     primary_label="Failed1")

        assert count_by_status(db, "domain:cbs_dom", EnrichmentStatus.completed) == 2
        assert count_by_status(db, "domain:cbs_dom", EnrichmentStatus.pending) == 1
        assert count_by_status(db, "domain:cbs_dom", EnrichmentStatus.failed) == 1
        assert count_by_status(db, "domain:cbs_dom", EnrichmentStatus.processing) == 0

    def test_count_by_status_ignores_graph_materializer(self, db):
        from backend.services.entity_query import count_by_status

        _make_entity(db, domain="cbs_gm", source="graph_materializer",
                     status=EnrichmentStatus.completed, primary_label="Ghost Done")
        _make_entity(db, domain="cbs_gm", source="openalex",
                     status=EnrichmentStatus.completed, primary_label="Real Done")

        assert count_by_status(db, "domain:cbs_gm", EnrichmentStatus.completed) == 1


# ── 6.5: count_enriched == count_by_status(..., completed) ────────────────────

class TestCountEnriched:
    def test_count_enriched_equals_count_by_status_completed(self, db):
        from backend.services.entity_query import count_by_status, count_enriched

        _make_entity(db, domain="ce_dom", status=EnrichmentStatus.completed, primary_label="A")
        _make_entity(db, domain="ce_dom", status=EnrichmentStatus.completed, primary_label="B")
        _make_entity(db, domain="ce_dom", status=EnrichmentStatus.pending, primary_label="C")

        assert count_enriched(db, "domain:ce_dom") == count_by_status(
            db, "domain:ce_dom", EnrichmentStatus.completed
        )
        assert count_enriched(db, "domain:ce_dom") == 2


# ── 6.6: import has no side effects ───────────────────────────────────────────

class TestImportSideEffects:
    def test_import_entity_query_requires_no_db_connection(self):
        """
        Importing the module must not open a DB connection or perform any IO.
        We verify by reloading it; if any side-effect query ran it would raise
        or leak connections in the test's StaticPool.
        """
        import backend.services.entity_query as eq_module
        reloaded = importlib.reload(eq_module)
        # The module must export the expected callables
        assert callable(reloaded.entity_base_q)
        assert callable(reloaded.count_total)
        assert callable(reloaded.count_by_status)
        assert callable(reloaded.count_enriched)
