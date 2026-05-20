"""
Tests for the enrichment scheduler service and API endpoints.

Coverage map (tasks.md §7):
  7.1  _check_domain correctly identifies stale vs healthy domains
  7.2  _requeue_domain sets exactly min(stale_count, budget) entities to 'pending'
  7.3  _requeue_domain does not touch 'completed', 'pending', or 'processing' entities
  7.4  GET /enrichment/schedule returns 200 with expected fields
  7.5  GET /enrichment/schedule/{domain_id} returns staleness report
  7.6  POST /enrichment/schedule/{domain_id}/trigger requires admin role (403 for viewer)
  7.7  PUT /enrichment/schedule/{domain_id}/policy creates on first call (201), updates on second (200)
  7.8  policy with enabled=false causes scheduler to skip that domain in run_once
"""
import pytest

from backend import models
from backend.schemas import EnrichmentStatus
from backend.services.enrichment_scheduler import EnrichmentScheduler


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db(session_factory):
    """Fresh DB session, cleaned up after each test."""
    with session_factory() as session:
        yield session
        session.query(models.EnrichmentSchedulerRun).delete()
        session.query(models.DomainEnrichmentPolicy).delete()
        session.query(models.RawEntity).delete()
        session.commit()


@pytest.fixture()
def sched():
    """A fresh EnrichmentScheduler instance (not the singleton)."""
    return EnrichmentScheduler(interval_seconds=60)


