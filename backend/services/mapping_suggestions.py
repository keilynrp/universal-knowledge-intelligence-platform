"""Mapping Suggestion Contract — Task 3.1.

Generates, accepts, rejects, and supersedes field mapping suggestions
based on source profile analysis.
"""
from __future__ import annotations

import logging
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from backend import models
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
    org_id: int | None = None
    import_batch_id: int | None = None
    source_id: str | None = None
    source_format: str | None = None
    source_schema: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


def _loads_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _suggestion_from_record(record: models.MappingSuggestionRecord) -> MappingSuggestion:
    return MappingSuggestion(
        id=record.id,
        source_field=record.source_field,
        canonical_target=record.canonical_target,
        confidence=record.confidence or 0.0,
        evidence_samples=_loads_list(record.evidence_samples),
        status=SuggestionStatus(record.status or SuggestionStatus.REVIEW_REQUIRED.value),
        reviewer_id=record.reviewer_id,
        reviewed_at=record.reviewed_at.isoformat() if record.reviewed_at else None,
        rationale=record.rationale or "",
        superseded_by=record.superseded_by,
        semantic_concept=record.semantic_concept,
        identifier_scheme=record.identifier_scheme,
        evidence=_loads_list(record.evidence),
        requires_review=bool(record.requires_review),
        org_id=record.org_id,
        import_batch_id=record.import_batch_id,
        source_id=record.source_id,
        source_format=record.source_format,
        source_schema=record.source_schema,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


class MappingSuggestionService:
    """Generates and manages mapping suggestions."""

    def __init__(self, db: Session | None = None, org_id: int | None = None) -> None:
        self.db = db
        self.org_id = org_id
        self._suggestions: dict[int, MappingSuggestion] = {}
        self._next_id = 1

    def generate_suggestions(
        self,
        profile: SourceProfile,
        *,
        org_id: int | None = None,
        import_batch_id: int | None = None,
    ) -> list[MappingSuggestion]:
        """Generate mapping suggestions from a source profile."""
        suggestions: list[MappingSuggestion] = []
        effective_org_id = org_id if org_id is not None else self.org_id
        source_schema = infer_source_schema(profile.source_format, {f.field_name for f in profile.field_profiles})

        for fp in profile.field_profiles:
            target, confidence, metadata = self._infer_target(
                fp,
                source_schema=source_schema,
                org_id=effective_org_id,
            )
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
                org_id=effective_org_id,
                import_batch_id=import_batch_id,
                source_id=profile.source_id,
                source_format=profile.source_format,
                source_schema=source_schema,
            )
            if self.db is not None:
                record = self._persist_suggestion(suggestion)
                suggestion = _suggestion_from_record(record)
            else:
                self._suggestions[self._next_id] = suggestion
                self._next_id += 1
            suggestions.append(suggestion)

        return suggestions

    def accept_suggestion(self, suggestion_id: int, reviewer_id: int) -> MappingSuggestion | None:
        """Accept a suggestion and record the reviewer."""
        if self.db is not None:
            suggestion = self.db.get(models.MappingSuggestionRecord, suggestion_id)
            if not suggestion:
                return None
            if suggestion.status not in (SuggestionStatus.ACCEPTED.value, SuggestionStatus.SUPERSEDED.value):
                now = datetime.now(timezone.utc)
                suggestion.status = SuggestionStatus.ACCEPTED.value
                suggestion.reviewer_id = reviewer_id
                suggestion.reviewed_at = now
                suggestion.updated_at = now
                self._upsert_rule_from_suggestion(suggestion, reviewer_id=reviewer_id)
                self.db.commit()
                self.db.refresh(suggestion)
            return _suggestion_from_record(suggestion)

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
        if self.db is not None:
            suggestion = self.db.get(models.MappingSuggestionRecord, suggestion_id)
            if not suggestion:
                return None
            if suggestion.status != SuggestionStatus.SUPERSEDED.value:
                now = datetime.now(timezone.utc)
                suggestion.status = SuggestionStatus.REJECTED.value
                suggestion.rationale = rationale
                suggestion.reviewer_id = reviewer_id
                suggestion.reviewed_at = now
                suggestion.updated_at = now
                self.db.commit()
                self.db.refresh(suggestion)
            return _suggestion_from_record(suggestion)

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
        if self.db is not None:
            old = self.db.get(models.MappingSuggestionRecord, old_id)
            if not old:
                return None
            old.status = SuggestionStatus.SUPERSEDED.value
            old.superseded_by = new_id
            old.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(old)
            return _suggestion_from_record(old)

        old = self._suggestions.get(old_id)
        if not old:
            return None
        old.status = SuggestionStatus.SUPERSEDED
        old.superseded_by = new_id
        return old

    def check_reappearance(self, source_field: str, canonical_target: str) -> bool:
        """Check if a suggestion for this field→target already exists (not rejected)."""
        if self.db is not None:
            query = self.db.query(models.MappingSuggestionRecord).filter(
                models.MappingSuggestionRecord.source_field == source_field,
                models.MappingSuggestionRecord.canonical_target == canonical_target,
                models.MappingSuggestionRecord.status.notin_([
                    SuggestionStatus.REJECTED.value,
                    SuggestionStatus.SUPERSEDED.value,
                ]),
            )
            if self.org_id is not None:
                query = query.filter(models.MappingSuggestionRecord.org_id == self.org_id)
            return query.first() is not None

        for s in self._suggestions.values():
            if (
                s.source_field == source_field
                and s.canonical_target == canonical_target
                and s.status not in (SuggestionStatus.REJECTED, SuggestionStatus.SUPERSEDED)
            ):
                return True
        return False

    def get(self, suggestion_id: int) -> MappingSuggestion | None:
        if self.db is not None:
            record = self.db.get(models.MappingSuggestionRecord, suggestion_id)
            return _suggestion_from_record(record) if record else None
        return self._suggestions.get(suggestion_id)

    def list_suggestions(self, status: SuggestionStatus | None = None) -> list[MappingSuggestion]:
        if self.db is not None:
            query = self.db.query(models.MappingSuggestionRecord)
            if self.org_id is not None:
                query = query.filter(models.MappingSuggestionRecord.org_id == self.org_id)
            if status:
                query = query.filter(models.MappingSuggestionRecord.status == status.value)
            return [
                _suggestion_from_record(record)
                for record in query.order_by(models.MappingSuggestionRecord.id.desc()).all()
            ]

        result = list(self._suggestions.values())
        if status:
            result = [s for s in result if s.status == status]
        return result

    def resolve_field_target(
        self,
        source_field: str,
        *,
        sample_values: list[Any] | None = None,
        source_schema: str | None = None,
        org_id: int | None = None,
    ) -> tuple[str | None, dict[str, Any]]:
        """Resolve a field using approved rules before built-in correspondence."""
        target, confidence, metadata = self._infer_target(
            FieldProfile(field_name=source_field, sample_values=sample_values or []),
            source_schema=source_schema,
            org_id=org_id if org_id is not None else self.org_id,
        )
        metadata["confidence"] = confidence
        return target, metadata

    def _infer_target(
        self,
        fp: FieldProfile,
        *,
        source_schema: str | None = None,
        org_id: int | None = None,
    ) -> tuple[str | None, float, dict[str, Any]]:
        """Infer the best canonical target for a field profile."""
        override = self._find_active_rule(fp.field_name, source_schema=source_schema, org_id=org_id)
        if override:
            evidence = ["approved_field_correspondence_rule", *_loads_list(override.evidence)]
            return override.canonical_target, override.confidence or 1.0, {
                "semantic_concept": override.semantic_concept,
                "identifier_scheme": override.identifier_scheme,
                "evidence": evidence,
                "requires_review": False,
            }

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

    def _persist_suggestion(self, suggestion: MappingSuggestion) -> models.MappingSuggestionRecord:
        assert self.db is not None
        existing = self.db.query(models.MappingSuggestionRecord).filter(
            models.MappingSuggestionRecord.org_id == suggestion.org_id,
            models.MappingSuggestionRecord.source_id == suggestion.source_id,
            models.MappingSuggestionRecord.source_schema == suggestion.source_schema,
            models.MappingSuggestionRecord.source_field == suggestion.source_field,
            models.MappingSuggestionRecord.canonical_target == suggestion.canonical_target,
            models.MappingSuggestionRecord.status.notin_([
                SuggestionStatus.REJECTED.value,
                SuggestionStatus.SUPERSEDED.value,
            ]),
        ).first()
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        record = models.MappingSuggestionRecord(
            org_id=suggestion.org_id,
            import_batch_id=suggestion.import_batch_id,
            source_id=suggestion.source_id,
            source_format=suggestion.source_format,
            source_schema=suggestion.source_schema,
            source_field=suggestion.source_field,
            canonical_target=suggestion.canonical_target,
            confidence=suggestion.confidence,
            status=suggestion.status.value if hasattr(suggestion.status, "value") else str(suggestion.status),
            evidence_samples=json.dumps(suggestion.evidence_samples, ensure_ascii=False),
            semantic_concept=suggestion.semantic_concept,
            identifier_scheme=suggestion.identifier_scheme,
            evidence=json.dumps(suggestion.evidence, ensure_ascii=False),
            requires_review=suggestion.requires_review,
            rationale=suggestion.rationale,
            created_at=now,
        )
        self.db.add(record)
        self.db.flush()
        return record

    def _find_active_rule(
        self,
        source_field: str,
        *,
        source_schema: str | None,
        org_id: int | None,
    ) -> models.FieldCorrespondenceRule | None:
        if self.db is None:
            return None
        query = self.db.query(models.FieldCorrespondenceRule).filter(
            models.FieldCorrespondenceRule.source_field == source_field,
            models.FieldCorrespondenceRule.is_active.is_(True),
        )
        if source_schema is None:
            query = query.filter(models.FieldCorrespondenceRule.source_schema.is_(None))
        else:
            query = query.filter(models.FieldCorrespondenceRule.source_schema == source_schema)
        if org_id is None:
            query = query.filter(models.FieldCorrespondenceRule.org_id.is_(None))
        else:
            query = query.filter(models.FieldCorrespondenceRule.org_id == org_id)
        return query.order_by(models.FieldCorrespondenceRule.id.desc()).first()

    def _upsert_rule_from_suggestion(
        self,
        suggestion: models.MappingSuggestionRecord,
        *,
        reviewer_id: int,
    ) -> models.FieldCorrespondenceRule:
        assert self.db is not None
        rule = self._find_active_rule(
            suggestion.source_field,
            source_schema=suggestion.source_schema,
            org_id=suggestion.org_id,
        )
        now = datetime.now(timezone.utc)
        if rule is None:
            rule = models.FieldCorrespondenceRule(
                org_id=suggestion.org_id,
                source_schema=suggestion.source_schema,
                source_field=suggestion.source_field,
                created_at=now,
            )
            self.db.add(rule)
        rule.canonical_target = suggestion.canonical_target
        rule.semantic_concept = suggestion.semantic_concept
        rule.identifier_scheme = suggestion.identifier_scheme
        rule.confidence = 1.0
        rule.evidence = json.dumps(["accepted_mapping_suggestion", *( _loads_list(suggestion.evidence) )], ensure_ascii=False)
        rule.is_active = True
        rule.created_from_suggestion_id = suggestion.id
        rule.created_by_id = reviewer_id
        rule.updated_at = now
        self.db.flush()
        return rule
