"""Mapping Suggestion Contract — Task 3.1.

Generates, accepts, rejects, and supersedes field mapping suggestions
based on source profile analysis.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.services.field_correspondence import infer_source_schema, resolve_field_correspondence
from backend.services.source_profiler import FieldProfile, SemanticRole, SourceProfile

logger = logging.getLogger(__name__)


class SuggestionStatus(str, Enum):
    AUTO_ACCEPTABLE = "auto_acceptable"
    REVIEW_REQUIRED = "review_required"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


# Canonical target fields that can be mapped to
CANONICAL_TARGETS = {
    "primary_label", "secondary_label", "canonical_id", "entity_type",
    "enrichment_doi", "enrichment_citation_count", "enrichment_concepts",
    "enrichment_source",
}

# Semantic role → canonical target heuristic
_ROLE_TARGET_MAP: dict[SemanticRole, str] = {
    SemanticRole.PUBLICATION: "primary_label",
    SemanticRole.PERSON: "secondary_label",
    SemanticRole.IDENTIFIER: "enrichment_doi",
    SemanticRole.CONCEPT: "enrichment_concepts",
}

# Field name → canonical target exact matches
_NAME_TARGET_MAP: dict[str, str] = {
    "title": "primary_label",
    "name": "primary_label",
    "display_name": "primary_label",
    "authors": "secondary_label",
    "author": "secondary_label",
    "creator": "secondary_label",
    "doi": "enrichment_doi",
    "citation_count": "enrichment_citation_count",
    "cited_by_count": "enrichment_citation_count",
    "concepts": "enrichment_concepts",
    "keywords": "enrichment_concepts",
    "topics": "enrichment_concepts",
    "source": "enrichment_source",
    "source_api": "enrichment_source",
    "type": "entity_type",
    "entity_type": "entity_type",
}


@dataclass
class MappingSuggestion:
    """A suggested mapping from source field to canonical target."""
    id: int | None = None
    source_field: str = ""
    canonical_target: str = ""
    confidence: float = 0.0
    evidence_samples: list[str] = field(default_factory=list)
    status: SuggestionStatus = SuggestionStatus.REVIEW_REQUIRED
    reviewer_id: int | None = None
    reviewed_at: str | None = None
    rationale: str = ""
    superseded_by: int | None = None
    semantic_concept: str | None = None
    identifier_scheme: str | None = None
    evidence: list[str] = field(default_factory=list)
    requires_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


class MappingSuggestionService:
    """Generates and manages mapping suggestions."""

    def __init__(self) -> None:
        self._suggestions: dict[int, MappingSuggestion] = {}
        self._next_id = 1

    def generate_suggestions(self, profile: SourceProfile) -> list[MappingSuggestion]:
        """Generate mapping suggestions from a source profile."""
        suggestions: list[MappingSuggestion] = []
        source_schema = infer_source_schema(profile.source_format, {f.field_name for f in profile.field_profiles})

        for fp in profile.field_profiles:
            target, confidence, metadata = self._infer_target(fp, source_schema=source_schema)
            if not target:
                continue

            status = (
                SuggestionStatus.AUTO_ACCEPTABLE
                if confidence >= 0.9
                else SuggestionStatus.REVIEW_REQUIRED
            )

            suggestion = MappingSuggestion(
                id=self._next_id,
                source_field=fp.field_name,
                canonical_target=target,
                confidence=round(confidence, 3),
                evidence_samples=fp.sample_values[:3],
                status=status,
                semantic_concept=metadata.get("semantic_concept"),
                identifier_scheme=metadata.get("identifier_scheme"),
                evidence=metadata.get("evidence", []),
                requires_review=bool(metadata.get("requires_review", False)),
            )
            self._suggestions[self._next_id] = suggestion
            self._next_id += 1
            suggestions.append(suggestion)

        return suggestions

    def accept_suggestion(self, suggestion_id: int, reviewer_id: int) -> MappingSuggestion | None:
        """Accept a suggestion and record the reviewer."""
        suggestion = self._suggestions.get(suggestion_id)
        if not suggestion:
            return None
        if suggestion.status in (SuggestionStatus.ACCEPTED, SuggestionStatus.SUPERSEDED):
            return suggestion

        suggestion.status = SuggestionStatus.ACCEPTED
        suggestion.reviewer_id = reviewer_id
        suggestion.reviewed_at = datetime.now(timezone.utc).isoformat()
        return suggestion

    def reject_suggestion(
        self, suggestion_id: int, rationale: str, reviewer_id: int,
    ) -> MappingSuggestion | None:
        """Reject a suggestion with a rationale."""
        suggestion = self._suggestions.get(suggestion_id)
        if not suggestion:
            return None
        if suggestion.status == SuggestionStatus.SUPERSEDED:
            return suggestion

        suggestion.status = SuggestionStatus.REJECTED
        suggestion.rationale = rationale
        suggestion.reviewer_id = reviewer_id
        suggestion.reviewed_at = datetime.now(timezone.utc).isoformat()
        return suggestion

    def supersede_suggestion(self, old_id: int, new_id: int) -> MappingSuggestion | None:
        """Mark an old suggestion as superseded by a new one."""
        old = self._suggestions.get(old_id)
        if not old:
            return None
        old.status = SuggestionStatus.SUPERSEDED
        old.superseded_by = new_id
        return old

    def check_reappearance(self, source_field: str, canonical_target: str) -> bool:
        """Check if a suggestion for this field→target already exists (not rejected)."""
        for s in self._suggestions.values():
            if (
                s.source_field == source_field
                and s.canonical_target == canonical_target
                and s.status not in (SuggestionStatus.REJECTED, SuggestionStatus.SUPERSEDED)
            ):
                return True
        return False

    def get(self, suggestion_id: int) -> MappingSuggestion | None:
        return self._suggestions.get(suggestion_id)

    def list_suggestions(self, status: SuggestionStatus | None = None) -> list[MappingSuggestion]:
        result = list(self._suggestions.values())
        if status:
            result = [s for s in result if s.status == status]
        return result

    def _infer_target(self, fp: FieldProfile, *, source_schema: str | None = None) -> tuple[str | None, float, dict[str, Any]]:
        """Infer the best canonical target for a field profile."""
        correspondence = resolve_field_correspondence(
            fp.field_name,
            sample_values=fp.sample_values,
            source_schema=source_schema,
        )
        if correspondence:
            if correspondence.canonical_target is None:
                return None, 0.0, {
                    "semantic_concept": correspondence.semantic_concept,
                    "identifier_scheme": correspondence.identifier_scheme,
                    "evidence": list(correspondence.evidence),
                    "requires_review": correspondence.requires_review,
                }
            return correspondence.canonical_target, correspondence.confidence, {
                "semantic_concept": correspondence.semantic_concept,
                "identifier_scheme": correspondence.identifier_scheme,
                "evidence": list(correspondence.evidence),
                "requires_review": correspondence.requires_review,
            }

        fn_lower = fp.field_name.lower().replace("-", "_").replace(" ", "_")

        # Exact name match
        if fn_lower in _NAME_TARGET_MAP:
            return _NAME_TARGET_MAP[fn_lower], 0.95, {"evidence": ["legacy_exact_name"]}

        # Semantic role match
        for role in fp.semantic_candidates:
            if role in _ROLE_TARGET_MAP:
                return _ROLE_TARGET_MAP[role], 0.75, {"evidence": ["semantic_role"]}

        # Identifier with DOI content
        if "DOI" in fp.candidate_identifiers:
            return "canonical_id", 0.85, {
                "semantic_concept": "persistent_identifier",
                "identifier_scheme": "doi",
                "evidence": ["candidate_identifier"],
            }

        return None, 0.0, {}
