"""Sprint 72 — Entity Quality Score tests."""
import pytest
from backend.quality_scorer import score_entity, compute_all
from backend import models


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_entity(**kwargs) -> models.UniversalEntity:
    """Build a transient UniversalEntity without DB. Assign an id manually."""
    e = models.UniversalEntity()
    e.id = kwargs.get("id", 1)
    e.primary_label = kwargs.get("primary_label", None)
    e.secondary_label = kwargs.get("secondary_label", None)
    e.canonical_id = kwargs.get("canonical_id", None)
    e.entity_type = kwargs.get("entity_type", None)
    e.enrichment_status = kwargs.get("enrichment_status", "none")
    e.enrichment_doi = kwargs.get("enrichment_doi", None)
    e.quality_score = kwargs.get("quality_score", None)
    e.attributes_json = kwargs.get("attributes_json", None)
    return e


# ── Unit tests for the scorer ─────────────────────────────────────────────────

class TestQualityScorer:
    def test_empty_entity_scores_zero(self):
        e = _make_entity()
        score, _ = score_entity(e, set(), set())
        assert score == 0.0

    def test_primary_label_contributes(self):
        e = _make_entity(primary_label="Test Entity")
        score, bd = score_entity(e, set(), set())
        assert score == pytest.approx(0.15, abs=1e-4)
        assert bd["primary_label"]["present"] is True

    def test_full_fields_no_enrichment(self):
        e = _make_entity(
            primary_label="Label",
            secondary_label="Secondary",
            canonical_id="ABC123",
            entity_type="paper",
        )
        score, _ = score_entity(e, set(), set())
        # 0.15 + 0.10 + 0.10 + 0.05 = 0.40
        assert score == pytest.approx(0.40, abs=1e-4)

    def test_enrichment_completed_adds_score(self):
        e = _make_entity(
            primary_label="Label",
            secondary_label="Secondary",
            canonical_id="ABC123",
            entity_type="paper",
            enrichment_status="completed",
        )
        score, _ = score_entity(e, set(), set())
        # 0.40 + 0.25 = 0.65
        assert score == pytest.approx(0.65, abs=1e-4)

    def test_doi_bonus_only_when_completed(self):
        # DOI present but enrichment_status != "completed" → no bonus
        e = _make_entity(enrichment_doi="10.1234/test")
        score, bd = score_entity(e, set(), set())
        assert bd["enrichment_doi"]["present"] is False
        assert bd["enrichment_doi"]["contribution"] == 0.0

    def test_doi_bonus_when_completed(self):
        e = _make_entity(enrichment_status="completed", enrichment_doi="10.1234/test")
        score, bd = score_entity(e, set(), set())
        assert bd["enrichment_doi"]["present"] is True
        assert bd["enrichment_doi"]["contribution"] == pytest.approx(0.05, abs=1e-4)

    def test_score_capped_at_one(self):
        e = _make_entity(
            primary_label="Label",
            secondary_label="Secondary",
            canonical_id="ABC123",
            entity_type="paper",
            enrichment_status="completed",
            enrichment_doi="10.1234/test",
        )
        # Add authority + relationships → would be 1.0
        score, _ = score_entity(e, {"Label"}, {1})
        assert score <= 1.0

    def test_score_is_float(self):
        e = _make_entity(primary_label="Label")
        score, _ = score_entity(e, set(), set())
        assert isinstance(score, float)

    def test_authority_dimension(self):
        e = _make_entity(primary_label="KnownLabel")
        score, bd = score_entity(e, {"KnownLabel"}, set())
        assert bd["authority_confirmed"]["confirmed"] is True
        assert bd["authority_confirmed"]["mode"] == "label_match"
        assert bd["authority_confirmed"]["contribution"] == pytest.approx(0.20, abs=1e-4)

    def test_publication_authority_uses_canonical_authors(self):
        import json as _json
        # A publication's own label (a title) never matches an author record; the
        # authority signal comes from attrs["canonical_authors"] instead.
        e = _make_entity(
            primary_label="Some Paper Title", entity_type="publication",
            attributes_json=_json.dumps({"canonical_authors": {"Ada Lovelace": {"source": "orcid"}}}),
        )
        score, bd = score_entity(e, set(), set())  # not in confirmed_labels
        assert bd["authority_confirmed"]["confirmed"] is True
        assert bd["authority_confirmed"]["mode"] == "canonical_authors"
        assert bd["authority_confirmed"]["contribution"] == pytest.approx(0.20, abs=1e-4)

    def test_publication_without_canonical_authors_scores_zero(self):
        # Even if the title happened to be in confirmed_labels, publications ignore
        # label-match and require canonical_authors.
        e = _make_entity(
            primary_label="Some Paper Title", entity_type="publication",
            attributes_json='{"authors": "x"}',
        )
        score, bd = score_entity(e, {"Some Paper Title"}, set())
        assert bd["authority_confirmed"]["confirmed"] is False
        assert bd["authority_confirmed"]["contribution"] == 0.0

    def test_relationship_dimension(self):
        e = _make_entity(id=42)
        score, bd = score_entity(e, set(), {42})
        assert bd["relationships"]["has_relationships"] is True
        assert bd["relationships"]["contribution"] == pytest.approx(0.10, abs=1e-4)


