"""Authority Canonical Promotion — Task 3.7.

Promotes authority candidates to canonical status. Preserves source and
enrichment layers, detects conflicts, and applies auto-accept rules.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PromotionStatus(str, Enum):
    PROMOTED = "promoted"
    CONFLICT = "conflict"
    REJECTED = "rejected"
    AUTO_ACCEPTED = "auto_accepted"
    PENDING_REVIEW = "pending_review"


@dataclass
class PromotionPayload:
    """Payload for promoting a candidate to canonical status."""
    entity_type: str  # person | institution | identifier | place | venue | concept
    label: str
    identifiers: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    evidence_refs: list[str] = field(default_factory=list)
    reviewer_id: int | None = None
    auto_policy: str | None = None
    source_layer: dict[str, Any] = field(default_factory=dict)
    enrichment_layer: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromotionResult:
    """Result of a canonical promotion attempt."""
    id: int | None = None
    status: PromotionStatus = PromotionStatus.PENDING_REVIEW
    canonical_label: str = ""
    identifiers: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    conflict_details: str = ""
    source_preserved: bool = True
    enrichment_preserved: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class AuthorityPromotionService:
    """Promotes authority candidates to canonical status."""

    def __init__(self, auto_accept_threshold: float = 0.9) -> None:
        self._promotions: dict[int, PromotionResult] = {}
        self._next_id = 1
        self._auto_accept_threshold = auto_accept_threshold
        # Track rejected candidates to prevent re-creation
        self._rejected_keys: set[str] = set()

    @property
    def promotions(self) -> list[PromotionResult]:
        return list(self._promotions.values())

    def promote(self, payload: PromotionPayload) -> PromotionResult:
        """Attempt to promote a candidate to canonical status."""
        dedup_key = self._dedup_key(payload)

        # Check if previously rejected (don't recreate unless evidence changes)
        if dedup_key in self._rejected_keys:
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                canonical_label=payload.label,
                identifiers=payload.identifiers,
                confidence=payload.confidence,
                conflict_details="Previously rejected; not recreated",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        # Check for conflicts with existing promotions
        conflict = self._detect_conflict(payload)
        if conflict:
            result = PromotionResult(
                id=self._next_id,
                status=PromotionStatus.CONFLICT,
                canonical_label=payload.label,
                identifiers=payload.identifiers,
                confidence=payload.confidence,
                conflict_details=conflict,
                source_preserved=True,
                enrichment_preserved=True,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._promotions[self._next_id] = result
            self._next_id += 1
            return result

        # Auto-accept check
        if (
            payload.confidence >= self._auto_accept_threshold
            and payload.auto_policy
        ):
            status = PromotionStatus.AUTO_ACCEPTED
        elif payload.reviewer_id is not None:
            status = PromotionStatus.PROMOTED
        else:
            status = PromotionStatus.PENDING_REVIEW

        result = PromotionResult(
            id=self._next_id,
            status=status,
            canonical_label=payload.label,
            identifiers=payload.identifiers,
            confidence=payload.confidence,
            source_preserved=True,
            enrichment_preserved=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._promotions[self._next_id] = result
        self._next_id += 1
        return result

    def reject(self, promotion_id: int, reason: str = "") -> PromotionResult | None:
        """Reject a promotion and record it to prevent re-creation."""
        result = self._promotions.get(promotion_id)
        if not result:
            return None
        result.status = PromotionStatus.REJECTED
        result.conflict_details = reason
        # Track rejection
        key = f"{result.canonical_label}|{'|'.join(f'{k}={v}' for k, v in sorted(result.identifiers.items()))}"
        self._rejected_keys.add(key)
        return result

    def get(self, promotion_id: int) -> PromotionResult | None:
        return self._promotions.get(promotion_id)

    def list_promotions(self, status: PromotionStatus | None = None) -> list[PromotionResult]:
        results = list(self._promotions.values())
        if status:
            results = [r for r in results if r.status == status]
        return results

    def _detect_conflict(self, payload: PromotionPayload) -> str:
        """Detect conflicts between enrichment and authority data."""
        for p in self._promotions.values():
            if p.status in (PromotionStatus.REJECTED,):
                continue
            # Same identifiers but different labels → conflict
            for id_type, id_val in payload.identifiers.items():
                existing_val = p.identifiers.get(id_type)
                if existing_val and existing_val == id_val and p.canonical_label != payload.label:
                    return (
                        f"Identifier {id_type}={id_val} already promoted as "
                        f"'{p.canonical_label}', conflicting with '{payload.label}'"
                    )
        return ""

    def _dedup_key(self, payload: PromotionPayload) -> str:
        ids = "|".join(f"{k}={v}" for k, v in sorted(payload.identifiers.items()))
        return f"{payload.label}|{ids}"
