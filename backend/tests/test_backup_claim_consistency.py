from pathlib import Path
import re
import subprocess

from backend.enterprise_controls import ENTERPRISE_CONTROLS


ROOT = Path(__file__).resolve().parents[2]
LEGAL_DOCS = (
    "docs/legal/ROPA.md",
    "docs/legal/PRIVACY_CONTROLS_OVERVIEW.md",
    "docs/legal/DPA_BASELINE.md",
    "docs/legal/SUBPROCESSOR_REGISTER.md",
)
CLAIM_DOCS = LEGAL_DOCS + (
    "docs/product/ENTERPRISE_CONTROL_REGISTER.md",
    "docs/product/TRACEABILITY_MATRIX.md",
)
HONEST_STATUS = (
    "Repository controls and runbook implemented; provider configuration, two "
    "successful backup cycles, and the first isolated restore drill remain pending."
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def _bcp_control():
    return next(
        control
        for control in ENTERPRISE_CONTROLS
        if control.control_id == "ER-BCP-001"
    )


def test_backup_claims_use_the_honest_operational_status():
    for path in CLAIM_DOCS:
        content = _read(path)
        assert HONEST_STATUS in _normalize_whitespace(content), path
        assert "pending merge" not in content.lower(), path
        assert "runbook approved" not in content.lower(), path


def test_no_restore_drill_is_claimed_as_passed_without_committed_evidence():
    evidence_root = ROOT / "docs/operating/evidence/ER-BCP-001"
    committed_evidence = ()
    if evidence_root.exists():
        tracked = subprocess.run(
            [
                "git",
                "ls-tree",
                "-r",
                "--name-only",
                "HEAD",
                "--",
                str(evidence_root.relative_to(ROOT)),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        committed_evidence = tuple(path for path in tracked if path)
    passed_claim = re.compile(
        r"(first restore drill (?:completed|passed)|restore drill (?:completed|passed|successful))",
        re.IGNORECASE,
    )
    claims = [
        path
        for path in CLAIM_DOCS
        if passed_claim.search(_read(path))
    ]
    assert not claims or committed_evidence, claims
    if claims:
        for claim_path in claims:
            claim = _read(claim_path)
            assert any(Path(evidence).name in claim for evidence in committed_evidence)


def test_legal_backup_claims_use_rpo_24h_and_rto_4h():
    for path in LEGAL_DOCS:
        content = _read(path)
        assert re.search(r"RPO(?: target)?:? 24h", content, re.IGNORECASE), path
        assert re.search(r"RTO(?: target)?:? 4h", content, re.IGNORECASE), path
        assert not re.search(r"RPO(?: target)?:? (?!24h)\d+h", content, re.IGNORECASE), path
        assert not re.search(r"RTO(?: target)?:? (?!4h)\d+h", content, re.IGNORECASE), path


def test_er_bcp_001_remains_specified_until_provider_configuration():
    control = _bcp_control()
    assert control.current_maturity == "specified"
    assert control.current_maturity != "verified"

    register = _read("docs/product/ENTERPRISE_CONTROL_REGISTER.md")
    traceability = _read("docs/product/TRACEABILITY_MATRIX.md")
    assert re.search(r"\| ER-BCP-001 \|[^\n]*\| specified \|", register)
    assert re.search(r"\| Recovery medido \|[^\n]*\| specified \|", traceability)


def test_next_gate_requires_two_backup_cycles_and_one_isolated_restore_drill():
    expected_gate = (
        "Configure the provider, observe two successful backup cycles, and "
        "complete the first isolated restore drill."
    )
    assert _bcp_control().next_gate == expected_gate
    assert expected_gate in _read("docs/product/ENTERPRISE_CONTROL_REGISTER.md")


def test_subprocessor_register_keeps_provider_and_region_placeholders():
    register = _read("docs/legal/SUBPROCESSOR_REGISTER.md")
    assert "[OPERATOR TO FILL: S3 backup provider]" in register
    assert "[OPERATOR TO FILL: backup storage region]" in register
