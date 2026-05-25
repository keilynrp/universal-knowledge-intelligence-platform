"""Tests for Task 1.6 — RAG Skill Registry."""
import tempfile
from pathlib import Path

import yaml

from backend.services.rag_skill_registry import (
    GovernanceLevel,
    RAGSkillRegistry,
    SkillDefinition,
)


def _write_yaml(tmp_dir: Path, filename: str, data: dict) -> Path:
    path = tmp_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    return path


class TestSkillDefinition:
    def test_default_values(self):
        skill = SkillDefinition(skill_id="test")
        assert skill.version == "1.0"
        assert skill.governance_level == GovernanceLevel.ADVISORY
        assert skill.timeout_ms == 30_000
        assert skill.enabled is True

    def test_is_advisory(self):
        skill = SkillDefinition(skill_id="s1", governance_level=GovernanceLevel.ADVISORY)
        assert skill.is_advisory()
        assert not skill.is_governed()

    def test_is_governed(self):
        skill = SkillDefinition(skill_id="s2", governance_level=GovernanceLevel.GOVERNED_WRITE_CANDIDATE)
        assert skill.is_governed()
        assert not skill.is_advisory()

    def test_to_dict(self):
        skill = SkillDefinition(skill_id="s3", description="Test skill")
        d = skill.to_dict()
        assert d["skill_id"] == "s3"
        assert d["governance_level"] == "advisory"


class TestRegistryLoadFromYaml:
    def test_load_valid_yaml(self, tmp_path):
        data = {
            "skills": [
                {
                    "skill_id": "summarize",
                    "description": "Summarize entities",
                    "governance_level": "advisory",
                    "timeout_ms": 10000,
                },
                {
                    "skill_id": "write_candidates",
                    "governance_level": "governed_write_candidate",
                },
            ]
        }
        path = _write_yaml(tmp_path, "skills.yaml", data)
        registry = RAGSkillRegistry()
        count = registry.load_from_yaml(path)
        assert count == 2
        assert registry.get("summarize") is not None
        assert registry.get("write_candidates").governance_level == GovernanceLevel.GOVERNED_WRITE_CANDIDATE

    def test_invalid_definition_rejected(self, tmp_path):
        data = {
            "skills": [
                {"description": "Missing skill_id"},
                {"skill_id": "", "description": "Empty skill_id"},
                {"skill_id": "valid_one"},
            ]
        }
        path = _write_yaml(tmp_path, "skills.yaml", data)
        registry = RAGSkillRegistry()
        count = registry.load_from_yaml(path)
        assert count == 1
        assert registry.get("valid_one") is not None

    def test_missing_file(self, tmp_path):
        registry = RAGSkillRegistry()
        count = registry.load_from_yaml(tmp_path / "nonexistent.yaml")
        assert count == 0

    def test_load_from_directory(self, tmp_path):
        _write_yaml(tmp_path, "a.yaml", {"skills": [{"skill_id": "s1"}]})
        _write_yaml(tmp_path, "b.yml", {"skills": [{"skill_id": "s2"}]})
        registry = RAGSkillRegistry()
        count = registry.load_from_directory(tmp_path)
        assert count == 2
        assert registry.get("s1") is not None
        assert registry.get("s2") is not None


class TestDisabledSkillNotRoutable:
    def test_disabled_skill(self):
        registry = RAGSkillRegistry()
        registry.register(SkillDefinition(skill_id="disabled", enabled=False))
        assert not registry.is_routable("disabled")
        assert registry.is_routable("disabled") is False

    def test_enabled_skill(self):
        registry = RAGSkillRegistry()
        registry.register(SkillDefinition(skill_id="active"))
        assert registry.is_routable("active")

    def test_nonexistent_skill(self):
        registry = RAGSkillRegistry()
        assert not registry.is_routable("nope")


class TestAllowlistEnforcement:
    def test_tenant_scoping(self):
        registry = RAGSkillRegistry()
        registry.register(SkillDefinition(skill_id="s1", allowed_tenants=["acme"]))
        registry.register(SkillDefinition(skill_id="s2", allowed_tenants=None))

        available = registry.available_for(tenant="acme")
        ids = {s.skill_id for s in available}
        assert "s1" in ids
        assert "s2" in ids

        available = registry.available_for(tenant="other")
        ids = {s.skill_id for s in available}
        assert "s1" not in ids
        assert "s2" in ids

    def test_domain_scoping(self):
        registry = RAGSkillRegistry()
        registry.register(SkillDefinition(skill_id="sci", allowed_domains=["science"]))
        registry.register(SkillDefinition(skill_id="all"))

        available = registry.available_for(domain="science")
        ids = {s.skill_id for s in available}
        assert "sci" in ids
        assert "all" in ids

        available = registry.available_for(domain="healthcare")
        ids = {s.skill_id for s in available}
        assert "sci" not in ids
        assert "all" in ids

    def test_feature_flag_scoping(self):
        registry = RAGSkillRegistry()
        registry.register(SkillDefinition(skill_id="beta", feature_flags=["beta_rag"]))
        registry.register(SkillDefinition(skill_id="stable"))

        available = registry.available_for(active_flags=set())
        ids = {s.skill_id for s in available}
        assert "beta" not in ids
        assert "stable" in ids

        available = registry.available_for(active_flags={"beta_rag"})
        ids = {s.skill_id for s in available}
        assert "beta" in ids

    def test_disabled_excluded(self):
        registry = RAGSkillRegistry()
        registry.register(SkillDefinition(skill_id="off", enabled=False))
        available = registry.available_for()
        assert len(available) == 0


class TestListSkills:
    def test_list_enabled_only(self):
        registry = RAGSkillRegistry()
        registry.register(SkillDefinition(skill_id="a", enabled=True))
        registry.register(SkillDefinition(skill_id="b", enabled=False))
        assert len(registry.list_skills(enabled_only=True)) == 1
        assert len(registry.list_skills(enabled_only=False)) == 2

    def test_list_advisory_and_governed(self):
        registry = RAGSkillRegistry()
        registry.register(SkillDefinition(skill_id="adv", governance_level=GovernanceLevel.ADVISORY))
        registry.register(SkillDefinition(skill_id="gov", governance_level=GovernanceLevel.GOVERNED_WRITE_CANDIDATE))
        registry.register(SkillDefinition(skill_id="rev", governance_level=GovernanceLevel.REVIEW_REQUIRED))
        assert len(registry.list_advisory()) == 1
        assert len(registry.list_governed()) == 1


class TestLoadDefaultSkills:
    def test_default_skills_file_loads(self):
        skills_path = Path(__file__).resolve().parent.parent / "backend" / "skills" / "default_skills.yaml"
        if not skills_path.exists():
            return  # skip if not in expected path
        registry = RAGSkillRegistry()
        count = registry.load_from_yaml(skills_path)
        assert count >= 3
        assert registry.get("summarize_entities") is not None
        assert registry.get("suggest_authority_candidates") is not None
        assert registry.get("suggest_authority_candidates").is_governed()
