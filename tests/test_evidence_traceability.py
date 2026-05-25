"""Tests for evidence_traceability.py — Task 4.6."""
import pytest

from backend.services.evidence_traceability import (
    EvidenceItem,
    EvidencePanel,
    EvidenceTraceabilityService,
    EvidenceType,
)


class TestBuildPanels:
    def test_basic_panel(self):
        svc = EvidenceTraceabilityService()
        recs = [{"action": "Review data quality issues", "evidence_refs": [
            {"ref_type": "quality", "label": "Score", "value": "0.4"}
        ]}]
        panels = svc.build_panels(recs)
        assert len(panels) == 1
        assert panels[0].recommendation_text == "Review data quality issues"
        assert len(panels[0].items) >= 1

    def test_evidence_refs_extracted(self):
        svc = EvidenceTraceabilityService()
        recs = [{"action": "Do something", "evidence_refs": [
            {"ref_type": "entity", "label": "Entity A", "value": "123"},
            {"ref_type": "benchmark", "label": "Rule X", "value": "pass"},
        ]}]
        panels = svc.build_panels(recs)
        assert len(panels[0].items) == 2
        types = {i.ref_type for i in panels[0].items}
        assert "entity" in types
        assert "benchmark" in types

    def test_concept_evidence_added(self):
        svc = EvidenceTraceabilityService()
        recs = [{"action": "Enrich entities to extract concepts", "evidence_refs": []}]
        concepts = [{"concept": "AI", "count": 5}, {"concept": "NLP", "count": 3}]
        panels = svc.build_panels(recs, concepts=concepts)
        concept_items = [i for i in panels[0].items if i.ref_type == EvidenceType.CONCEPT]
        assert len(concept_items) == 2

    def test_quality_evidence_added(self):
        svc = EvidenceTraceabilityService()
        recs = [{"action": "Review data quality", "evidence_refs": []}]
        panels = svc.build_panels(recs, quality_metrics={"overall_score": 0.3})
        quality_items = [i for i in panels[0].items if i.ref_type == EvidenceType.QUALITY]
        assert len(quality_items) == 1

    def test_enrichment_evidence_added(self):
        svc = EvidenceTraceabilityService()
        recs = [{"action": "Run enrichment pipeline", "evidence_refs": []}]
        panels = svc.build_panels(recs, quality_metrics={"enrichment_coverage": 0.3})
        enr_items = [i for i in panels[0].items if i.ref_type == EvidenceType.ENRICHMENT]
        assert len(enr_items) == 1
        assert "30%" in enr_items[0].value

    def test_fallback_when_no_evidence(self):
        svc = EvidenceTraceabilityService()
        recs = [{"action": "Unknown action XYZ", "evidence_refs": []}]
        panels = svc.build_panels(recs)
        assert panels[0].fallback_copy != ""
        assert len(panels[0].items) == 0

    def test_multiple_recommendations(self):
        svc = EvidenceTraceabilityService()
        recs = [
            {"action": "Action A", "evidence_refs": [{"ref_type": "entity", "label": "X"}]},
            {"action": "Action B", "evidence_refs": []},
        ]
        panels = svc.build_panels(recs)
        assert len(panels) == 2


class TestBuildAppendix:
    def test_basic_appendix(self):
        svc = EvidenceTraceabilityService()
        recs = [{"action": "Review quality", "evidence_refs": [
            {"ref_type": "quality", "label": "Score", "value": "0.5"}
        ]}]
        panels = svc.build_panels(recs, quality_metrics={"overall_score": 0.5})
        appendix = svc.build_appendix(panels)
        assert appendix["title"] == "Evidence Appendix"
        assert appendix["total_references"] > 0
        assert len(appendix["sections"]) >= 1

    def test_empty_panels_excluded(self):
        svc = EvidenceTraceabilityService()
        panel = EvidencePanel(recommendation_id="x", items=[])
        appendix = svc.build_appendix([panel])
        assert appendix["total_references"] == 0
        assert len(appendix["sections"]) == 0


class TestSerialization:
    def test_evidence_item_to_dict(self):
        item = EvidenceItem(ref_type="entity", label="Test", confidence=0.9)
        d = item.to_dict()
        assert d["ref_type"] == "entity"
        assert d["confidence"] == 0.9

    def test_panel_to_dict(self):
        panel = EvidencePanel(
            recommendation_id="rec_0",
            items=[EvidenceItem(ref_type="quality", label="Score")],
        )
        d = panel.to_dict()
        assert d["has_evidence"] is True
        assert len(d["items"]) == 1

    def test_panel_no_evidence_to_dict(self):
        panel = EvidencePanel(recommendation_id="rec_0", items=[], fallback_copy="N/A")
        d = panel.to_dict()
        assert d["has_evidence"] is False
