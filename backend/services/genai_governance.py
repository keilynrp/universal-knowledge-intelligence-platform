"""GenAI Cross-Cutting Governance — Task 5.7.

Enforces governance rules for GenAI-produced outputs:
- Mapping suggestions must have confidence + evidence
- Authority candidates are candidates only (require review)
- Narratives must be grounded in governed evidence
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class GovernanceViolation(Exception):
    """Raised when GenAI output violates governance rules."""
    pass


@dataclass
class GenAIOutput:
    """A GenAI-produced output with governance metadata."""
    output_type: str  # mapping_suggestion | authority_candidate | narrative
    content: Any = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    provenance_source: str = ""  # model ID or skill ID
    requires_review: bool = False
    disclaimer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Governance thresholds
MAPPING_AUTO_ACCEPT_THRESHOLD = 0.9
MAPPING_REVIEW_THRESHOLD = 0.7
AUTHORITY_ALWAYS_REQUIRES_REVIEW = True
NARRATIVE_REQUIRES_EVIDENCE = True


def validate_mapping_suggestion(output: GenAIOutput) -> GenAIOutput:
    """Validate a GenAI mapping suggestion meets governance requirements.

    - Must have confidence score
    - Must have at least 1 evidence item
    - Low confidence → requires_review
    """
    if output.confidence <= 0:
        raise GovernanceViolation(
            "GenAI mapping suggestion must include a confidence score > 0"
        )
    if not output.evidence:
        raise GovernanceViolation(
            "GenAI mapping suggestion must include at least one evidence item"
        )

    # Determine review requirement
    if output.confidence >= MAPPING_AUTO_ACCEPT_THRESHOLD:
        output.requires_review = False
    else:
        output.requires_review = True

    output.disclaimer = "AI-assisted suggestion. Review before applying."
    return output


def validate_authority_candidate(output: GenAIOutput) -> GenAIOutput:
    """Validate a GenAI authority candidate meets governance requirements.

    - Always requires review before promotion to canonical
    - Must have confidence + source
    """
    if output.confidence <= 0:
        raise GovernanceViolation(
            "GenAI authority candidate must include a confidence score > 0"
        )
    if not output.provenance_source:
        raise GovernanceViolation(
            "GenAI authority candidate must specify provenance_source"
        )

    # Authority candidates ALWAYS require review
    output.requires_review = True
    output.disclaimer = "AI-generated candidate. Requires human review before canonical promotion."
    return output


def validate_narrative(output: GenAIOutput) -> GenAIOutput:
    """Validate a GenAI narrative meets governance requirements.

    - Must be grounded in governed evidence
    - Includes provenance disclaimer
    """
    if NARRATIVE_REQUIRES_EVIDENCE and not output.evidence:
        raise GovernanceViolation(
            "GenAI narrative must be grounded in at least one evidence reference"
        )

    output.requires_review = False  # advisory, but with disclaimer
    output.disclaimer = (
        "AI-generated narrative grounded in governed evidence. "
        "Verify claims against source data."
    )
    return output


def validate_genai_output(output: GenAIOutput) -> GenAIOutput:
    """Route validation by output type."""
    validators = {
        "mapping_suggestion": validate_mapping_suggestion,
        "authority_candidate": validate_authority_candidate,
        "narrative": validate_narrative,
    }
    validator = validators.get(output.output_type)
    if not validator:
        raise ValueError(f"Unknown GenAI output type: {output.output_type}")
    return validator(output)


def should_show_ai_badge(output: GenAIOutput) -> bool:
    """Whether the frontend should display an AI-assisted badge."""
    return True  # Always show badge for GenAI outputs


def get_governance_label(output: GenAIOutput) -> str:
    """Get the governance label for display."""
    if output.requires_review:
        return "Review required"
    if output.confidence >= MAPPING_AUTO_ACCEPT_THRESHOLD:
        return "Auto-acceptable"
    return "AI-assisted"
