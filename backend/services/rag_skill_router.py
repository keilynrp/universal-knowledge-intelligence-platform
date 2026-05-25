"""RAG Skill Router — Task 2.8.

Routes incoming RAG queries to the appropriate skill or direct answer,
applying role-based eligibility and domain scoping.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.services.rag_skill_registry import GovernanceLevel, RAGSkillRegistry, SkillDefinition

logger = logging.getLogger(__name__)


class RoutingDecision(str, Enum):
    DIRECT_ANSWER = "direct_answer"
    SINGLE_SKILL = "single_skill"
    PLAN_CANDIDATE = "plan_candidate"
    POLICY_BLOCK = "policy_block"


# Viewer can only use advisory skills
_ROLE_GOVERNANCE_MAP: dict[str, set[GovernanceLevel]] = {
    "viewer": {GovernanceLevel.ADVISORY},
    "editor": {GovernanceLevel.ADVISORY, GovernanceLevel.REVIEW_REQUIRED},
    "admin": {GovernanceLevel.ADVISORY, GovernanceLevel.REVIEW_REQUIRED, GovernanceLevel.GOVERNED_WRITE_CANDIDATE},
    "super_admin": {GovernanceLevel.ADVISORY, GovernanceLevel.REVIEW_REQUIRED, GovernanceLevel.GOVERNED_WRITE_CANDIDATE},
}


@dataclass
class RouterInput:
    """Input contract for the skill router."""
    query: str
    evidence_summary: str = ""
    domain: str | None = None
    user_role: str = "viewer"
    tenant: str | None = None
    active_flags: set[str] = field(default_factory=set)


@dataclass
class RouterResult:
    """Output of a routing decision."""
    decision: RoutingDecision
    skill: SkillDefinition | None = None
    confidence: float = 0.0
    policy_reason: str = ""
    audit_entry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "skill_id": self.skill.skill_id if self.skill else None,
            "confidence": self.confidence,
            "policy_reason": self.policy_reason,
            "audit_entry": self.audit_entry,
        }


class RAGSkillRouter:
    """Routes queries to skills based on evidence, role, and domain."""

    def __init__(self, registry: RAGSkillRegistry) -> None:
        self._registry = registry

    def route(self, input: RouterInput) -> RouterResult:
        """Determine routing decision for a query."""
        audit: dict[str, Any] = {
            "query_preview": input.query[:100],
            "domain": input.domain,
            "user_role": input.user_role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 1. Get available skills for context
        available = self._registry.available_for(
            tenant=input.tenant,
            domain=input.domain,
            active_flags=input.active_flags,
        )

        # 2. Filter by role eligibility
        allowed_governance = _ROLE_GOVERNANCE_MAP.get(input.user_role, {GovernanceLevel.ADVISORY})
        eligible = [s for s in available if s.governance_level in allowed_governance]

        audit["available_count"] = len(available)
        audit["eligible_count"] = len(eligible)

        # 3. If no evidence → direct answer
        if not input.evidence_summary.strip():
            audit["reason"] = "no_evidence_summary"
            return RouterResult(
                decision=RoutingDecision.DIRECT_ANSWER,
                confidence=0.5,
                policy_reason="No evidence context provided; using direct RAG",
                audit_entry=audit,
            )

        # 4. Try to match a skill
        best_skill = self._find_best_skill(input, eligible)

        if best_skill is None:
            audit["reason"] = "no_matching_skill"
            return RouterResult(
                decision=RoutingDecision.DIRECT_ANSWER,
                confidence=0.6,
                policy_reason="No matching skill found; falling back to direct RAG",
                audit_entry=audit,
            )

        # 5. Check governance policy
        if best_skill.governance_level == GovernanceLevel.GOVERNED_WRITE_CANDIDATE:
            if input.user_role not in ("admin", "super_admin"):
                audit["reason"] = "policy_block_governance"
                audit["blocked_skill"] = best_skill.skill_id
                return RouterResult(
                    decision=RoutingDecision.POLICY_BLOCK,
                    skill=best_skill,
                    confidence=0.9,
                    policy_reason=f"Skill '{best_skill.skill_id}' requires admin role for governed writes",
                    audit_entry=audit,
                )

        # 6. Determine if single skill or plan
        if best_skill.governance_level == GovernanceLevel.REVIEW_REQUIRED:
            audit["reason"] = "plan_candidate_review_required"
            return RouterResult(
                decision=RoutingDecision.PLAN_CANDIDATE,
                skill=best_skill,
                confidence=0.8,
                policy_reason=f"Skill '{best_skill.skill_id}' requires review before execution",
                audit_entry=audit,
            )

        audit["reason"] = "skill_matched"
        return RouterResult(
            decision=RoutingDecision.SINGLE_SKILL,
            skill=best_skill,
            confidence=0.85,
            policy_reason=f"Routed to skill '{best_skill.skill_id}'",
            audit_entry=audit,
        )

    def _find_best_skill(
        self,
        input: RouterInput,
        eligible: list[SkillDefinition],
    ) -> SkillDefinition | None:
        """Simple keyword-based skill matching against the query."""
        if not eligible:
            return None

        query_lower = input.query.lower()
        scores: list[tuple[float, SkillDefinition]] = []

        for skill in eligible:
            score = 0.0
            # Match skill_id keywords
            skill_words = set(skill.skill_id.replace("_", " ").split())
            desc_words = set(skill.description.lower().split())
            query_words = set(query_lower.split())

            overlap = skill_words & query_words
            desc_overlap = desc_words & query_words
            score += len(overlap) * 0.3
            score += len(desc_overlap) * 0.1

            # Boost if evidence types match
            if input.evidence_summary:
                for ev_type in skill.allowed_evidence_types:
                    if ev_type in input.evidence_summary.lower():
                        score += 0.2

            if score > 0:
                scores.append((score, skill))

        if not scores:
            return None

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]
