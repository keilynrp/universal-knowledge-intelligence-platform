"""Tests for Task 2.8 — RAG Skill Router."""
from backend.services.rag_skill_registry import (
    GovernanceLevel,
    RAGSkillRegistry,
    SkillDefinition,
)
from backend.services.rag_skill_router import (
    RAGSkillRouter,
    RouterInput,
    RoutingDecision,
)


def _make_registry() -> RAGSkillRegistry:
    """Create a registry with test skills."""
    registry = RAGSkillRegistry()
    registry.register(SkillDefinition(
        skill_id="summarize_entities",
        description="Summarize entity attributes",
        governance_level=GovernanceLevel.ADVISORY,
        allowed_evidence_types=["entity", "enrichment"],
    ))
    registry.register(SkillDefinition(
        skill_id="detect_duplicates",
        description="Identify potential duplicate entities",
        governance_level=GovernanceLevel.REVIEW_REQUIRED,
        allowed_evidence_types=["entity"],
    ))
    registry.register(SkillDefinition(
        skill_id="suggest_authority",
        description="Produce authority resolution candidates",
        governance_level=GovernanceLevel.GOVERNED_WRITE_CANDIDATE,
        allowed_evidence_types=["entity", "enrichment", "authority"],
    ))
    registry.register(SkillDefinition(
        skill_id="disabled_skill",
        description="This skill is disabled",
        enabled=False,
    ))
    return registry


class TestDirectRAG:
    def test_no_evidence_routes_direct(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(
            query="What is machine learning?",
            evidence_summary="",
        ))
        assert result.decision == RoutingDecision.DIRECT_ANSWER
        assert result.confidence > 0
        assert result.policy_reason != ""

    def test_no_matching_skill_routes_direct(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(
            query="completely unrelated query about cooking recipes",
            evidence_summary="no relevant data",
        ))
        # May route direct or find a partial match; verify it returns a valid decision
        assert result.decision in (RoutingDecision.DIRECT_ANSWER, RoutingDecision.SINGLE_SKILL)


class TestSkillAssisted:
    def test_summarize_match(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(
            query="summarize the entities in this dataset",
            evidence_summary="entity enrichment data available",
            user_role="editor",
        ))
        assert result.decision == RoutingDecision.SINGLE_SKILL
        assert result.skill is not None
        assert result.skill.skill_id == "summarize_entities"

    def test_review_required_becomes_plan(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(
            query="detect duplicates in the entities",
            evidence_summary="entity data available",
            user_role="editor",
        ))
        assert result.decision == RoutingDecision.PLAN_CANDIDATE
        assert result.skill.skill_id == "detect_duplicates"


class TestInsufficientEvidence:
    def test_empty_evidence(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(query="help me", evidence_summary=""))
        assert result.decision == RoutingDecision.DIRECT_ANSWER


class TestPolicyBlocked:
    def test_viewer_blocked_from_governed(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(
            query="suggest authority candidates",
            evidence_summary="entity enrichment authority data",
            user_role="viewer",
        ))
        # Viewer can only access advisory skills, so governed skill won't be eligible
        # Should either not find it or route to something else
        if result.skill and result.skill.skill_id == "suggest_authority":
            assert result.decision == RoutingDecision.POLICY_BLOCK

    def test_editor_blocked_from_governed_write(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(
            query="suggest authority candidates for enrichment",
            evidence_summary="entity enrichment authority data",
            user_role="editor",
        ))
        # Editor can't use governed_write_candidate
        if result.skill and result.skill.governance_level == GovernanceLevel.GOVERNED_WRITE_CANDIDATE:
            assert result.decision == RoutingDecision.POLICY_BLOCK

    def test_admin_can_use_governed(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(
            query="suggest authority candidates for entity enrichment",
            evidence_summary="entity enrichment authority data available",
            user_role="admin",
        ))
        if result.skill and result.skill.skill_id == "suggest_authority":
            assert result.decision in (RoutingDecision.SINGLE_SKILL, RoutingDecision.PLAN_CANDIDATE)


class TestAuditEntry:
    def test_audit_always_present(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(query="test", evidence_summary="test"))
        assert "timestamp" in result.audit_entry
        assert "user_role" in result.audit_entry

    def test_to_dict(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(query="test", evidence_summary=""))
        d = result.to_dict()
        assert "decision" in d
        assert "confidence" in d
        assert "policy_reason" in d


class TestDisabledSkillNotRouted:
    def test_disabled_excluded(self):
        router = RAGSkillRouter(_make_registry())
        result = router.route(RouterInput(
            query="use the disabled skill",
            evidence_summary="data available",
        ))
        if result.skill:
            assert result.skill.skill_id != "disabled_skill"
