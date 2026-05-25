"""Tests for genai_governance.py — Task 5.7."""
import pytest

from backend.services.genai_governance import (
    GenAIOutput,
    GovernanceViolation,
    get_governance_label,
    should_show_ai_badge,
    validate_authority_candidate,
    validate_genai_output,
    validate_mapping_suggestion,
    validate_narrative,
)


class TestMappingSuggestion:
    def test_valid_high_confidence(self):
        output = GenAIOutput(
            output_type="mapping_suggestion",
            confidence=0.95,
            evidence=["field_name_match"],
            provenance_source="gpt-4",
        )
        result = validate_mapping_suggestion(output)
        assert result.requires_review is False
        assert result.disclaimer != ""

    def test_valid_low_confidence_requires_review(self):
        output = GenAIOutput(
            output_type="mapping_suggestion",
            confidence=0.6,
            evidence=["partial_match"],
        )
        result = validate_mapping_suggestion(output)
        assert result.requires_review is True

    def test_no_confidence_raises(self):
        output = GenAIOutput(
            output_type="mapping_suggestion",
            confidence=0.0,
            evidence=["something"],
        )
        with pytest.raises(GovernanceViolation, match="confidence"):
            validate_mapping_suggestion(output)

    def test_no_evidence_raises(self):
        output = GenAIOutput(
            output_type="mapping_suggestion",
            confidence=0.8,
            evidence=[],
        )
        with pytest.raises(GovernanceViolation, match="evidence"):
            validate_mapping_suggestion(output)


class TestAuthorityCandidateGovernance:
    def test_always_requires_review(self):
        output = GenAIOutput(
            output_type="authority_candidate",
            confidence=0.99,
            provenance_source="model-x",
        )
        result = validate_authority_candidate(output)
        assert result.requires_review is True

    def test_no_confidence_raises(self):
        output = GenAIOutput(
            output_type="authority_candidate",
            confidence=0.0,
            provenance_source="model-x",
        )
        with pytest.raises(GovernanceViolation, match="confidence"):
            validate_authority_candidate(output)

    def test_no_provenance_raises(self):
        output = GenAIOutput(
            output_type="authority_candidate",
            confidence=0.8,
            provenance_source="",
        )
        with pytest.raises(GovernanceViolation, match="provenance"):
            validate_authority_candidate(output)

    def test_disclaimer_mentions_review(self):
        output = GenAIOutput(
            output_type="authority_candidate",
            confidence=0.9,
            provenance_source="skill-1",
        )
        result = validate_authority_candidate(output)
        assert "review" in result.disclaimer.lower()


class TestNarrativeGovernance:
    def test_valid_with_evidence(self):
        output = GenAIOutput(
            output_type="narrative",
            confidence=0.8,
            evidence=["entity_1", "concept_2"],
        )
        result = validate_narrative(output)
        assert result.requires_review is False
        assert "grounded" in result.disclaimer.lower()

    def test_no_evidence_raises(self):
        output = GenAIOutput(
            output_type="narrative",
            confidence=0.8,
            evidence=[],
        )
        with pytest.raises(GovernanceViolation, match="evidence"):
            validate_narrative(output)


class TestValidateGenAIOutput:
    def test_routes_mapping(self):
        output = GenAIOutput(
            output_type="mapping_suggestion",
            confidence=0.9,
            evidence=["match"],
        )
        result = validate_genai_output(output)
        assert result.disclaimer != ""

    def test_routes_authority(self):
        output = GenAIOutput(
            output_type="authority_candidate",
            confidence=0.8,
            provenance_source="skill",
        )
        result = validate_genai_output(output)
        assert result.requires_review is True

    def test_routes_narrative(self):
        output = GenAIOutput(
            output_type="narrative",
            confidence=0.7,
            evidence=["ref"],
        )
        result = validate_genai_output(output)
        assert "grounded" in result.disclaimer.lower()

    def test_unknown_type_raises(self):
        output = GenAIOutput(output_type="bogus")
        with pytest.raises(ValueError, match="Unknown"):
            validate_genai_output(output)


class TestHelpers:
    def test_always_show_badge(self):
        output = GenAIOutput(output_type="mapping_suggestion")
        assert should_show_ai_badge(output) is True

    def test_governance_label_review(self):
        output = GenAIOutput(output_type="authority_candidate", requires_review=True)
        assert get_governance_label(output) == "Review required"

    def test_governance_label_auto(self):
        output = GenAIOutput(output_type="mapping_suggestion", confidence=0.95)
        assert get_governance_label(output) == "Auto-acceptable"

    def test_governance_label_assisted(self):
        output = GenAIOutput(output_type="narrative", confidence=0.6)
        assert get_governance_label(output) == "AI-assisted"

    def test_to_dict(self):
        output = GenAIOutput(
            output_type="narrative",
            confidence=0.8,
            evidence=["ref1"],
        )
        d = output.to_dict()
        assert d["output_type"] == "narrative"
        assert d["confidence"] == 0.8