# ── API: bulk compute ─────────────────────────────────────────────────────────

class TestComputeEndpoint:
    def test_requires_admin_not_editor(self, client, editor_headers):
        res = client.post("/entities/quality/compute", headers=editor_headers)
        assert res.status_code == 403

    def test_viewer_blocked(self, client, viewer_headers):
        res = client.post("/entities/quality/compute", headers=viewer_headers)
        assert res.status_code == 403

    def test_admin_can_compute(self, client, auth_headers, db_session):
        # Seed an entity
        e = models.UniversalEntity(primary_label="Test", enrichment_status="none")
        db_session.add(e)
        db_session.commit()

        res = client.post("/entities/quality/compute", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "computed" in data
        assert data["computed"] >= 1

    def test_compute_persists_scores(self, client, auth_headers, db_session):
        e = models.UniversalEntity(primary_label="Persist", enrichment_status="none")
        db_session.add(e)
        db_session.commit()
        entity_id = e.id

        client.post("/entities/quality/compute", headers=auth_headers)

        db_session.expire_all()
        refreshed = db_session.query(models.UniversalEntity).filter_by(id=entity_id).first()
        assert refreshed is not None
        assert refreshed.quality_score is not None
        assert isinstance(refreshed.quality_score, float)


# ── API: quality breakdown ────────────────────────────────────────────────────

class TestQualityBreakdown:
    def test_requires_auth(self, client):
        # Create a dummy entity id=999 (likely missing) — should get 401 without token
        res = client.get("/entities/1/quality")
        assert res.status_code in (401, 403)

    def test_returns_breakdown(self, client, auth_headers, db_session):
        e = models.UniversalEntity(primary_label="Breakdown", enrichment_status="none")
        db_session.add(e)
        db_session.commit()
        entity_id = e.id

        res = client.get(f"/entities/{entity_id}/quality", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "score" in data
        assert "breakdown" in data
        assert data["entity_id"] == entity_id

    def test_404_for_missing_entity(self, client, auth_headers):
        res = client.get("/entities/999999/quality", headers=auth_headers)
        assert res.status_code == 404

    def test_breakdown_has_all_dimensions(self, client, auth_headers, db_session):
        e = models.UniversalEntity(
            primary_label="DimCheck",
            secondary_label="Secondary",
            canonical_id="ID123",
            entity_type="paper",
            enrichment_status="none",
        )
        db_session.add(e)
        db_session.commit()
        entity_id = e.id

        res = client.get(f"/entities/{entity_id}/quality", headers=auth_headers)
        assert res.status_code == 200
        breakdown = res.json()["breakdown"]
        # Check expected dimension keys are present
        assert "primary_label" in breakdown
        assert "enrichment_status" in breakdown
        assert "authority_confirmed" in breakdown
        assert "relationships" in breakdown


# ── API: entities quality filter & sort ──────────────────────────────────────

class TestEntitiesQualityFilter:
    def test_min_quality_filter(self, client, auth_headers, db_session):
        # Create entities and compute scores
        e1 = models.UniversalEntity(primary_label="HighQ", enrichment_status="none")
        e2 = models.UniversalEntity(primary_label=None, enrichment_status="none")
        db_session.add_all([e1, e2])
        db_session.commit()

        # Manually set scores
        e1.quality_score = 0.8
        e2.quality_score = 0.1
        db_session.commit()

        res = client.get("/entities?min_quality=0.7", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        # All returned entities should have quality >= 0.7
        for entity in data:
            assert entity.get("quality_score", 0) >= 0.7

    def test_min_quality_filter_computes_missing_scores(self, client, auth_headers, db_session):
        e1 = models.UniversalEntity(
            primary_label="High Missing Score",
            secondary_label="Research Office",
            canonical_id="AUTH:high-missing-score",
            entity_type="organization",
            enrichment_status="completed",
            enrichment_doi="10.1000/high",
            quality_score=None,
        )
        e2 = models.UniversalEntity(
            primary_label="Low Missing Score",
            enrichment_status="none",
            quality_score=None,
        )
        db_session.add_all([e1, e2])
        db_session.flush()
        db_session.add(
            models.AuthorityRecord(
                field_name="primary_label",
                original_value="High Missing Score",
                authority_source="ror",
                authority_id="https://ror.org/high",
                canonical_label="High Missing Score",
                confidence=1.0,
                status="confirmed",
            )
        )
        db_session.commit()

        res = client.get("/entities?min_quality=0.7", headers=auth_headers)
        assert res.status_code == 200
        labels = {entity["primary_label"] for entity in res.json()}
        assert "High Missing Score" in labels
        assert "Low Missing Score" not in labels
        high_result = next(entity for entity in res.json() if entity["primary_label"] == "High Missing Score")
        assert high_result["quality_score"] >= 0.7

    def test_sort_by_quality_desc(self, client, auth_headers, db_session):
        e1 = models.UniversalEntity(primary_label="A", enrichment_status="none", quality_score=0.2)
        e2 = models.UniversalEntity(primary_label="B", enrichment_status="none", quality_score=0.9)
        e3 = models.UniversalEntity(primary_label="C", enrichment_status="none", quality_score=0.5)
        db_session.add_all([e1, e2, e3])
        db_session.commit()

        res = client.get("/entities?sort_by=quality_score&order=desc", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        scores = [e.get("quality_score") for e in data if e.get("quality_score") is not None]
        assert scores == sorted(scores, reverse=True)

    def test_invalid_sort_by_rejected(self, client, auth_headers):
        res = client.get("/entities?sort_by=invalid_field", headers=auth_headers)
        assert res.status_code == 422


# ── Stats and dashboard quality fields ───────────────────────────────────────

class TestStatsQuality:
    def test_stats_includes_quality(self, client, auth_headers, db_session):
        res = client.get("/stats", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "quality" in data
        assert "average" in data["quality"]
        assert "distribution" in data["quality"]

    def test_dashboard_includes_quality(self, client, auth_headers, db_session):
        res = client.get("/dashboard/summary", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "quality" in data
        assert "average" in data["quality"]
        assert "distribution" in data["quality"]

    def test_quality_distribution_keys(self, client, auth_headers, db_session):
        e = models.UniversalEntity(primary_label="Scored", enrichment_status="none", quality_score=0.8)
        db_session.add(e)
        db_session.commit()

        res = client.get("/stats", headers=auth_headers)
        data = res.json()
        dist = data["quality"]["distribution"]
        assert "high" in dist
        assert "medium" in dist
        assert "low" in dist
        assert "unscored" in dist


# ── Gap detector ──────────────────────────────────────────────────────────────

class TestGapDetectorQuality:
    def test_gap_check_present(self, client, auth_headers, db_session):
        res = client.get("/artifacts/gaps/default", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        gap_checks = [g["check"] if "check" in g else g.get("category", "") for g in data["gaps"]]
        # The category field should have "quality"
        categories = [g.get("category", "") for g in data["gaps"]]
        assert "quality" in categories

    def test_gap_no_scores_is_warning(self, client, auth_headers, db_session):
        # With no quality scores computed, should get warning
        e = models.UniversalEntity(primary_label="NoScore", enrichment_status="none")
        db_session.add(e)
        db_session.commit()

        res = client.get("/artifacts/gaps/default", headers=auth_headers)
        assert res.status_code == 200
        gaps = res.json()["gaps"]
        quality_gap = next((g for g in gaps if g.get("category") == "quality"), None)
        assert quality_gap is not None
        # No scored entities → warning severity
        assert quality_gap["severity"] in ("warning", "ok")

    def test_gap_low_quality_critical(self, client, auth_headers, db_session):
        # Seed entities with low scores (>30% low quality → critical)
        for i in range(10):
            db_session.add(models.UniversalEntity(
                primary_label=f"Low{i}",
                enrichment_status="none",
                quality_score=0.1,  # all low
            ))
        db_session.commit()

        res = client.get("/artifacts/gaps/default", headers=auth_headers)
        assert res.status_code == 200
        gaps = res.json()["gaps"]
        quality_gap = next((g for g in gaps if g.get("category") == "quality"), None)
        assert quality_gap is not None
        assert quality_gap["severity"] == "critical"
