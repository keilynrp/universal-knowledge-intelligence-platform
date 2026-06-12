from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.enterprise_controls import ENTERPRISE_CONTROLS  # noqa: E402


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def register_rows() -> dict[str, tuple[str, str]]:
    rows = {}
    for line in read("docs/product/ENTERPRISE_CONTROL_REGISTER.md").splitlines():
        if line.startswith("| ER-"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            rows.setdefault(cells[0], (cells[2], cells[3]))
    return rows


def validate() -> list[str]:
    errors = []
    manifest = {
        control.control_id: (control.priority, control.current_maturity)
        for control in ENTERPRISE_CONTROLS
    }
    if register_rows() != manifest:
        errors.append("control register and machine manifest differ")
    epic = read("docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md")
    backlog = read("docs/product/PROGRAM_BACKLOG.md")
    traceability = read("docs/product/TRACEABILITY_MATRIX.md")
    for control in ENTERPRISE_CONTROLS:
        if control.control_id not in epic:
            errors.append(f"{control.control_id} missing from EPIC-018")
        if control.control_id not in traceability:
            errors.append(f"{control.control_id} missing from traceability")
        for work_id in control.related_work:
            for name, content in (("EPIC-018", epic), ("backlog", backlog), ("traceability", traceability)):
                if work_id not in content:
                    errors.append(f"{work_id} missing from {name}")
    for path in ("docs/UKIP_ENTERPRISE_ROADMAP.md", "docs/ukip_system_evaluation.md"):
        if not read(path).startswith("> **Status: Historical"):
            errors.append(f"{path} lacks Historical notice")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Enterprise readiness documentation is aligned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