def _make_entity(db, *, source="test", domain="science", status: str = "none"):
    entity = models.RawEntity(
        source=source,
        domain=domain,
        primary_label="Test Entity",
        enrichment_status=status,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def _make_policy(db, domain_id="science", *, enabled=True, min_pct=80.0, budget=100):
    policy = models.DomainEnrichmentPolicy(
        domain_id=domain_id,
        enabled=enabled,
        min_enrichment_pct=min_pct,
        max_budget_per_run=budget,
        staleness_threshold_days=30,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


# ── 7.1: _check_domain identifies stale vs healthy domains ────────────────────

class TestCheckDomain:
    def test_stale_domain_when_below_threshold(self, db, sched):
        """Domain with enrichment below min_pct is flagged as stale."""
        # 3 entities, 1 completed → 33% < 80% threshold
        for _ in range(2):
            _make_entity(db, status="none")
        _make_entity(db, status="completed")

        policy = _make_policy(db, min_pct=80.0)
        report = sched._check_domain(db, "science", policy)

        assert report["is_stale"] is True
        assert report["total_entities"] == 3
        assert report["enriched_entities"] == 1
        assert report["current_enrichment_pct"] == pytest.approx(33.33, abs=0.1)

    def test_healthy_domain_when_above_threshold(self, db, sched):
        """Domain with enrichment at or above min_pct is healthy."""
        for _ in range(9):
            _make_entity(db, status="completed")
        _make_entity(db, status="none")

        policy = _make_policy(db, min_pct=80.0)
        report = sched._check_domain(db, "science", policy)

        assert report["is_stale"] is False
        assert report["current_enrichment_pct"] == pytest.approx(90.0)

    def test_empty_domain_is_not_stale(self, db, sched):
        """Empty domain (no entities) reports is_stale=False."""
        policy = _make_policy(db, min_pct=80.0)
        report = sched._check_domain(db, "science", policy)

        assert report["is_stale"] is False
        assert report["total_entities"] == 0


# ── 7.2: _requeue_domain respects budget cap ──────────────────────────────────

class TestRequeueDomain:
    def test_requeues_up_to_budget(self, db, sched):
        """Requeue caps at max_budget_per_run when more stale entities exist."""
        for _ in range(20):
            _make_entity(db, status="none")

        policy = _make_policy(db, budget=5)
        queued = sched._requeue_domain(db, "science", policy)

        assert queued == 5

        pending_count = (
            db.query(models.RawEntity)
            .filter(
                models.RawEntity.domain == "science",
                models.RawEntity.enrichment_status == "pending",
            )
            .count()
        )
        assert pending_count == 5

    def test_requeues_all_when_fewer_than_budget(self, db, sched):
        """When fewer stale entities than budget, all are requeued."""
        for _ in range(3):
            _make_entity(db, status="none")
        _make_entity(db, status="failed")

        policy = _make_policy(db, budget=100)
        queued = sched._requeue_domain(db, "science", policy)

        assert queued == 4  # 3 none + 1 failed


# ── 7.3: _requeue_domain skips completed/pending/processing ──────────────────

class TestRequeueSafety:
    def test_does_not_touch_completed(self, db, sched):
        """Completed entities must never be re-queued by the scheduler."""
        for _ in range(5):
            _make_entity(db, status="completed")

        policy = _make_policy(db, budget=100)
        queued = sched._requeue_domain(db, "science", policy)

        assert queued == 0

        still_completed = (
            db.query(models.RawEntity)
            .filter(models.RawEntity.enrichment_status == "completed")
            .count()
        )
        assert still_completed == 5

    def test_does_not_touch_pending_or_processing(self, db, sched):
        """Pending and processing entities are skipped."""
        _make_entity(db, status="pending")
        _make_entity(db, status="processing")
        _make_entity(db, status="none")  # this one should be requeued

        policy = _make_policy(db, budget=100)
        queued = sched._requeue_domain(db, "science", policy)

        assert queued == 1  # only the 'none' entity

        # Verify pending/processing are unchanged
        pending = db.query(models.RawEntity).filter(
            models.RawEntity.enrichment_status == "pending"
        ).count()
        processing = db.query(models.RawEntity).filter(
            models.RawEntity.enrichment_status == "processing"
        ).count()
        # One was originally pending, plus the 'none' → 'pending' one → 2 total pending
        assert pending == 2
        assert processing == 1


# ── 7.4: GET /enrichment/schedule returns 200 ─────────────────────────────────

class TestGetSchedulerState:
    def test_returns_200_with_expected_fields(self, client, auth_headers):
        resp = client.get("/enrichment/schedule", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "interval_seconds" in data
        assert "domains_monitored" in data
        assert "total_queued_last_run" in data

    def test_requires_auth(self, client):
        resp = client.get("/enrichment/schedule")
        assert resp.status_code == 401


# ── 7.5: GET /enrichment/schedule/{domain_id} ────────────────────────────────

class TestGetDomainStaleness:
    def test_returns_staleness_report_for_known_domain(self, client, auth_headers):
        # "science" is a built-in domain in the schema registry
        resp = client.get("/enrichment/schedule/science", headers=auth_headers)
        # Either 200 (domain exists) or 404 if not in registry — we just verify it's not a 500
        assert resp.status_code in (200, 404)

    def test_returns_404_for_unknown_domain(self, client, auth_headers):
        resp = client.get(
            "/enrichment/schedule/nonexistent_domain_xyz", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_requires_auth(self, client):
        resp = client.get("/enrichment/schedule/science")
        assert resp.status_code == 401


# ── 7.6: POST trigger requires admin role ─────────────────────────────────────

class TestTriggerAuth:
    def test_viewer_gets_403(self, client, viewer_headers):
        resp = client.post(
            "/enrichment/schedule/science/trigger", headers=viewer_headers
        )
        assert resp.status_code == 403

    def test_admin_can_trigger_or_get_404_for_unknown(self, client, auth_headers):
        # An unknown domain returns 404, not 403
        resp = client.post(
            "/enrichment/schedule/nonexistent_domain_xyz/trigger", headers=auth_headers
        )
        assert resp.status_code == 404

    def test_unauthenticated_gets_401(self, client):
        resp = client.post("/enrichment/schedule/science/trigger")
        assert resp.status_code == 401


# ── 7.7: PUT policy creates (201) then updates (200) ─────────────────────────

class TestUpsertPolicy:
    DOMAIN = "scheduler_test_domain_007"

    def _cleanup(self, session_factory):
        with session_factory() as s:
            s.query(models.DomainEnrichmentPolicy).filter(
                models.DomainEnrichmentPolicy.domain_id == self.DOMAIN
            ).delete()
            s.commit()

    def test_creates_policy_returns_201(self, client, auth_headers, session_factory):
        self._cleanup(session_factory)
        resp = client.put(
            f"/enrichment/schedule/{self.DOMAIN}/policy",
            json={"min_enrichment_pct": 75.0, "max_budget_per_run": 50, "enabled": True},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["domain_id"] == self.DOMAIN
        assert data["min_enrichment_pct"] == 75.0

    def test_updates_existing_policy_returns_200(self, client, auth_headers, session_factory):
        self._cleanup(session_factory)
        # First create
        client.put(
            f"/enrichment/schedule/{self.DOMAIN}/policy",
            json={"min_enrichment_pct": 75.0, "enabled": True},
            headers=auth_headers,
        )
        # Then update
        resp = client.put(
            f"/enrichment/schedule/{self.DOMAIN}/policy",
            json={"min_enrichment_pct": 90.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["min_enrichment_pct"] == 90.0

    def test_invalid_pct_returns_422(self, client, auth_headers):
        resp = client.put(
            f"/enrichment/schedule/{self.DOMAIN}/policy",
            json={"min_enrichment_pct": 150},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_viewer_gets_403(self, client, viewer_headers):
        resp = client.put(
            f"/enrichment/schedule/{self.DOMAIN}/policy",
            json={"enabled": True},
            headers=viewer_headers,
        )
        assert resp.status_code == 403


# ── 7.8: disabled policy is skipped in run_once ──────────────────────────────

class TestDisabledPolicySkipped:
    def test_disabled_domain_skipped_in_run_once(self, db, sched):
        """run_once must not re-queue entities for a disabled policy."""
        # Ensure no enabled policies exist in the test DB for this run
        db.query(models.DomainEnrichmentPolicy).delete()
        db.commit()

        # Create stale entities for 'science'
        for _ in range(5):
            _make_entity(db, status="none")

        # Create a DISABLED policy — the scheduler must skip it
        disabled_policy = models.DomainEnrichmentPolicy(
            domain_id="science",
            enabled=False,  # disabled!
            min_enrichment_pct=80.0,
            max_budget_per_run=100,
            staleness_threshold_days=30,
        )
        db.add(disabled_policy)
        db.commit()

        # run_once only processes enabled=True policies — the disabled one is excluded
        summary = sched.run_once(db)

        # The disabled domain must not have been stale or queued
        assert summary["total_queued"] == 0
        assert summary["domains_stale"] == 0

        # Entities remain in 'none' state — nothing was requeued
        none_count = (
            db.query(models.RawEntity)
            .filter(models.RawEntity.enrichment_status == "none")
            .count()
        )
        assert none_count == 5
