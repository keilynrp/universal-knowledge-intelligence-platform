# Enterprise Readiness Operational Source of Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make UKIP's enterprise control register, delivery backlog, runtime readiness endpoint, and historical documentation operate as one drift-resistant source of truth for regulated institutional procurement readiness.

**Architecture:** Keep `ENTERPRISE_CONTROL_REGISTER.md` human-authoritative and add a typed Python companion manifest for runtime use. Enforce stable-ID parity and cross-document references with a focused lint script and tests, while stories, backlog, and traceability describe delivery without independently redefining control maturity.

**Tech Stack:** Markdown, Python 3.11+, dataclasses/standard library, pytest, FastAPI test client, GitHub Actions.

---

## File Map

**Create**

- `backend/enterprise_controls.py` - typed machine-readable control manifest and report helpers.
- `scripts/lint_enterprise_readiness.py` - validates register, stories, traceability, runtime parity, and historical classification.
- `backend/tests/test_enterprise_controls.py` - unit tests for manifest integrity and report aggregation.
- `backend/tests/test_enterprise_readiness_docs.py` - repository-level tests for documentation parity.
- `docs/product/stories/US-073-backup-restore-rto-rpo-disaster-recovery.md`
- `docs/product/stories/US-074-secure-sdlc-sbom-vulnerability-management.md`
- `docs/product/stories/US-075-audit-evidence-pack-integrity-verification.md`
- `docs/product/stories/US-076-privacy-legal-subprocessor-assurance.md`
- `docs/product/stories/US-077-enterprise-identity-lifecycle-mfa-offboarding.md`
- `docs/product/stories/US-078-deployment-topology-data-residency-governance.md`
- `docs/product/stories/US-079-incident-response-customer-notification.md`
- `docs/product/stories/US-080-capacity-load-degradation-envelope.md`
- `docs/product/stories/US-081-independent-assurance-enterprise-pilot-exit.md`

**Modify**

- `docs/DOCUMENTATION_GOVERNANCE.md` - add the enterprise authority hierarchy.
- `docs/README.md` - expose the enterprise operational reading path.
- `docs/product/README.md` - identify the program and register as operational authorities.
- `docs/product/ENTERPRISE_READINESS_PROGRAM.md` - align target, waves, ownership, and implementation order.
- `docs/product/ENTERPRISE_CONTROL_REGISTER.md` - normalize complete control metadata and next gates.
- `docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md` - synchronize stories, controls, and phase gates.
- `docs/product/PROGRAM_BACKLOG.md` - remove the historical roadmap as an active source and add ordered enterprise work.
- `docs/product/TRACEABILITY_MATRIX.md` - replace the aggregate EPIC-018 row with control-level traceability.
- `backend/enterprise_readiness.py` - become a compatibility wrapper over `enterprise_controls.py`.
- `backend/tests/test_sprint104_enterprise_readiness.py` - assert the new control-oriented API contract.
- `.github/workflows/lint.yml` - add the blocking enterprise-readiness documentation check.
- `docs/UKIP_ENTERPRISE_ROADMAP.md` - add a prominent historical notice.
- `docs/ukip_system_evaluation.md` - add a dated-assessment notice.
- `docs/reference/HISTORICAL_REFERENCE_INDEX.md` - link historical documents to their replacements.

### Task 1: Establish the Enterprise Authority Hierarchy

**Files:**
- Modify: `docs/DOCUMENTATION_GOVERNANCE.md`
- Modify: `docs/README.md`
- Modify: `docs/product/README.md`
- Test: `backend/tests/test_enterprise_readiness_docs.py`

- [ ] **Step 1: Write a failing authority test**

Create `backend/tests/test_enterprise_readiness_docs.py`:

```python
from pathlib import Path


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
```

- [ ] **Step 2: Run the authority test and verify failure**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py::test_enterprise_authority_hierarchy_is_documented -v
```

Expected: FAIL because the authority hierarchy is not yet explicit in both documents.

- [ ] **Step 3: Add the authority hierarchy**

Add an `Enterprise readiness authority` section to `docs/DOCUMENTATION_GOVERNANCE.md` with this precedence:

```markdown
## Enterprise readiness authority

For enterprise-readiness work, authority is:

