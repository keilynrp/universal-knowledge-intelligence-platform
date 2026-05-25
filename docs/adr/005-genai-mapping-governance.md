# ADR-005: GenAI Mapping Assistance Governance

## Status

Accepted

## Date

2026-05-24

## Context

AI models can suggest field mappings, generate authority candidates, and produce narrative summaries. Without governance, AI outputs could silently enter the canonical layer without evidence, confidence tracking, or human review — violating data quality principles.

## Decision

All GenAI outputs are governed by type-specific validation (`backend/services/genai_governance.py`):

1. **Mapping Suggestions** — Must include confidence score (>0) and at least one evidence reference. Low confidence (<0.8) forces `review_required` status. Zero confidence or empty evidence raises `GovernanceViolation`.
2. **Authority Candidates** — Always require human review regardless of confidence. Must include provenance source identifier.
3. **Narratives** — Must be grounded in governed evidence (non-empty evidence list). Disclaimer text is always attached.

Cross-cutting rules:
- `should_show_ai_badge()` always returns True — all AI outputs are visibly disclosed.
- `get_governance_label()` classifies outputs as "Review required", "Auto-acceptable", or "AI-assisted".
- No GenAI output bypasses the existing mapping suggestion or authority promotion pipelines.

## Consequences

- **Easier:** AI assistance accelerates mapping and resolution without compromising governance; consistent disclosure builds user trust.
- **Harder:** Every AI integration point must call validation before persistence; new output types require new validator functions.

## References

- Spec: `genai-cross-cutting-capability` (ukip-enterprise-architecture-governance)
- Implementation: `backend/services/genai_governance.py`
- Tests: `tests/test_genai_governance.py` (18 tests)
