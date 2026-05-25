"""RAG Skill Registry — Task 1.6.

Manages skill definitions loaded from static YAML config. Enforces
allowlist scoping (tenant, domain, feature flag) and classifies skills
by governance level.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


class GovernanceLevel(str, Enum):
    ADVISORY = "advisory"
    REVIEW_REQUIRED = "review_required"
    GOVERNED_WRITE_CANDIDATE = "governed_write_candidate"


@dataclass(slots=True)
class SkillDefinition:
    """A registered RAG skill."""

    skill_id: str
    version: str = "1.0"
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    allowed_evidence_types: list[str] = field(default_factory=list)
    governance_level: GovernanceLevel = GovernanceLevel.ADVISORY
    timeout_ms: int = 30_000
    audit_category: str = "general"
    # Scoping
    allowed_tenants: list[str] | None = None   # None = all tenants
    allowed_domains: list[str] | None = None   # None = all domains
    feature_flags: list[str] = field(default_factory=list)
    enabled: bool = True

    def is_advisory(self) -> bool:
        return self.governance_level == GovernanceLevel.ADVISORY

    def is_governed(self) -> bool:
        return self.governance_level == GovernanceLevel.GOVERNED_WRITE_CANDIDATE

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "version": self.version,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "allowed_evidence_types": self.allowed_evidence_types,
            "governance_level": self.governance_level.value,
            "timeout_ms": self.timeout_ms,
            "audit_category": self.audit_category,
            "enabled": self.enabled,
        }


def _parse_governance_level(raw: str | None) -> GovernanceLevel:
    if not raw:
        return GovernanceLevel.ADVISORY
    try:
        return GovernanceLevel(raw)
    except ValueError:
        return GovernanceLevel.ADVISORY


def _parse_skill(raw: dict[str, Any]) -> SkillDefinition | None:
    """Parse a single skill definition dict. Returns None if invalid."""
    skill_id = raw.get("skill_id")
    if not skill_id or not isinstance(skill_id, str):
        logger.warning("Skill definition missing skill_id, skipped")
        return None
    return SkillDefinition(
        skill_id=skill_id,
        version=str(raw.get("version", "1.0")),
        description=str(raw.get("description", "")),
        input_schema=raw.get("input_schema") or {},
        output_schema=raw.get("output_schema") or {},
        allowed_evidence_types=raw.get("allowed_evidence_types") or [],
        governance_level=_parse_governance_level(raw.get("governance_level")),
        timeout_ms=int(raw.get("timeout_ms", 30_000)),
        audit_category=str(raw.get("audit_category", "general")),
        allowed_tenants=raw.get("allowed_tenants"),
        allowed_domains=raw.get("allowed_domains"),
        feature_flags=raw.get("feature_flags") or [],
        enabled=bool(raw.get("enabled", True)),
    )


class RAGSkillRegistry:
    """In-memory registry of RAG skills loaded from YAML config."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    @property
    def skills(self) -> dict[str, SkillDefinition]:
        return dict(self._skills)

    def load_from_yaml(self, path: Path | str) -> int:
        """Load skill definitions from a YAML file. Returns count loaded."""
        path = Path(path)
        if not path.exists():
            logger.warning("Skills YAML not found: %s", path)
            return 0
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return 0
        skills_list = data.get("skills") or []
        if not isinstance(skills_list, list):
            return 0
        count = 0
        for raw in skills_list:
            if not isinstance(raw, dict):
                continue
            skill = _parse_skill(raw)
            if skill:
                self._skills[skill.skill_id] = skill
                count += 1
        logger.info("Loaded %d RAG skills from %s", count, path)
        return count

    def load_from_directory(self, directory: Path | str | None = None) -> int:
        """Load all YAML skill definitions from a directory."""
        directory = Path(directory) if directory else _DEFAULT_SKILLS_DIR
        if not directory.is_dir():
            return 0
        total = 0
        for yaml_file in sorted(directory.glob("*.yaml")):
            total += self.load_from_yaml(yaml_file)
        for yml_file in sorted(directory.glob("*.yml")):
            total += self.load_from_yaml(yml_file)
        return total

    def register(self, skill: SkillDefinition) -> None:
        """Register a skill programmatically."""
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def list_skills(self, enabled_only: bool = True) -> list[SkillDefinition]:
        skills = list(self._skills.values())
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        return skills

    def list_advisory(self) -> list[SkillDefinition]:
        return [s for s in self._skills.values() if s.enabled and s.is_advisory()]

    def list_governed(self) -> list[SkillDefinition]:
        return [s for s in self._skills.values() if s.enabled and s.is_governed()]

    def available_for(
        self,
        *,
        tenant: str | None = None,
        domain: str | None = None,
        active_flags: set[str] | None = None,
    ) -> list[SkillDefinition]:
        """Return skills available for a given tenant/domain/feature-flag context."""
        result: list[SkillDefinition] = []
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            if skill.allowed_tenants is not None and tenant not in skill.allowed_tenants:
                continue
            if skill.allowed_domains is not None and domain not in skill.allowed_domains:
                continue
            if skill.feature_flags:
                if not active_flags or not active_flags.issuperset(skill.feature_flags):
                    continue
            result.append(skill)
        return result

    def is_routable(self, skill_id: str) -> bool:
        """Check if a skill exists and is enabled."""
        skill = self._skills.get(skill_id)
        return skill is not None and skill.enabled