1. Control status: `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
2. Maturity and claim policy: `docs/product/ENTERPRISE_READINESS_PROGRAM.md`
3. Program execution: `docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md`
4. Delivery units: `docs/product/stories/US-042*` and `US-073` through `US-081`
5. Portfolio sequence: `docs/product/PROGRAM_BACKLOG.md`
6. Control-to-evidence mapping: `docs/product/TRACEABILITY_MATRIX.md`
7. Runtime projection: `backend/enterprise_readiness.py`

The runtime projection never overrides the control register.
```

Add the same files under an `Enterprise readiness` subsection in `docs/README.md`
and `docs/product/README.md`. State that historical roadmaps cannot set current
priority or maturity.

- [ ] **Step 4: Run the authority test**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py::test_enterprise_authority_hierarchy_is_documented -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add docs/DOCUMENTATION_GOVERNANCE.md docs/README.md docs/product/README.md backend/tests/test_enterprise_readiness_docs.py
git commit -m "docs: establish enterprise readiness authority"
```

### Task 2: Add the Typed Enterprise Control Manifest

**Files:**
- Create: `backend/enterprise_controls.py`
- Create: `backend/tests/test_enterprise_controls.py`

- [ ] **Step 1: Write failing manifest tests**

Create `backend/tests/test_enterprise_controls.py`:

```python
from backend.enterprise_controls import (
    CONTROL_MATURITY_ORDER,
    ENTERPRISE_CONTROLS,
    build_enterprise_readiness_report,
)


EXPECTED_IDS = {
    "ER-CTRL-001",
    "ER-OPS-001",
    "ER-BCP-001",
    "ER-SDLC-001",
    "ER-AUD-001",
    "ER-PRIV-001",
    "ER-IAM-001",
    "ER-DEP-001",
    "ER-IR-001",
    "ER-PERF-001",
    "ER-ASSURE-001",
}


def test_manifest_has_unique_expected_control_ids():
    ids = [control.control_id for control in ENTERPRISE_CONTROLS]
    assert set(ids) == EXPECTED_IDS
    assert len(ids) == len(set(ids))


def test_every_control_has_delivery_and_next_gate():
    for control in ENTERPRISE_CONTROLS:
        assert control.owner
        assert control.related_work
        assert control.next_gate
        assert control.current_maturity in CONTROL_MATURITY_ORDER
        assert control.target_maturity in CONTROL_MATURITY_ORDER


def test_report_aggregates_by_priority_and_maturity():
    report = build_enterprise_readiness_report()
    assert report["status"] == "enterprise_readiness_program"
    assert report["target_claim"] == "regulated_institutional_enterprise_ready"
    assert report["summary"]["total_controls"] == len(ENTERPRISE_CONTROLS)
    assert sum(report["summary"]["priority_counts"].values()) == len(ENTERPRISE_CONTROLS)
    assert sum(report["summary"]["maturity_counts"].values()) == len(ENTERPRISE_CONTROLS)
```

- [ ] **Step 2: Run tests and verify import failure**

Run:

```powershell
pytest backend/tests/test_enterprise_controls.py -v
```

Expected: FAIL with `ModuleNotFoundError: backend.enterprise_controls`.

- [ ] **Step 3: Implement the typed manifest**

Create `backend/enterprise_controls.py` with:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


Priority = Literal["P0", "P1", "P2"]
Maturity = Literal[
    "identified",
    "specified",
    "implemented",
    "verified",
    "operated",
    "auditable",
]

CONTROL_MATURITY_ORDER = {
    "identified": 0,
    "specified": 1,
    "implemented": 2,
    "verified": 3,
    "operated": 4,
    "auditable": 5,
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
REGISTER_UPDATED_AT = "2026-06-12"


@dataclass(frozen=True)
class EnterpriseControl:
    control_id: str
    title: str
    objective: str
    priority: Priority
    current_maturity: Maturity
    target_maturity: Maturity
    owner: str
    related_work: tuple[str, ...]
    next_gate: str
    evidence_summary: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["related_work"] = list(self.related_work)
        payload["evidence_summary"] = list(self.evidence_summary)
        return payload
```

Define all 11 controls using the exact priority, maturity, owner, and related
story from `ENTERPRISE_CONTROL_REGISTER.md`. Add:

