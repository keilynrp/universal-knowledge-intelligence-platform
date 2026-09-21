"""Machine-readable companion to the enterprise control register."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Priority = Literal["P0", "P1", "P2"]
Maturity = Literal["identified", "specified", "implemented", "verified", "operated", "auditable"]

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


ENTERPRISE_CONTROLS = (
    EnterpriseControl(
        "ER-CTRL-001",
        "Governed control lifecycle",
        "Keep control status, ownership, evidence, and claims governed.",
        "P0",
        "specified",
        "auditable",
        "Product/security owner",
        (),
        "Operate the register on a release candidate and publish a versioned evidence index.",
        (
            (
                "Cycle 1 release evidence index published for RC-2026-08-26-01 "
                "(main@8139ee1179ea0505ca2f5b5720c6886478d79d9f); see "
                "docs/product/evidence/RC-2026-08-26-01.md. Owner attestation pending; "
                "reproducibility across a second RC not yet demonstrated."
            ),
        ),
    ),
    EnterpriseControl("ER-OPS-001", "Durable background jobs", "Run critical jobs outside the web lifecycle with durable tenant-scoped state.", "P1", "specified", "operated", "Platform owner", ("US-042",), "Implement the queue-backed runtime and complete its recovery test and observation window."),
    EnterpriseControl(
        "ER-BCP-001",
        "Backup, restore, and disaster recovery",
        "Restore PostgreSQL and required state within approved and measured objectives.",
        "P0",
        "specified",
        "auditable",
        "Operations owner",
        ("US-073",),
        "Decide how tenant isolation is demonstrated, and run an isolated restore drill that passes.",
        (
            "Provider configured and two scheduled backup cycles evidenced; the first isolated restore drill (2026-09-21) restored the backup within RTO but failed two required checks (RPO of the chosen recovery point, tenant isolation) and is recorded as failed; the owner approved the readiness dossier on 2026-09-21.",
        ),
    ),
    EnterpriseControl("ER-SDLC-001", "Secure software supply chain", "Enforce release security, dependency, image, and provenance gates.", "P0", "implemented", "operated", "Security/platform owner", ("US-074",), "Enable required repository checks and preserve 30 days of gate operation evidence.", ("CodeQL, Gitleaks, dependency audits, Trivy, and SBOM workflows exist.",)),
    EnterpriseControl("ER-AUD-001", "Audit evidence pack", "Export tenant-scoped, integrity-verifiable control evidence.", "P1", "identified", "auditable", "Security/compliance owner", ("US-075",), "Specify the evidence schema, signing model, retention, and verification command."),
    EnterpriseControl("ER-PRIV-001", "Privacy and legal assurance", "Maintain a professionally reviewed privacy and subprocessor assurance pack.", "P1", "specified", "auditable", "Privacy/legal owner", ("US-076",), "Complete external legal review and record approved versions and owners.", ("Baseline DPA, ROPA, subprocessor register, privacy overview, and Mexico annex exist.",)),
    EnterpriseControl("ER-IAM-001", "Enterprise identity lifecycle", "Prevent orphaned access across joiner, mover, leaver, session, and API-key lifecycles.", "P1", "identified", "operated", "Security/platform owner", ("US-077",), "Specify MFA, provisioning, revocation, break-glass, and offboarding drill behavior."),
    EnterpriseControl("ER-DEP-001", "Deployment and residency governance", "Make supported topology, regional boundaries, data flows, and exit behavior explicit.", "P1", "identified", "auditable", "Architecture/operations owner", ("US-078",), "Approve the topology matrix, region policy, data-flow inventory, and exit procedure."),
    EnterpriseControl("ER-IR-001", "Incident response", "Detect, classify, contain, notify, and evidence security incidents.", "P0", "identified", "operated", "Security/operations owner", ("US-079",), "Approve the severity model and run the first tabletop exercise."),
    EnterpriseControl("ER-PERF-001", "Capacity and degradation envelope", "Know supported workloads, saturation points, and graceful degradation behavior.", "P1", "identified", "operated", "Platform owner", ("US-080",), "Define workload profiles, performance objectives, load scenarios, and saturation alerts."),
    EnterpriseControl("ER-ASSURE-001", "Independent assurance and pilot exit", "Require independent security assessment and a governed enterprise pilot exit decision.", "P0", "identified", "auditable", "Executive/security owner", ("US-081",), "Define pentest scope, remediation thresholds, pilot observation window, and exit authority."),
)


def build_enterprise_readiness_report() -> dict:
    controls = sorted(
        (control.to_dict() for control in ENTERPRISE_CONTROLS),
        key=lambda item: (PRIORITY_ORDER[item["priority"]], item["control_id"]),
    )
    return {
        "status": "enterprise_readiness_program",
        "service": "ukip-backend",
        "target_claim": "regulated_institutional_enterprise_ready",
        "updated_at": REGISTER_UPDATED_AT,
        "summary": {
            "total_controls": len(controls),
            "priority_counts": {priority: sum(item["priority"] == priority for item in controls) for priority in PRIORITY_ORDER},
            "maturity_counts": {maturity: sum(item["current_maturity"] == maturity for item in controls) for maturity in CONTROL_MATURITY_ORDER},
        },
        "controls": controls,
        "claim_disclaimer": "This report does not assert certification or unqualified enterprise readiness.",
    }
