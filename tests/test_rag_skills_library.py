"""Tests for rag_skills_library.py — Task 4.8."""
import pytest

from backend.services.rag_skills_library import (
    CitationGrounding,
    CitationGroundingSkill,
    EvidenceGrade,
    EvidenceGradingSkill,
    StakeholderBriefing,
    StakeholderBriefingSkill,
)


class TestEvidenceGrading:
    def test_grades_returned(self):
        skill = EvidenceGradingSkill()
        evidence = [
            {"id": 1, "text": "Machine learning advances in NLP"},
            {"id": 2, "text": "Cooking recipes for pasta"},
        ]
        grades = skill.execute("machine learning NLP", evidence)
        assert len(grades) == 2
        # First should be more relevant
        assert grades[0].relevance >= grades[1].relevance

    def test_sorted_by_overall(self):
        skill = EvidenceGradingSkill()
        evidence = [
            {"id": 1, "text": "Unrelated content about geology"},
            {"id": 2, "text": "Deep learning neural networks transformer"},
        ]
        grades = skill.execute("deep learning transformer", evidence)
        assert grades[0].overall >= grades[1].overall

    def test_doi_boosts_quality(self):
        skill = EvidenceGradingSkill()
        evidence = [
            {"id": 1, "text": "Some relevant text about AI", "doi": "10.1234/test"},
        ]
        grades = skill.execute("AI", evidence)
        assert grades[0].quality >= 0.7

    def test_recency_scoring(self):
        skill = EvidenceGradingSkill()
        evidence = [
            {"id": 1, "text": "Recent AI paper", "year": 2025},
            {"id": 2, "text": "Old AI paper", "year": 2010},
        ]
        grades = skill.execute("AI paper", evidence)
        recent = next(g for g in grades if g.evidence_id == "1")
        old = next(g for g in grades if g.evidence_id == "2")
        assert recent.recency > old.recency

    def test_rationale_generated(self):
        skill = EvidenceGradingSkill()
        grades = skill.execute("test", [{"id": 1, "text": "test content"}])
        assert grades[0].rationale != ""

    def test_to_dict(self):
        grade = EvidenceGrade(evidence_id="1", relevance=0.8, overall=0.7)
        d = grade.to_dict()
        assert d["evidence_id"] == "1"

    def test_skill_metadata(self):
        assert EvidenceGradingSkill.SKILL_ID == "evidence_grading"
        assert EvidenceGradingSkill.GOVERNANCE_LEVEL == "advisory"


class TestCitationGrounding:
    def test_grounds_claims(self):
        skill = CitationGroundingSkill()
        claims = ["Machine learning improves NLP tasks"]
        evidence = [
            {"id": 1, "text": "Machine learning has shown improvements in NLP tasks recently"},
            {"id": 2, "text": "Cooking recipes are popular online"},
        ]
        groundings = skill.execute(claims, evidence)
        assert len(groundings) == 1
        assert groundings[0].confidence > 0

    def test_no_evidence_found(self):
        skill = CitationGroundingSkill()
        claims = ["Quantum computing breakthrough"]
        evidence = [{"id": 1, "text": "Cooking pasta is easy"}]
        groundings = skill.execute(claims, evidence)
        assert groundings[0].confidence == 0.0
        assert "No supporting evidence" in groundings[0].snippet

    def test_multiple_claims(self):
        skill = CitationGroundingSkill()
        claims = ["AI is growing", "NLP is a subfield"]
        evidence = [
            {"id": 1, "text": "AI is growing rapidly in industry"},
            {"id": 2, "text": "NLP is a subfield of artificial intelligence"},
        ]
        groundings = skill.execute(claims, evidence)
        assert len(groundings) == 2

    def test_snippet_truncated(self):
        skill = CitationGroundingSkill()
        long_text = "word " * 200
        claims = ["word test"]
        evidence = [{"id": 1, "text": long_text}]
        groundings = skill.execute(claims, evidence)
        if groundings[0].confidence > 0:
            assert len(groundings[0].snippet) <= 200

    def test_to_dict(self):
        g = CitationGrounding(claim="test", confidence=0.5)
        assert g.to_dict()["claim"] == "test"

    def test_skill_metadata(self):
        assert CitationGroundingSkill.SKILL_ID == "citation_grounding"
        assert CitationGroundingSkill.GOVERNANCE_LEVEL == "advisory"


class TestStakeholderBriefing:
    def test_basic_briefing(self):
        skill = StakeholderBriefingSkill()
        readout = {
            "corpus_size": 500,
            "enrichment_coverage": 0.8,
            "confidence_level": "high",
            "known_signals": ["Machine Learning", "NLP"],
            "emerging_signals": ["LLM adoption"],
            "missing_data": [],
        }
        briefing = skill.execute(readout, audience="leadership")
        assert briefing.audience == "leadership"
        assert "500" in briefing.narrative
        assert len(briefing.key_findings) > 0

    def test_empty_corpus(self):
        skill = StakeholderBriefingSkill()
        readout = {"corpus_size": 0, "confidence_level": "low"}
        briefing = skill.execute(readout)
        assert "No data" in briefing.narrative

    def test_audience_affects_narrative(self):
        skill = StakeholderBriefingSkill()
        readout = {
            "corpus_size": 100,
            "enrichment_coverage": 0.5,
            "confidence_level": "medium",
            "known_signals": ["AI"],
        }
        leadership = skill.execute(readout, audience="leadership")
        investigator = skill.execute(readout, audience="investigator")
        assert leadership.narrative != investigator.narrative

    def test_caveats_generated(self):
        skill = StakeholderBriefingSkill()
        readout = {
            "corpus_size": 100,
            "enrichment_coverage": 0.3,
            "confidence_level": "low",
            "missing_data": ["No concept data"],
        }
        briefing = skill.execute(readout)
        assert len(briefing.caveats) >= 2

    def test_evidence_refs_passed(self):
        skill = StakeholderBriefingSkill()
        readout = {"corpus_size": 10, "confidence_level": "low"}
        evidence = [{"id": 1}, {"id": 2}]
        briefing = skill.execute(readout, evidence_items=evidence)
        assert len(briefing.evidence_refs) == 2

    def test_confidence_numeric(self):
        skill = StakeholderBriefingSkill()
        readout = {"corpus_size": 100, "confidence_level": "high"}
        briefing = skill.execute(readout)
        assert briefing.confidence == 0.85

    def test_to_dict(self):
        b = StakeholderBriefing(audience="leadership", narrative="test")
        assert b.to_dict()["audience"] == "leadership"

    def test_skill_metadata(self):
        assert StakeholderBriefingSkill.SKILL_ID == "stakeholder_briefing"
        assert StakeholderBriefingSkill.GOVERNANCE_LEVEL == "advisory"