```python
def build_enterprise_readiness_report() -> dict:
    controls = sorted(
        (control.to_dict() for control in ENTERPRISE_CONTROLS),
        key=lambda item: (
            PRIORITY_ORDER[item["priority"]],
            item["control_id"],
        ),
    )
    return {
        "status": "enterprise_readiness_program",
        "service": "ukip-backend",
        "target_claim": "regulated_institutional_enterprise_ready",
        "updated_at": REGISTER_UPDATED_AT,
        "summary": {
            "total_controls": len(controls),
            "priority_counts": {
                priority: sum(item["priority"] == priority for item in controls)
                for priority in PRIORITY_ORDER
            },
            "maturity_counts": {
                maturity: sum(
                    item["current_maturity"] == maturity for item in controls
                )
                for maturity in CONTROL_MATURITY_ORDER
            },
        },
        "controls": controls,
        "claim_disclaimer": (
            "This report does not assert certification or unqualified "
            "enterprise readiness."
        ),
    }
```

- [ ] **Step 4: Run manifest tests**

Run:

```powershell
pytest backend/tests/test_enterprise_controls.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/enterprise_controls.py backend/tests/test_enterprise_controls.py
git commit -m "feat: add enterprise control manifest"
```

### Task 3: Normalize the Program and Control Register

**Files:**
- Modify: `docs/product/ENTERPRISE_READINESS_PROGRAM.md`
- Modify: `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
- Test: `backend/tests/test_enterprise_readiness_docs.py`

- [ ] **Step 1: Add failing register parity tests**

Append:

```python
import re

from backend.enterprise_controls import ENTERPRISE_CONTROLS


