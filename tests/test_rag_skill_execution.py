"""Tests for Task 2.9 — RAG Skill Execution."""
import time

from backend.services.rag_skill_registry import GovernanceLevel, SkillDefinition
from backend.services.rag_skill_execution import (
    InvocationStatus,
    RAGSkillExecutor,
    ReviewStatus,
)


def _advisory_skill() -> SkillDefinition:
    return SkillDefinition(
        skill_id="test_summarize",
        governance_level=GovernanceLevel.ADVISORY,
        input_schema={
            "type": "object",
            "required": ["entity_ids"],
            "properties": {
                "entity_ids": {"type": "array"},
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
            },
        },
        timeout_ms=5000,
    )


def _review_skill() -> SkillDefinition:
    return SkillDefinition(
        skill_id="test_review",
        governance_level=GovernanceLevel.REVIEW_REQUIRED,
        timeout_ms=5000,
    )


class TestCompletedInvocation:
    def test_successful_execution(self):
        executor = RAGSkillExecutor()
        executor.register_handler("test_summarize", lambda inp: {"summary": "Test summary"})

        result = executor.execute(
            _advisory_skill(),
            query_id="q1",
            input_evidence={"entity_ids": [1, 2, 3]},
        )
        assert result.status == InvocationStatus.COMPLETED
        assert result.output["summary"] == "Test summary"
        assert result.timing_ms >= 0
        assert result.review_status == ReviewStatus.NOT_REQUIRED


class TestFailedInvocation:
    def test_handler_raises(self):
        executor = RAGSkillExecutor()
        executor.register_handler("test_summarize", lambda inp: (_ for _ in ()).throw(ValueError("boom")))

        result = executor.execute(
            _advisory_skill(),
            query_id="q2",
            input_evidence={"entity_ids": [1]},
        )
        assert result.status == InvocationStatus.FAILED
        assert "boom" in result.error_message

    def test_missing_handler(self):
        executor = RAGSkillExecutor()
        result = executor.execute(
            _advisory_skill(),
            query_id="q3",
            input_evidence={"entity_ids": [1]},
        )
        assert result.status == InvocationStatus.FAILED
        assert "No handler" in result.error_message

    def test_input_validation_failure(self):
        executor = RAGSkillExecutor()
        executor.register_handler("test_summarize", lambda inp: {"summary": "ok"})

        result = executor.execute(
            _advisory_skill(),
            query_id="q4",
            input_evidence={},  # missing required entity_ids
        )
        assert result.status == InvocationStatus.FAILED
        assert "entity_ids" in result.error_message


class TestTimedOutInvocation:
    def test_timeout_detection(self):
        skill = SkillDefinition(
            skill_id="slow_skill",
            timeout_ms=1,  # 1ms timeout
        )
        executor = RAGSkillExecutor()

        def slow_handler(inp):
            time.sleep(0.01)  # 10ms, exceeds 1ms timeout
            return {"result": "done"}

        executor.register_handler("slow_skill", slow_handler)
        result = executor.execute(skill, query_id="q5", input_evidence={})
        assert result.status == InvocationStatus.TIMED_OUT


class TestReviewRequiredInvocation:
    def test_review_required_status(self):
        executor = RAGSkillExecutor()
        executor.register_handler("test_review", lambda inp: {"result": "needs review"})

        result = executor.execute(
            _review_skill(),
            query_id="q6",
            input_evidence={},
        )
        assert result.status == InvocationStatus.COMPLETED
        assert result.review_status == ReviewStatus.PENDING_REVIEW


class TestFallback:
    def test_fallback_on_failure(self):
        executor = RAGSkillExecutor()
        # No handler registered → will fail
        result = executor.execute_with_fallback(
            _advisory_skill(),
            query_id="q7",
            input_evidence={"entity_ids": [1]},
            fallback_fn=lambda inp: {"answer": "fallback response"},
        )
        assert result.output["answer"] == "fallback response"
        assert "fell back" in result.error_message.lower() or "fallback" in result.error_message.lower()

    def test_no_fallback_on_success(self):
        executor = RAGSkillExecutor()
        executor.register_handler("test_summarize", lambda inp: {"summary": "ok"})

        result = executor.execute_with_fallback(
            _advisory_skill(),
            query_id="q8",
            input_evidence={"entity_ids": [1]},
            fallback_fn=lambda inp: {"answer": "should not be called"},
        )
        assert result.status == InvocationStatus.COMPLETED
        assert result.output["summary"] == "ok"


class TestAuditLog:
    def test_audit_entries_recorded(self):
        executor = RAGSkillExecutor()
        executor.register_handler("test_summarize", lambda inp: {"summary": "ok"})

        executor.execute(_advisory_skill(), "q9", {"entity_ids": [1]})
        executor.execute(_advisory_skill(), "q10", {"entity_ids": [2]})

        assert len(executor.audit_log) == 2
        assert executor.audit_log[0].query_id == "q9"
        assert executor.audit_log[1].query_id == "q10"


class TestInvocationSerialization:
    def test_to_dict(self):
        executor = RAGSkillExecutor()
        executor.register_handler("test_summarize", lambda inp: {"summary": "ok"})

        result = executor.execute(_advisory_skill(), "q11", {"entity_ids": [1]})
        d = result.to_dict()
        assert d["status"] == "completed"
        assert d["review_status"] == "not_required"
        assert d["skill_id"] == "test_summarize"
