"""RAG Skill Execution Service — Task 2.9.

Executes a routed skill invocation, validates input/output schemas,
enforces timeouts, and records audit events.
"""
from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from backend.services.rag_skill_registry import GovernanceLevel, SkillDefinition

logger = logging.getLogger(__name__)


class InvocationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    POLICY_BLOCKED = "policy_blocked"


class ReviewStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class SkillInvocation:
    """Record of a single skill execution."""
    query_id: str
    skill_id: str
    version: str = "1.0"
    input_evidence: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    status: InvocationStatus = InvocationStatus.PENDING
    confidence: float = 0.0
    provenance: list[str] = field(default_factory=list)
    timing_ms: int = 0
    review_status: ReviewStatus = ReviewStatus.NOT_REQUIRED
    error_message: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["review_status"] = self.review_status.value
        return d


def _validate_schema(data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Lightweight schema validation. Returns list of error messages."""
    errors: list[str] = []
    if not schema:
        return errors

    required = schema.get("required") or []
    properties = schema.get("properties") or {}

    for field_name in required:
        if field_name not in data:
            errors.append(f"Missing required field: {field_name}")

    for field_name, value in data.items():
        if field_name in properties:
            expected_type = properties[field_name].get("type")
            if expected_type and not _check_type(value, expected_type):
                errors.append(f"Field '{field_name}' expected type '{expected_type}', got {type(value).__name__}")

    return errors


def _check_type(value: Any, expected: str) -> bool:
    """Check if a value matches a JSON Schema type string."""
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    expected_type = type_map.get(expected)
    if expected_type is None:
        return True
    return isinstance(value, expected_type)


# Type alias for skill handler functions
SkillHandler = Callable[[dict[str, Any]], dict[str, Any]]


class RAGSkillExecutor:
    """Executes skill invocations with validation, timeout, and audit."""

    def __init__(self) -> None:
        self._handlers: dict[str, SkillHandler] = {}
        self._audit_log: list[SkillInvocation] = []

    def register_handler(self, skill_id: str, handler: SkillHandler) -> None:
        """Register a callable handler for a skill."""
        self._handlers[skill_id] = handler

    @property
    def audit_log(self) -> list[SkillInvocation]:
        return list(self._audit_log)

    def execute(
        self,
        skill: SkillDefinition,
        query_id: str,
        input_evidence: dict[str, Any],
    ) -> SkillInvocation:
        """Execute a skill and return the invocation record."""
        invocation = SkillInvocation(
            query_id=query_id,
            skill_id=skill.skill_id,
            version=skill.version,
            input_evidence=input_evidence,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # 1. Validate input
        input_errors = _validate_schema(input_evidence, skill.input_schema)
        if input_errors:
            invocation.status = InvocationStatus.FAILED
            invocation.error_message = f"Input validation failed: {'; '.join(input_errors)}"
            self._record(invocation)
            return invocation

        # 2. Check handler exists
        handler = self._handlers.get(skill.skill_id)
        if handler is None:
            invocation.status = InvocationStatus.FAILED
            invocation.error_message = f"No handler registered for skill '{skill.skill_id}'"
            self._record(invocation)
            return invocation

        # 3. Execute with timeout tracking
        invocation.status = InvocationStatus.RUNNING
        timeout_s = skill.timeout_ms / 1000.0
        start = time.monotonic()

        try:
            result = handler(input_evidence)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            invocation.timing_ms = elapsed_ms

            if elapsed_ms > skill.timeout_ms:
                invocation.status = InvocationStatus.TIMED_OUT
                invocation.error_message = f"Execution exceeded timeout ({skill.timeout_ms}ms)"
                self._record(invocation)
                return invocation

            # 4. Validate output
            if isinstance(result, dict):
                output_errors = _validate_schema(result, skill.output_schema)
                if output_errors:
                    logger.warning("Skill %s output validation: %s", skill.skill_id, output_errors)

                invocation.output = result
                invocation.confidence = result.get("confidence", 0.0)
                invocation.provenance = result.get("provenance", [])
            else:
                invocation.output = {"raw": str(result)}

            invocation.status = InvocationStatus.COMPLETED

            # 5. Set review status based on governance
            if skill.governance_level == GovernanceLevel.REVIEW_REQUIRED:
                invocation.review_status = ReviewStatus.PENDING_REVIEW
            elif skill.governance_level == GovernanceLevel.GOVERNED_WRITE_CANDIDATE:
                invocation.review_status = ReviewStatus.PENDING_REVIEW

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            invocation.timing_ms = elapsed_ms
            invocation.status = InvocationStatus.FAILED
            invocation.error_message = str(exc)
            logger.exception("Skill %s failed", skill.skill_id)

        self._record(invocation)
        return invocation

    def execute_with_fallback(
        self,
        skill: SkillDefinition,
        query_id: str,
        input_evidence: dict[str, Any],
        fallback_fn: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> SkillInvocation:
        """Execute a skill; on failure, fall back to direct RAG."""
        invocation = self.execute(skill, query_id, input_evidence)

        if invocation.status in (InvocationStatus.FAILED, InvocationStatus.TIMED_OUT):
            try:
                fallback_result = fallback_fn(input_evidence)
                invocation.output = fallback_result
                invocation.provenance = ["fallback_direct_rag"]
                invocation.error_message += " [fell back to direct RAG]"
            except Exception as exc:
                invocation.error_message += f" [fallback also failed: {exc}]"

        return invocation

    def _record(self, invocation: SkillInvocation) -> None:
        """Persist audit event."""
        self._audit_log.append(invocation)
        logger.info(
            "Skill invocation: skill=%s query=%s status=%s timing=%dms",
            invocation.skill_id,
            invocation.query_id,
            invocation.status.value,
            invocation.timing_ms,
        )
