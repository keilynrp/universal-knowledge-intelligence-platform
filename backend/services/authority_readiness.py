"""Authority Readiness Status — Task 3.6.

Tracks the readiness state of authority resolution per domain/dataset,
with per-family breakdowns and stale detection.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from backend.services.authority_candidate_extraction import CandidateFamily


class ReadinessState(str, Enum):
    NOT_STARTED = "not_started"
    SOURCE_CANDIDATES_READY = "source_candidates_ready"
    ENRICHMENT_CANDIDATES_READY = "enrichment_candidates_ready"
    REVIEW_REQUIRED = "review_required"
    PARTIALLY_RESOLVED = "partially_resolved"
    RESOLVED = "resolved"
    STALE = "stale"
    FAILED = "failed"


@dataclass
class FamilyCounts:
    """Per-family counts for authority readiness."""
    extracted: int = 0
    resolved: int = 0
    review_required: int = 0
    rejected: int = 0
    failed: int = 0
    stale: int = 0

    @property
    def total(self) -> int:
        return self.extracted + self.resolved + self.review_required + self.rejected + self.failed + self.stale

    @property
    def resolution_rate(self) -> float:
        t = self.total
        return self.resolved / t if t > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["total"] = self.total
        d["resolution_rate"] = round(self.resolution_rate, 3)
        return d


@dataclass
class AuthorityReadiness:
    """Authority readiness status for a domain or dataset."""
    scope_id: str  # domain_id or dataset_id
    scope_type: str = "domain"  # domain | dataset
    state: ReadinessState = ReadinessState.NOT_STARTED
    families: dict[str, FamilyCounts] = field(default_factory=dict)
    last_extraction_at: str | None = None
    last_evidence_change_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope_id": self.scope_id,
            "scope_type": self.scope_type,
            "state": self.state.value,
            "families": {k: v.to_dict() for k, v in self.families.items()},
            "last_extraction_at": self.last_extraction_at,
            "last_evidence_change_at": self.last_evidence_change_at,
        }


class AuthorityReadinessTracker:
    """Tracks authority readiness state per scope."""

    def __init__(self) -> None:
        self._readiness: dict[str, AuthorityReadiness] = {}

    def get_or_create(self, scope_id: str, scope_type: str = "domain") -> AuthorityReadiness:
        if scope_id not in self._readiness:
            self._readiness[scope_id] = AuthorityReadiness(
                scope_id=scope_id,
                scope_type=scope_type,
                families={f.value: FamilyCounts() for f in CandidateFamily},
            )
        return self._readiness[scope_id]

    def record_extraction(
        self,
        scope_id: str,
        family: CandidateFamily,
        count: int,
        timestamp: str,
        scope_type: str = "domain",
    ) -> AuthorityReadiness:
        """Record that candidates were extracted for a family."""
        readiness = self.get_or_create(scope_id, scope_type)
        fc = readiness.families.setdefault(family.value, FamilyCounts())
        fc.extracted += count
        readiness.last_extraction_at = timestamp
        readiness.state = self._compute_state(readiness)
        return readiness

    def record_resolution(
        self,
        scope_id: str,
        family: CandidateFamily,
        resolved: int = 0,
        review_required: int = 0,
        rejected: int = 0,
        failed: int = 0,
    ) -> AuthorityReadiness:
        """Record resolution outcomes for a family."""
        readiness = self.get_or_create(scope_id)
        fc = readiness.families.setdefault(family.value, FamilyCounts())
        fc.resolved += resolved
        fc.review_required += review_required
        fc.rejected += rejected
        fc.failed += failed
        readiness.state = self._compute_state(readiness)
        return readiness

    def mark_stale(
        self,
        scope_id: str,
        family: CandidateFamily,
        count: int,
        evidence_change_at: str,
    ) -> AuthorityReadiness:
        """Mark candidates as stale due to evidence changes."""
        readiness = self.get_or_create(scope_id)
        fc = readiness.families.setdefault(family.value, FamilyCounts())
        fc.stale += count
        readiness.last_evidence_change_at = evidence_change_at
        readiness.state = self._compute_state(readiness)
        return readiness

    def _compute_state(self, readiness: AuthorityReadiness) -> ReadinessState:
        """Compute overall state from family counts."""
        total_extracted = sum(fc.extracted for fc in readiness.families.values())
        total_resolved = sum(fc.resolved for fc in readiness.families.values())
        total_review = sum(fc.review_required for fc in readiness.families.values())
        total_failed = sum(fc.failed for fc in readiness.families.values())
        total_stale = sum(fc.stale for fc in readiness.families.values())
        total_all = sum(fc.total for fc in readiness.families.values())

        if total_all == 0:
            return ReadinessState.NOT_STARTED
        if total_stale > 0:
            return ReadinessState.STALE
        if total_failed > 0 and total_resolved == 0:
            return ReadinessState.FAILED
        if total_review > 0:
            return ReadinessState.REVIEW_REQUIRED
        if total_resolved == total_all and total_all > 0:
            return ReadinessState.RESOLVED
        if total_resolved > 0:
            return ReadinessState.PARTIALLY_RESOLVED
        if total_extracted > 0:
            # Determine if source-only or enrichment
            return ReadinessState.SOURCE_CANDIDATES_READY

        return ReadinessState.NOT_STARTED
