"""Tests for mapping_suggestions.py — Task 3.1."""
import pytest

from backend.services.source_profiler import FieldProfile, SemanticRole, SourceProfile
from backend.services.mapping_suggestions import (
    MappingSuggestion,
    MappingSuggestionService,
    SuggestionStatus,
    CANONICAL_TARGETS,
    _NAME_TARGET_MAP,
    _ROLE_TARGET_MAP,
)


def _profile(*field_profiles: FieldProfile) -> SourceProfile:
    return SourceProfile(
        source_id="test-src",
        source_format="csv",
        total_rows=10,
        field_profiles=list(field_profiles),
    )


def _fp(name: str, *, semantic: list[SemanticRole] | None = None,
        identifiers: list[str] | None = None,
        samples: list[str] | None = None) -> FieldProfile:
    return FieldProfile(
        field_name=name,
        total_count=10,
        non_null_count=10,
        inferred_type="TEXT",
        semantic_candidates=semantic or [],
        candidate_identifiers=identifiers or [],
        sample_values=samples or ["a", "b", "c"],
    )


class TestSuggestionGeneration:
    def test_name_exact_match_title(self):
        svc = MappingSuggestionService()
        result = svc.generate_suggestions(_profile(_fp("title")))
        assert len(result) == 1
        assert result[0].canonical_target == "primary_label"
        assert result[0].confidence == 0.95
        assert result[0].status == SuggestionStatus.AUTO_ACCEPTABLE

    def test_name_exact_match_doi(self):
        svc = MappingSuggestionService()
        result = svc.generate_suggestions(_profile(_fp("doi")))
        assert result[0].canonical_target == "enrichment_doi"

    def test_name_exact_match_authors(self):
        svc = MappingSuggestionService()
        result = svc.generate_suggestions(_profile(_fp("authors")))
        assert result[0].canonical_target == "secondary_label"

    def test_semantic_role_fallback(self):
        svc = MappingSuggestionService()
        result = svc.generate_suggestions(_profile(
            _fp("unknown_field", semantic=[SemanticRole.PERSON])
        ))
        assert len(result) == 1
        assert result[0].canonical_target == "secondary_label"
        assert result[0].confidence == 0.75
        assert result[0].status == SuggestionStatus.REVIEW_REQUIRED

    def test_identifier_doi_fallback(self):
        svc = MappingSuggestionService()
        result = svc.generate_suggestions(_profile(
            _fp("some_id_field", identifiers=["DOI"])
        ))
        assert len(result) == 1
        assert result[0].canonical_target == "enrichment_doi"
        assert result[0].confidence == 0.85

    def test_no_match_yields_nothing(self):
        svc = MappingSuggestionService()
        result = svc.generate_suggestions(_profile(
            _fp("xyzzy_field_99")
        ))
        assert result == []

    def test_multiple_fields(self):
        svc = MappingSuggestionService()
        result = svc.generate_suggestions(_profile(
            _fp("title"), _fp("doi"), _fp("concepts")
        ))
        assert len(result) == 3
        targets = {s.canonical_target for s in result}
        assert targets == {"primary_label", "enrichment_doi", "enrichment_concepts"}

    def test_evidence_samples_capped(self):
        svc = MappingSuggestionService()
        result = svc.generate_suggestions(_profile(
            _fp("title", samples=["a", "b", "c", "d", "e"])
        ))
        assert len(result[0].evidence_samples) <= 3

    def test_ids_are_sequential(self):
        svc = MappingSuggestionService()
        result = svc.generate_suggestions(_profile(
            _fp("title"), _fp("doi")
        ))
        assert result[0].id == 1
        assert result[1].id == 2


class TestAcceptReject:
    def test_accept(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title")))
        accepted = svc.accept_suggestion(1, reviewer_id=42)
        assert accepted is not None
        assert accepted.status == SuggestionStatus.ACCEPTED
        assert accepted.reviewer_id == 42
        assert accepted.reviewed_at is not None

    def test_accept_missing_returns_none(self):
        svc = MappingSuggestionService()
        assert svc.accept_suggestion(999, reviewer_id=1) is None

    def test_accept_idempotent(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title")))
        svc.accept_suggestion(1, reviewer_id=1)
        again = svc.accept_suggestion(1, reviewer_id=2)
        assert again.status == SuggestionStatus.ACCEPTED
        assert again.reviewer_id == 1  # first reviewer kept

    def test_reject(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title")))
        rejected = svc.reject_suggestion(1, "wrong mapping", reviewer_id=5)
        assert rejected.status == SuggestionStatus.REJECTED
        assert rejected.rationale == "wrong mapping"

    def test_reject_missing(self):
        svc = MappingSuggestionService()
        assert svc.reject_suggestion(999, "nope", reviewer_id=1) is None


class TestSupersede:
    def test_supersede(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title"), _fp("doi")))
        result = svc.supersede_suggestion(1, 2)
        assert result.status == SuggestionStatus.SUPERSEDED
        assert result.superseded_by == 2

    def test_supersede_missing(self):
        svc = MappingSuggestionService()
        assert svc.supersede_suggestion(999, 1) is None

    def test_cannot_reject_superseded(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title")))
        svc.supersede_suggestion(1, 99)
        rejected = svc.reject_suggestion(1, "nah", reviewer_id=1)
        assert rejected.status == SuggestionStatus.SUPERSEDED  # no change


class TestReappearance:
    def test_existing_not_rejected(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title")))
        assert svc.check_reappearance("title", "primary_label") is True

    def test_rejected_does_not_count(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title")))
        svc.reject_suggestion(1, "wrong", reviewer_id=1)
        assert svc.check_reappearance("title", "primary_label") is False

    def test_no_match(self):
        svc = MappingSuggestionService()
        assert svc.check_reappearance("title", "primary_label") is False


class TestListAndGet:
    def test_list_all(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title"), _fp("doi")))
        assert len(svc.list_suggestions()) == 2

    def test_list_by_status(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title"), _fp("doi")))
        svc.accept_suggestion(1, reviewer_id=1)
        assert len(svc.list_suggestions(SuggestionStatus.ACCEPTED)) == 1
        assert len(svc.list_suggestions(SuggestionStatus.AUTO_ACCEPTABLE)) == 1

    def test_get(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title")))
        assert svc.get(1) is not None
        assert svc.get(999) is None

    def test_to_dict(self):
        svc = MappingSuggestionService()
        svc.generate_suggestions(_profile(_fp("title")))
        d = svc.get(1).to_dict()
        assert d["status"] == "auto_acceptable"
        assert d["source_field"] == "title"
