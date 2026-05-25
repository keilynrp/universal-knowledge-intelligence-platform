"""Tests for decision_readout.py — Task 4.3."""
import pytest

from backend.services.decision_readout import (
    DecisionReadout,
    DecisionReadoutBuilder,
    EvidenceRef,
    Recommendation,
)


def _dashboard(**kwargs) -> dict:
    base = {
        "kpis": {
            "total_entities": 500,
            "enriched_entities": 400,
            "authority_resolved": 200,
            "avg_quality_score": 0.72,
        },
        "top_concepts": [
            {"concept": "Machine Learning"},
            {"concept": "NLP"},
            {"concept": "Deep Learning"},
        ],
        "timeline": [
            {"period": "2024-Q3", "count": 100},
            {"period": "2024-Q4", "count": 150},
        ],
        "top_entities": [
            {"label": "Harvard University"},
            {"label": "MIT"},
        ],
    }
    base.update(kwargs)
    return base


class TestCompleteDashboard:
    def test_basic_readout(self):
        builder = DecisionReadoutBuilder()
        readout = builder.build(_dashboard())
        assert readout.corpus_size == 500
        assert readout.enrichment_coverage == 0.8
        assert readout.authority_coverage == 0.4
        assert readout.quality_score == 0.72

    def test_known_signals(self):
        builder = DecisionReadoutBuilder()
        readout = builder.build(_dashboard())
        assert "Machine Learning" in readout.known_signals

    def test_emerging_signals_acceleration(self):
        builder = DecisionReadoutBuilder()
        # 150 > 100 * 1.2 = 120 → accelerating
        readout = builder.build(_dashboard())
        assert "Accelerating publication rate" in readout.emerging_signals

    def test_top_entities_as_signals(self):
        builder = DecisionReadoutBuilder()
        readout = builder.build(_dashboard())
        entity_signals = [s for s in readout.known_signals if "Key entity" in s]
        assert len(entity_signals) >= 1

    def test_confidence_high(self):
        builder = DecisionReadoutBuilder()
        readout = builder.build(_dashboard())
        # enrichment 0.8 → +0.4, authority 0.4 → +0.15, quality 0.72 → +0.2, signals → +0.1 = 0.85
        assert readout.confidence_level == "high"

    def test_audience_passed(self):
        builder = DecisionReadoutBuilder()
        readout = builder.build(_dashboard(), audience="investigator")
        assert readout.audience == "investigator"


class TestEmptyDashboard:
    def test_empty_corpus(self):
        builder = DecisionReadoutBuilder()
        readout = builder.build({"kpis": {"total_entities": 0}})
        assert readout.corpus_size == 0
        assert readout.confidence_level == "low"
        assert "No entities in corpus" in readout.missing_data
        assert len(readout.recommendations) == 1
        assert readout.recommendations[0].action == "Import data"

    def test_missing_kpis(self):
        builder = DecisionReadoutBuilder()
        readout = builder.build({})
        assert readout.corpus_size == 0


class TestPartialDashboard:
    def test_low_enrichment(self):
        builder = DecisionReadoutBuilder()
        dashboard = _dashboard()
        dashboard["kpis"]["enriched_entities"] = 100  # 20%
        readout = builder.build(dashboard)
        assert readout.enrichment_coverage == 0.2
        assert "Enrichment coverage below 50%" in readout.missing_data

    def test_no_concepts(self):
        builder = DecisionReadoutBuilder()
        dashboard = _dashboard(top_concepts=[])
        readout = builder.build(dashboard)
        assert "No concept data available" in readout.missing_data

    def test_declining_timeline(self):
        builder = DecisionReadoutBuilder()
        dashboard = _dashboard(timeline=[
            {"count": 200},
            {"count": 100},  # < 200 * 0.8
        ])
        readout = builder.build(dashboard)
        assert "Declining publication rate" in readout.emerging_signals


class TestRecommendations:
    def test_enrichment_recommendation(self):
        builder = DecisionReadoutBuilder()
        dashboard = _dashboard()
        dashboard["kpis"]["enriched_entities"] = 100
        readout = builder.build(dashboard)
        actions = [r.action for r in readout.recommendations]
        assert "Run enrichment pipeline" in actions

    def test_authority_recommendation(self):
        builder = DecisionReadoutBuilder()
        dashboard = _dashboard()
        dashboard["kpis"]["authority_resolved"] = 10  # 2%
        readout = builder.build(dashboard)
        actions = [r.action for r in readout.recommendations]
        assert "Initiate authority resolution" in actions

    def test_quality_recommendation(self):
        builder = DecisionReadoutBuilder()
        dashboard = _dashboard()
        dashboard["kpis"]["avg_quality_score"] = 0.3
        readout = builder.build(dashboard)
        actions = [r.action for r in readout.recommendations]
        assert "Review data quality issues" in actions

    def test_evidence_refs_on_recommendations(self):
        builder = DecisionReadoutBuilder()
        dashboard = _dashboard()
        dashboard["kpis"]["enriched_entities"] = 100
        readout = builder.build(dashboard)
        enrichment_rec = [r for r in readout.recommendations if "enrichment" in r.action.lower()]
        assert enrichment_rec[0].evidence_refs[0].ref_type == "enrichment"


class TestSerialization:
    def test_to_dict(self):
        builder = DecisionReadoutBuilder()
        readout = builder.build(_dashboard())
        d = readout.to_dict()
        assert d["corpus_size"] == 500
        assert isinstance(d["recommendations"], list)
        if d["recommendations"]:
            assert "action" in d["recommendations"][0]
