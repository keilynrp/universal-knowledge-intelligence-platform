"""
Tests for epistemic classification engine and schema configuration.
"""
import json

import pytest

from backend import models
from backend.schema_registry import (
    DomainSchema,
    EpistemologyConfig,
    EvidenceLevel,
    Paradigm,
    ParadigmIndicators,
    SchemaRegistry,
)
from backend.analyzers.epistemic_classifier import (
    _normalize_scores,
    _score_entity,
    classify_batch,
    classify_entity,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

_PARADIGMS = [
    Paradigm(
        id="empiricist",
        label="Empiricist",
        indicators=ParadigmIndicators(
            terms=["randomized", "controlled trial", "statistical significance", "sample size"],
            document_types=["randomized controlled trial", "meta-analysis"],
            journals_affinity=["Nature", "Science"],
        ),
    ),
    Paradigm(
        id="constructivist",
        label="Constructivist",
        indicators=ParadigmIndicators(
            terms=["discourse analysis", "ethnography", "qualitative", "phenomenology"],
            document_types=["case study", "ethnographic study"],
            journals_affinity=["Social Studies of Science"],
        ),
    ),
    Paradigm(
        id="critical",
        label="Critical",
        indicators=ParadigmIndicators(
            terms=["power relations", "hegemony", "equity", "justice"],
            document_types=["commentary", "position paper"],
            journals_affinity=["Critical Inquiry"],
        ),
    ),
]


def _make_entity(db, abstract="", concepts="", doc_type="", journal="", domain="science"):
    attrs = {}
    if abstract:
        attrs["abstract"] = abstract
    if doc_type:
        attrs["document_type"] = doc_type
    if journal:
        attrs["journal"] = journal
    entity = models.RawEntity(
        primary_label="Test Entity",
        domain=domain,
        enrichment_status="completed",
        enrichment_concepts=concepts or None,
        attributes_json=json.dumps(attrs),
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


# ── Schema loading tests ─────────────────────────────────────────────────────

class TestEpistemologySchema:

    def test_science_domain_has_epistemology(self):
        reg = SchemaRegistry()
        science = reg.get_domain("science")
        assert science is not None
        assert science.epistemology is not None
        assert len(science.epistemology.paradigms) == 3
        ids = [p.id for p in science.epistemology.paradigms]
        assert "empiricist" in ids
        assert "constructivist" in ids
        assert "critical" in ids

    def test_science_domain_has_evidence_hierarchy(self):
        reg = SchemaRegistry()
        science = reg.get_domain("science")
        assert len(science.epistemology.evidence_hierarchy) == 6
        assert science.epistemology.evidence_hierarchy[0].level == 1

    def test_domain_without_epistemology_loads(self):
        """Domains without epistemology key should still load with epistemology=None."""
        reg = SchemaRegistry()
        for did in reg.domains:
            domain = reg.get_domain(did)
            if did != "science":
                assert domain.epistemology is None, f"Domain {did} should not have epistemology"

    def test_domain_schema_without_epistemology_key(self):
        """DomainSchema can be created without epistemology."""
        schema = DomainSchema(
            id="test",
            name="Test",
            description="Test domain",
            primary_entity="entity",
            attributes=[],
        )
        assert schema.epistemology is None


# ── Scoring tests ────────────────────────────────────────────────────────────

class TestScoring:

    def test_empiricist_abstract_scores_highest(self):
        scores = _score_entity(
            abstract="This randomized controlled trial evaluated the statistical significance of sample size effects.",
            concepts="Clinical Trial, Statistics",
            document_type="randomized controlled trial",
            journal="Nature",
            paradigms=_PARADIGMS,
        )
        assert scores["empiricist"] > scores["constructivist"]
        assert scores["empiricist"] > scores["critical"]

    def test_constructivist_abstract_scores_highest(self):
        scores = _score_entity(
            abstract="This qualitative ethnography uses discourse analysis and phenomenology to explore lived experience.",
            concepts="Qualitative Research, Ethnography",
            document_type="ethnographic study",
            journal="Social Studies of Science",
            paradigms=_PARADIGMS,
        )
        assert scores["constructivist"] > scores["empiricist"]
        assert scores["constructivist"] > scores["critical"]

    def test_critical_abstract_scores_highest(self):
        scores = _score_entity(
            abstract="This commentary examines power relations and hegemony in the pursuit of equity and justice in education.",
            concepts="Critical Theory, Social Justice",
            document_type="commentary",
            journal="Critical Inquiry",
            paradigms=_PARADIGMS,
        )
        assert scores["critical"] > scores["empiricist"]
        assert scores["critical"] > scores["constructivist"]

    def test_no_matches_all_zero(self):
        scores = _score_entity(
            abstract="This paper discusses the weather patterns in the tropics during summer months with no specific methodology.",
            concepts="Weather, Tropics",
            document_type="article",
            journal="Unknown Journal",
            paradigms=_PARADIGMS,
        )
        total = sum(scores.values())
        assert total == 0.0 or total < 0.01

    def test_normalization(self):
        scores = {"a": 0.6, "b": 0.3, "c": 0.1}
        normalized = _normalize_scores(scores)
        assert abs(sum(normalized.values()) - 1.0) < 0.001

    def test_normalization_all_zero(self):
        scores = {"a": 0.0, "b": 0.0}
        normalized = _normalize_scores(scores)
        assert normalized == {}


# ── classify_entity tests ────────────────────────────────────────────────────

class TestClassifyEntity:

    def test_classify_persists_profile(self, db_session):
        entity = _make_entity(
            db_session,
            abstract="A randomized controlled trial with strong statistical significance and large sample size was conducted.",
            concepts="Clinical Trial",
            doc_type="randomized controlled trial",
            journal="Nature",
        )
        result = classify_entity(db_session, entity, _PARADIGMS)
        assert result is not None
        assert result["dominant"] == "empiricist"
        assert "paradigms" in result

        # Check persistence
        attrs = json.loads(entity.attributes_json)
        assert "epistemic_profile" in attrs
        assert attrs["epistemic_profile"]["dominant"] == "empiricist"

    def test_classify_short_abstract_returns_none(self, db_session):
        entity = _make_entity(db_session, abstract="Too short")
        result = classify_entity(db_session, entity, _PARADIGMS)
        assert result is None

    def test_classify_no_abstract_returns_none(self, db_session):
        entity = _make_entity(db_session, abstract="")
        result = classify_entity(db_session, entity, _PARADIGMS)
        assert result is None

    def test_classify_no_matches_returns_none(self, db_session):
        entity = _make_entity(
            db_session,
            abstract="Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        )
        result = classify_entity(db_session, entity, _PARADIGMS)
        assert result is None

    def test_reclassification_overwrites(self, db_session):
        entity = _make_entity(
            db_session,
            abstract="A randomized controlled trial with strong statistical significance and large sample size was conducted.",
            journal="Nature",
        )
        classify_entity(db_session, entity, _PARADIGMS)

        # Re-classify with constructivist-heavy content
        attrs = json.loads(entity.attributes_json)
        attrs["abstract"] = "A qualitative ethnography using discourse analysis and phenomenology to explore lived experience and meaning."
        entity.attributes_json = json.dumps(attrs)
        db_session.commit()

        result = classify_entity(db_session, entity, _PARADIGMS)
        assert result is not None
        assert result["dominant"] == "constructivist"


# ── classify_batch tests ─────────────────────────────────────────────────────

class TestClassifyBatch:

    def test_batch_classifies_entities(self, db_session):
        _make_entity(
            db_session,
            abstract="A randomized controlled trial evaluated the statistical significance of sample size on patient outcomes.",
            domain="science",
        )
        _make_entity(
            db_session,
            abstract="This qualitative ethnography uses discourse analysis and phenomenology to explore lived experience in schools.",
            domain="science",
        )
        result = classify_batch(db_session, "science")
        assert result["classified"] >= 1

    def test_batch_skips_already_classified(self, db_session):
        entity = _make_entity(
            db_session,
            abstract="A randomized controlled trial with strong statistical significance and large sample size for evaluation.",
            domain="science",
        )
        classify_entity(db_session, entity, _PARADIGMS)
        result = classify_batch(db_session, "science")
        assert result["skipped"] >= 1

    def test_batch_unconfigured_domain(self, db_session):
        result = classify_batch(db_session, "healthcare")
        assert result.get("error") == "no_config"

    def test_batch_counts_unclassified(self, db_session):
        _make_entity(db_session, abstract="Short", domain="science")
        result = classify_batch(db_session, "science")
        assert result["unclassified"] >= 1


# ── Post-enrichment hook tests ───────────────────────────────────────────────

class TestPostEnrichmentHook:

    def test_hook_classifies_science_entity(self, db_session):
        from backend.enrichment_worker import _try_epistemic_classify

        entity = _make_entity(
            db_session,
            abstract="A randomized controlled trial evaluated the statistical significance of sample size on clinical outcomes.",
            domain="science",
        )
        _try_epistemic_classify(db_session, entity)
        db_session.commit()

        attrs = json.loads(entity.attributes_json)
        assert "epistemic_profile" in attrs
        assert attrs["epistemic_profile"]["dominant"] == "empiricist"

    def test_hook_skips_healthcare_entity(self, db_session):
        from backend.enrichment_worker import _try_epistemic_classify

        entity = _make_entity(
            db_session,
            abstract="A randomized controlled trial evaluated the statistical significance of sample size on clinical outcomes.",
            domain="healthcare",
        )
        _try_epistemic_classify(db_session, entity)
        db_session.commit()

        attrs = json.loads(entity.attributes_json)
        assert "epistemic_profile" not in attrs

    def test_hook_does_not_crash_on_error(self, db_session):
        from backend.enrichment_worker import _try_epistemic_classify

        entity = _make_entity(db_session, abstract="Short", domain="science")
        # Should not raise even though entity is unclassifiable
        _try_epistemic_classify(db_session, entity)
        db_session.commit()


# ── Endpoint tests ───────────────────────────────────────────────────────────

class TestEpistemicEndpoints:

    def test_classify_endpoint(self, client, auth_headers, db_session):
        _make_entity(
            db_session,
            abstract="A randomized controlled trial with strong statistical significance and large sample size for clinical evaluation.",
            domain="science",
        )
        resp = client.post("/analytics/epistemic/science/classify", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "classified" in data
        assert data["classified"] >= 1

    def test_classify_viewer_forbidden(self, client, viewer_headers, db_session):
        resp = client.post("/analytics/epistemic/science/classify", headers=viewer_headers)
        assert resp.status_code == 403

    def test_classify_unconfigured_domain(self, client, auth_headers):
        resp = client.post("/analytics/epistemic/healthcare/classify", headers=auth_headers)
        assert resp.status_code == 400

    def test_distribution_endpoint(self, client, auth_headers, db_session):
        entity = _make_entity(
            db_session,
            abstract="A randomized controlled trial with strong statistical significance and large sample size for clinical evaluation.",
            domain="science",
        )
        classify_entity(db_session, entity, _PARADIGMS)

        resp = client.get("/analytics/epistemic/science/distribution", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_classified"] >= 1
        assert "paradigm_counts" in data
        assert "paradigms" in data

    def test_distribution_empty(self, client, auth_headers):
        resp = client.get("/analytics/epistemic/science/distribution", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_classified"] >= 0

    def test_distribution_unconfigured_domain(self, client, auth_headers):
        resp = client.get("/analytics/epistemic/healthcare/distribution", headers=auth_headers)
        assert resp.status_code == 400


# ── OLAP integration tests ───────────────────────────────────────────────────

class TestOLAPParadigmDimension:

    def test_paradigm_in_dimensions(self, client, auth_headers, db_session):
        resp = client.get("/cube/dimensions/science", headers=auth_headers)
        assert resp.status_code == 200
        dims = resp.json()
        dim_names = [d["name"] for d in dims]
        assert "paradigm" in dim_names

    def test_paradigm_not_in_dimensions_without_config(self, client, auth_headers):
        resp = client.get("/cube/dimensions/healthcare", headers=auth_headers)
        assert resp.status_code == 200
        dims = resp.json()
        dim_names = [d["name"] for d in dims]
        assert "paradigm" not in dim_names