def _register_rows() -> dict[str, tuple[str, str]]:
    register = _read("docs/product/ENTERPRISE_CONTROL_REGISTER.md")
    rows = {}
    for line in register.splitlines():
        if not line.startswith("| ER-"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        rows[cells[0]] = (cells[2], cells[3])
    return rows


def test_control_register_matches_machine_manifest():
    rows = _register_rows()
    expected = {
        control.control_id: (control.priority, control.current_maturity)
        for control in ENTERPRISE_CONTROLS
    }
    assert rows == expected


def test_program_declares_complete_maturity_model():
    program = _read("docs/product/ENTERPRISE_READINESS_PROGRAM.md")
    for maturity in (
        "identified",
        "specified",
        "implemented",
        "verified",
        "operated",
        "auditable",
    ):
        assert re.search(rf"`{maturity}`", program)
```

- [ ] **Step 2: Run parity tests**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py -v
```

Expected: FAIL until register values and manifest values are aligned exactly.

- [ ] **Step 3: Normalize the program**

Update `ENTERPRISE_READINESS_PROGRAM.md` to:

- name regulated institutional customers and demanding procurement as the target;
- preserve the six-state maturity model;
- include all 11 controls in sequence;
- use the dependency order from the approved design;
- state the three owner roles;
- state that Markdown register is human-authoritative and Python manifest is its
  validated runtime companion;
- set `Updated: 2026-06-12`.

- [ ] **Step 4: Normalize the register**

For each control, retain the summary table and add a detail subsection:

```markdown
### ER-BCP-001 - Backup, restore, RTO/RPO, and disaster recovery

- Priority: `P0`
- Current maturity: `identified`
- Target maturity: `auditable`
- Control owner: Operations owner
- Implementation owner: Platform owner
- Operational owner: Operations owner
- Related work: `US-073`
- Dependencies: PostgreSQL-first runtime, production storage inventory
- Next gate: approve RTO/RPO and complete the backup/restore design
- Observation window: two successful scheduled backup cycles plus one restore drill
- Evidence retention: release evidence pack plus 12 months of drill reports
- Residual risk: recovery objectives remain unproven until a restore drill passes
```

Add equivalent concrete metadata for all 11 controls. Do not raise maturity
based on this documentation change.

- [ ] **Step 5: Run register tests**

Run:

```powershell
pytest backend/tests/test_enterprise_controls.py backend/tests/test_enterprise_readiness_docs.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add docs/product/ENTERPRISE_READINESS_PROGRAM.md docs/product/ENTERPRISE_CONTROL_REGISTER.md backend/tests/test_enterprise_readiness_docs.py
git commit -m "docs: normalize enterprise control program"
```

### Task 4: Create US-073 Through US-081

**Files:**
- Create: the nine story files for `US-073`, `US-074`, `US-075`, `US-076`,
  `US-077`, `US-078`, `US-079`, `US-080`, and `US-081` listed in File Map.
- Modify: `backend/tests/test_enterprise_readiness_docs.py`

- [ ] **Step 1: Write a failing story existence and contract test**

Append:

```python
STORY_FILES = {
    "US-073": "docs/product/stories/US-073-backup-restore-rto-rpo-disaster-recovery.md",
    "US-074": "docs/product/stories/US-074-secure-sdlc-sbom-vulnerability-management.md",
    "US-075": "docs/product/stories/US-075-audit-evidence-pack-integrity-verification.md",
    "US-076": "docs/product/stories/US-076-privacy-legal-subprocessor-assurance.md",
    "US-077": "docs/product/stories/US-077-enterprise-identity-lifecycle-mfa-offboarding.md",
    "US-078": "docs/product/stories/US-078-deployment-topology-data-residency-governance.md",
    "US-079": "docs/product/stories/US-079-incident-response-customer-notification.md",
    "US-080": "docs/product/stories/US-080-capacity-load-degradation-envelope.md",
    "US-081": "docs/product/stories/US-081-independent-assurance-enterprise-pilot-exit.md",
}


def test_enterprise_story_contracts_exist():
    required_sections = (
        "## 1. User story",
        "## 2. Control outcome",
        "## 3. Scope",
        "## 4. Acceptance criteria",
        "## 5. Failure and abuse cases",
        "## 6. Operational acceptance",
        "## 7. Evidence",
        "## 8. Rollout and rollback",
        "## 9. Definition of Enterprise Done",
    )
    for story_id, path in STORY_FILES.items():
        content = _read(path)
        assert content.startswith(f"# {story_id} ")
        assert "EPIC-018" in content
        for section in required_sections:
            assert section in content
```

- [ ] **Step 2: Run story test**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py::test_enterprise_story_contracts_exist -v
```

Expected: FAIL with missing story files.

- [ ] **Step 3: Create US-073, US-074, and US-075**

Use the required section contract and these control outcomes:

- `US-073` / `ER-BCP-001`: measured backup and restore with approved RTO/RPO,
  automated schedule, encrypted off-host storage, restoration drill, and
  documented loss boundary.
- `US-074` / `ER-SDLC-001`: blocking CodeQL, Gitleaks, pip/npm audit, Trivy,
  SBOM retention, vulnerability SLA, branch protection, and 30-day operation.
- `US-075` / `ER-AUD-001`: tenant-scoped evidence export, canonical manifest,
  hash/signature verification, retention, redaction, access audit, and
  independent verification command.

Each story must name target maturity, exact observation window, evidence
artifacts, rollback behavior, and residual risk.

- [ ] **Step 4: Create US-076, US-077, and US-078**

Use these outcomes:

- `US-076` / `ER-PRIV-001`: externally reviewed DPA, ROPA, subprocessors,
  privacy controls, transfer/residency statements, version ownership, and
  annual review.
- `US-077` / `ER-IAM-001`: MFA enforcement, joiner/mover/leaver lifecycle,
  SCIM or documented governed alternative, session/API-key revocation, break
  glass, and offboarding drill.
- `US-078` / `ER-DEP-001`: supported topology matrix, region pinning policy,
  data-flow inventory, backup and subprocessor locations, customer exit/export,
  and prohibited deployment claims.

- [ ] **Step 5: Create US-079, US-080, and US-081**

Use these outcomes:

- `US-079` / `ER-IR-001`: severity model, ownership, detection-to-containment
  workflow, forensic evidence preservation, customer notification decision
  process, tabletop exercise, and corrective actions.
- `US-080` / `ER-PERF-001`: supported workload profiles, load tests, p95/p99
  targets, queue saturation behavior, graceful degradation, capacity alerts,
  and published operating envelope.
- `US-081` / `ER-ASSURE-001`: independent penetration test, remediation and
  retest, production-like pilot observation window, unresolved-risk review, and
  executive exit decision.

- [ ] **Step 6: Run story contract test**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py::test_enterprise_story_contracts_exist -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add docs/product/stories/US-073* docs/product/stories/US-074* docs/product/stories/US-075* docs/product/stories/US-076* docs/product/stories/US-077* docs/product/stories/US-078* docs/product/stories/US-079* docs/product/stories/US-080* docs/product/stories/US-081* backend/tests/test_enterprise_readiness_docs.py
git commit -m "docs: define enterprise assurance stories"
```

### Task 5: Align EPIC-018, Backlog, and Traceability

**Files:**
- Modify: `docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md`
- Modify: `docs/product/PROGRAM_BACKLOG.md`
- Modify: `docs/product/TRACEABILITY_MATRIX.md`
- Modify: `backend/tests/test_enterprise_readiness_docs.py`

- [ ] **Step 1: Write failing portfolio parity tests**

Append:

```python
def test_epic_backlog_and_traceability_reference_every_control_and_story():
    epic = _read(
        "docs/product/epics/"
        "EPIC-018-enterprise-assurance-and-operational-readiness.md"
    )
    backlog = _read("docs/product/PROGRAM_BACKLOG.md")
    traceability = _read("docs/product/TRACEABILITY_MATRIX.md")

    for control in ENTERPRISE_CONTROLS:
        assert control.control_id in epic
        assert control.control_id in traceability
        for work_id in control.related_work:
            if work_id.startswith("US-"):
                assert work_id in epic
                assert work_id in backlog
                assert work_id in traceability


def test_operational_backlog_does_not_use_historical_enterprise_roadmap():
    backlog = _read("docs/product/PROGRAM_BACKLOG.md")
    assert "`docs/UKIP_ENTERPRISE_ROADMAP.md`" not in backlog
```

- [ ] **Step 2: Run portfolio tests**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py -v
```

Expected: FAIL because controls and stories are currently aggregated.

- [ ] **Step 3: Expand EPIC-018**

Update the epic to include:

- the regulated institutional target;
- all 11 controls and their delivery units;
- six implementation phases from the approved design;
- dependencies and release posture;
- explicit separation between story state and control maturity;
- success criteria requiring no P0/P1 below the permitted target.

- [ ] **Step 4: Add ordered enterprise backlog**

Replace `UKIP_ENTERPRISE_ROADMAP.md` under active strategic sources with:

```markdown
- `docs/product/ENTERPRISE_READINESS_PROGRAM.md`
- `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
- `docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md`
```

Add an `Enterprise readiness execution order` table with one row per
`US-042`, `US-073` through `US-081`, including control, priority, dependency,
delivery state, and target maturity.

- [ ] **Step 5: Expand traceability to one row per control**

Replace the aggregate EPIC-018 row with 11 rows. Each row must contain:

- objective;
- `EPIC-018`;
- related story;
- sprint state as `Unscheduled` until assigned to a numbered sprint;
- spec/code/test evidence that already exists;
- required operational evidence;
- current maturity.

Use `ER-CTRL-001` as the story-independent governance row.

- [ ] **Step 6: Run portfolio tests**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md docs/product/PROGRAM_BACKLOG.md docs/product/TRACEABILITY_MATRIX.md backend/tests/test_enterprise_readiness_docs.py
git commit -m "docs: align enterprise backlog and traceability"
```

### Task 6: Replace the Legacy Runtime Gap Model

**Files:**
- Modify: `backend/enterprise_readiness.py`
- Modify: `backend/tests/test_sprint104_enterprise_readiness.py`
- Test: `backend/tests/test_enterprise_controls.py`

- [ ] **Step 1: Rewrite endpoint tests for the control contract**

Replace legacy gap assertions with:

```python
from backend.enterprise_controls import ENTERPRISE_CONTROLS


def test_enterprise_readiness_returns_control_program(client, auth_headers):
    response = client.get("/ops/enterprise-readiness", headers=auth_headers)
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "enterprise_readiness_program"
    assert body["target_claim"] == "regulated_institutional_enterprise_ready"
    assert body["summary"]["total_controls"] == len(ENTERPRISE_CONTROLS)
    assert {item["control_id"] for item in body["controls"]} == {
        control.control_id for control in ENTERPRISE_CONTROLS
    }


def test_enterprise_controls_expose_next_gate_and_evidence(client, auth_headers):
    body = client.get(
        "/ops/enterprise-readiness", headers=auth_headers
    ).json()
    for control in body["controls"]:
        assert control["owner"]
        assert control["next_gate"]
        assert control["related_work"]
        assert "current_maturity" in control
        assert "target_maturity" in control


def test_enterprise_readiness_includes_non_certification_disclaimer(
    client, auth_headers
):
    body = client.get(
        "/ops/enterprise-readiness", headers=auth_headers
    ).json()
    assert "does not assert certification" in body["claim_disclaimer"]
```

Keep the existing admin authorization test.

- [ ] **Step 2: Run endpoint tests and verify failure**

Run:

```powershell
pytest backend/tests/test_sprint104_enterprise_readiness.py -v
```

Expected: FAIL because the endpoint still returns `gaps` and `resolved`.

- [ ] **Step 3: Convert the legacy module to a wrapper**

Replace `backend/enterprise_readiness.py` with:

```python
"""Compatibility entry point for the enterprise control report."""

from backend.enterprise_controls import build_enterprise_readiness_report


def get_enterprise_readiness_report() -> dict:
    return build_enterprise_readiness_report()
```

- [ ] **Step 4: Run focused backend tests**

Run:

```powershell
pytest backend/tests/test_enterprise_controls.py backend/tests/test_sprint104_enterprise_readiness.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/enterprise_readiness.py backend/enterprise_controls.py backend/tests/test_enterprise_controls.py backend/tests/test_sprint104_enterprise_readiness.py
git commit -m "refactor: project enterprise controls through ops API"
```

### Task 7: Classify Superseded Assessments as Historical

**Files:**
- Modify: `docs/UKIP_ENTERPRISE_ROADMAP.md`
- Modify: `docs/ukip_system_evaluation.md`
- Modify: `docs/reference/HISTORICAL_REFERENCE_INDEX.md`
- Modify: `backend/tests/test_enterprise_readiness_docs.py`

- [ ] **Step 1: Write a failing historical notice test**

Append:

```python
def test_superseded_enterprise_docs_have_historical_notice():
    replacements = (
        "docs/product/ENTERPRISE_READINESS_PROGRAM.md",
        "docs/product/ENTERPRISE_CONTROL_REGISTER.md",
    )
    for path in (
        "docs/UKIP_ENTERPRISE_ROADMAP.md",
        "docs/ukip_system_evaluation.md",
    ):
        content = _read(path)
        assert content.startswith("> **Status: Historical")
        for replacement in replacements:
            assert replacement in content
```

- [ ] **Step 2: Run the test**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py::test_superseded_enterprise_docs_have_historical_notice -v
```

Expected: FAIL because the notices are absent.

- [ ] **Step 3: Add notices and replacement links**

Prepend both historical documents with:

```markdown
> **Status: Historical.** This dated assessment does not govern current
> enterprise-readiness scope, priority, or maturity. Use
> `docs/product/ENTERPRISE_READINESS_PROGRAM.md` and
> `docs/product/ENTERPRISE_CONTROL_REGISTER.md`.
```

Update the historical index descriptions to name those replacements explicitly.

- [ ] **Step 4: Run the historical notice test**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py::test_superseded_enterprise_docs_have_historical_notice -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add docs/UKIP_ENTERPRISE_ROADMAP.md docs/ukip_system_evaluation.md docs/reference/HISTORICAL_REFERENCE_INDEX.md backend/tests/test_enterprise_readiness_docs.py
git commit -m "docs: classify legacy enterprise assessments"
```

### Task 8: Add the Drift-Detection Lint

**Files:**
- Create: `scripts/lint_enterprise_readiness.py`
- Modify: `.github/workflows/lint.yml`
- Modify: `backend/tests/test_enterprise_readiness_docs.py`

- [ ] **Step 1: Write failing lint behavior tests**

Append:

```python
import subprocess
import sys


def test_enterprise_readiness_lint_passes_repository_state():
    result = subprocess.run(
        [sys.executable, "scripts/lint_enterprise_readiness.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Enterprise readiness documentation is aligned." in result.stdout
```

- [ ] **Step 2: Run lint test and verify missing-script failure**

Run:

```powershell
pytest backend/tests/test_enterprise_readiness_docs.py::test_enterprise_readiness_lint_passes_repository_state -v
```

Expected: FAIL because the script does not exist.

- [ ] **Step 3: Implement the lint script**

Create `scripts/lint_enterprise_readiness.py` with standard-library checks:

```python
from __future__ import annotations

import re
import sys
from pathlib import Path

from backend.enterprise_controls import CONTROL_MATURITY_ORDER, ENTERPRISE_CONTROLS


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def register_rows() -> dict[str, tuple[str, str]]:
    rows = {}
    for line in read("docs/product/ENTERPRISE_CONTROL_REGISTER.md").splitlines():
        if line.startswith("| ER-"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            rows[cells[0]] = (cells[2], cells[3])
    return rows


def validate() -> list[str]:
    errors = []
    manifest = {
        control.control_id: (control.priority, control.current_maturity)
        for control in ENTERPRISE_CONTROLS
    }
    rows = register_rows()
    if rows != manifest:
        errors.append(f"register/manifest mismatch: {rows!r} != {manifest!r}")

    epic = read(
        "docs/product/epics/"
        "EPIC-018-enterprise-assurance-and-operational-readiness.md"
    )
    backlog = read("docs/product/PROGRAM_BACKLOG.md")
    traceability = read("docs/product/TRACEABILITY_MATRIX.md")
    for control in ENTERPRISE_CONTROLS:
        for document_name, content in (
            ("EPIC-018", epic),
            ("TRACEABILITY_MATRIX", traceability),
        ):
            if control.control_id not in content:
                errors.append(
                    f"{control.control_id} missing from {document_name}"
                )
        for work_id in control.related_work:
            if work_id.startswith("US-"):
                for document_name, content in (
                    ("EPIC-018", epic),
                    ("PROGRAM_BACKLOG", backlog),
                    ("TRACEABILITY_MATRIX", traceability),
                ):
                    if work_id not in content:
                        errors.append(f"{work_id} missing from {document_name}")

    for maturity in re.findall(
        r"\|\s*(identified|specified|implemented|verified|operated|auditable)\s*\|",
        read("docs/product/ENTERPRISE_CONTROL_REGISTER.md"),
    ):
        if maturity not in CONTROL_MATURITY_ORDER:
            errors.append(f"unsupported maturity: {maturity}")

    for path in (
        "docs/UKIP_ENTERPRISE_ROADMAP.md",
        "docs/ukip_system_evaluation.md",
    ):
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
```

- [ ] **Step 4: Add blocking CI job**

Add to `.github/workflows/lint.yml`:

```yaml
  enterprise-readiness-lint:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v6

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - name: Enforce enterprise readiness source of truth
        run: python scripts/lint_enterprise_readiness.py
```

- [ ] **Step 5: Run lint and docs tests**

Run:

```powershell
python scripts/lint_enterprise_readiness.py
pytest backend/tests/test_enterprise_readiness_docs.py -v
```

Expected:

```text
Enterprise readiness documentation is aligned.
```

and all tests PASS.

- [ ] **Step 6: Commit**

```powershell
git add scripts/lint_enterprise_readiness.py .github/workflows/lint.yml backend/tests/test_enterprise_readiness_docs.py
git commit -m "ci: enforce enterprise readiness documentation parity"
```

### Task 9: Final Verification and Documentation Consistency

**Files:**
- Verify all files changed in Tasks 1-8.

- [ ] **Step 1: Run focused enterprise tests**

Run:

```powershell
pytest backend/tests/test_enterprise_controls.py backend/tests/test_enterprise_readiness_docs.py backend/tests/test_sprint104_enterprise_readiness.py -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run the documentation lint directly**

Run:

```powershell
python scripts/lint_enterprise_readiness.py
```

Expected:

```text
Enterprise readiness documentation is aligned.
```

- [ ] **Step 3: Run broader backend regression tests**

Run:

```powershell
pytest backend/tests -q
```

Expected: PASS with only documented skips.

- [ ] **Step 4: Validate formatting and stale references**

Run:

```powershell
git diff --check
rg -n "US-073\\.\\.|COMPLIANCE-T.BD|docs/UKIP_ENTERPRISE_ROADMAP.md" docs/product backend/enterprise_readiness.py backend/enterprise_controls.py
```

Expected:

- `git diff --check` emits no errors.
- no abbreviated story range remains in operational documents;
- no active runtime control uses legacy compliance placeholder IDs;
- the historical roadmap appears only in explicit historical/classification context.

- [ ] **Step 5: Review the final diff**

Run:

```powershell
git status --short
git diff --stat
git diff -- docs/product/ENTERPRISE_CONTROL_REGISTER.md backend/enterprise_controls.py scripts/lint_enterprise_readiness.py
```

Expected: only planned files changed, with no unrelated edits.

- [ ] **Step 6: Commit final consistency fixes if needed**

If verification required corrections:

```powershell
git add <corrected-files>
git commit -m "docs: finalize enterprise readiness alignment"
```

If no corrections were required, do not create an empty commit.
