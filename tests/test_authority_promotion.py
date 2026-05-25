"""Tests for authority_promotion.py — Task 3.7."""
import pytest

from backend.services.authority_promotion import (
    AuthorityPromotionService,
    PromotionPayload,
    PromotionResult,
    PromotionStatus,
)


def _payload(**kwargs) -> PromotionPayload:
    defaults = {
        "entity_type": "person",
        "label": "Alice Smith",
        "identifiers": {"orcid": "0000-0001-2345-6789"},
        "confidence": 0.8,
    }
    defaults.update(kwargs)
    return PromotionPayload(**defaults)


class TestPromote:
    def test_pending_review_default(self):
        svc = AuthorityPromotionService()
        result = svc.promote(_payload())
        assert result.status == PromotionStatus.PENDING_REVIEW
        assert result.id == 1
        assert result.canonical_label == "Alice Smith"
        assert result.source_preserved is True
        assert result.enrichment_preserved is True

    def test_promoted_with_reviewer(self):
        svc = AuthorityPromotionService()
        result = svc.promote(_payload(reviewer_id=42))
        assert result.status == PromotionStatus.PROMOTED

    def test_auto_accepted(self):
        svc = AuthorityPromotionService()
        result = svc.promote(_payload(confidence=0.95, auto_policy="high_confidence"))
        assert result.status == PromotionStatus.AUTO_ACCEPTED

    def test_auto_accept_requires_policy(self):
        svc = AuthorityPromotionService()
        result = svc.promote(_payload(confidence=0.95))
        assert result.status == PromotionStatus.PENDING_REVIEW

    def test_custom_threshold(self):
        svc = AuthorityPromotionService(auto_accept_threshold=0.5)
        result = svc.promote(_payload(confidence=0.6, auto_policy="low_bar"))
        assert result.status == PromotionStatus.AUTO_ACCEPTED

    def test_sequential_ids(self):
        svc = AuthorityPromotionService()
        r1 = svc.promote(_payload(label="A"))
        r2 = svc.promote(_payload(label="B"))
        assert r1.id == 1
        assert r2.id == 2


class TestConflictDetection:
    def test_same_id_different_label(self):
        svc = AuthorityPromotionService()
        svc.promote(_payload(label="Alice Smith", identifiers={"orcid": "0000-0001"}))
        result = svc.promote(_payload(label="A. Smith", identifiers={"orcid": "0000-0001"}))
        assert result.status == PromotionStatus.CONFLICT
        assert "0000-0001" in result.conflict_details

    def test_same_label_same_id_no_conflict(self):
        svc = AuthorityPromotionService()
        svc.promote(_payload(label="Alice", identifiers={"orcid": "0000-0001"}))
        result = svc.promote(_payload(label="Alice", identifiers={"orcid": "0000-0001"}))
        # Same label + same id = no conflict (may be duplicate but not conflict)
        assert result.status != PromotionStatus.CONFLICT

    def test_rejected_not_counted_for_conflict(self):
        svc = AuthorityPromotionService()
        svc.promote(_payload(label="Alice", identifiers={"orcid": "0000-0001"}))
        svc.reject(1, "wrong")
        result = svc.promote(_payload(label="Bob", identifiers={"orcid": "0000-0001"}))
        assert result.status != PromotionStatus.CONFLICT


class TestReject:
    def test_reject(self):
        svc = AuthorityPromotionService()
        svc.promote(_payload())
        result = svc.reject(1, "incorrect identity")
        assert result is not None
        assert result.status == PromotionStatus.REJECTED
        assert result.conflict_details == "incorrect identity"

    def test_reject_missing(self):
        svc = AuthorityPromotionService()
        assert svc.reject(999) is None

    def test_rejected_prevents_recreation(self):
        svc = AuthorityPromotionService()
        svc.promote(_payload())
        svc.reject(1, "wrong")
        result = svc.promote(_payload())  # same payload
        assert result.status == PromotionStatus.REJECTED
        assert "Previously rejected" in result.conflict_details


class TestListAndGet:
    def test_get(self):
        svc = AuthorityPromotionService()
        svc.promote(_payload())
        assert svc.get(1) is not None
        assert svc.get(999) is None

    def test_list_all(self):
        svc = AuthorityPromotionService()
        svc.promote(_payload(label="A"))
        svc.promote(_payload(label="B"))
        assert len(svc.list_promotions()) == 2

    def test_list_by_status(self):
        svc = AuthorityPromotionService()
        svc.promote(_payload(label="A", reviewer_id=1, identifiers={"orcid": "0000-0001"}))
        svc.promote(_payload(label="B", identifiers={"orcid": "0000-0002"}))
        assert len(svc.list_promotions(PromotionStatus.PROMOTED)) == 1
        assert len(svc.list_promotions(PromotionStatus.PENDING_REVIEW)) == 1

    def test_promotions_property(self):
        svc = AuthorityPromotionService()
        svc.promote(_payload())
        assert len(svc.promotions) == 1


class TestToDict:
    def test_serialization(self):
        svc = AuthorityPromotionService()
        result = svc.promote(_payload())
        d = result.to_dict()
        assert d["status"] == "pending_review"
        assert d["canonical_label"] == "Alice Smith"
