from pathlib import Path
import subprocess
import sys

from backend.enterprise_controls import ENTERPRISE_CONTROLS


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_enterprise_authority_hierarchy_is_documented():
    governance = _read("docs/DOCUMENTATION_GOVERNANCE.md")
    product_index = _read("docs/product/README.md")
    required = [
        "docs/product/ENTERPRISE_CONTROL_REGISTER.md",
        "docs/product/ENTERPRISE_READINESS_PROGRAM.md",
        "docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md",
        "docs/product/TRACEABILITY_MATRIX.md",
    ]
    for path in required:
        assert path in governance
        assert path in product_index
    assert "Control status" in governance
    assert "Runtime projection" in governance


def test_control_register_matches_machine_manifest():
    rows = {}
    for line in _read("docs/product/ENTERPRISE_CONTROL_REGISTER.md").splitlines():
        if line.startswith("| ER-"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            rows.setdefault(cells[0], (cells[2], cells[3]))
    assert rows == {
        control.control_id: (control.priority, control.current_maturity)
        for control in ENTERPRISE_CONTROLS
    }


def test_enterprise_story_contracts_exist():
    paths = sorted((ROOT / "docs/product/stories").glob("US-07[3-9]-*.md"))
    paths += sorted((ROOT / "docs/product/stories").glob("US-08[0-1]-*.md"))
    assert len(paths) == 9
    required = (
        "## 1. User story", "## 2. Control outcome", "## 3. Scope",
        "## 4. Acceptance criteria", "## 5. Failure and abuse cases",
        "## 6. Operational acceptance", "## 7. Evidence",
        "## 8. Rollout and rollback", "## 9. Definition of Enterprise Done",
    )
    for path in paths:
        content = path.read_text(encoding="utf-8")
        assert "EPIC-018" in content
        for section in required:
            assert section in content


def test_superseded_enterprise_docs_have_historical_notice():
    for path in ("docs/UKIP_ENTERPRISE_ROADMAP.md", "docs/ukip_system_evaluation.md"):
        content = _read(path)
        assert content.startswith("> **Status: Historical")
        assert "docs/product/ENTERPRISE_READINESS_PROGRAM.md" in content
        assert "docs/product/ENTERPRISE_CONTROL_REGISTER.md" in content


def test_enterprise_readiness_lint_passes_repository_state():
    result = subprocess.run(
        [sys.executable, "scripts/lint_enterprise_readiness.py"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
