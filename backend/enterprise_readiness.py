"""Enterprise readiness and compliance gap baseline for commercial planning."""
from __future__ import annotations

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
REGISTER_UPDATED_AT = "2026-06-05"

ENTERPRISE_READINESS_GAPS = [
    {
        "id": "data_lifecycle_controls",
        "area": "privacy_governance",
        "priority": "P0",
        "status": "gap",
        "title": "Data retention, export, and deletion controls are not formalized",
        "current_state": (
            "The platform can import, mutate, and export data, but it lacks a "
            "policy-backed workflow for retention, subject deletion, and lifecycle evidence."
        ),
        "impact": (
            "Blocks GDPR-style conversations and creates ambiguity during customer legal review."
        ),
        "recommendation": (
            "Define lifecycle policy, create admin workflows for export and deletion requests, "
            "and document evidence retained for those operations."
        ),
        "related_work": ["COMPLIANCE-TBD-RETENTION", "COMPLIANCE-TBD-PRIVACY"],
    },
    {
        "id": "secrets_rotation",
        "area": "security_operations",
        "priority": "P0",
        "status": "partial",
        "title": "Secrets and credentials lack a documented rotation program",
        "current_state": (
            "Secrets are configurable and some sensitive values are encrypted at rest, "
            "but there is no documented rotation cadence, dual-key rollout, or audit workflow."
        ),
        "impact": (
            "Weakens enterprise security posture and slows incident response after credential exposure."
        ),
        "recommendation": (
            "Add rotation runbooks, ownership, staged secret rollover, and evidence that rotations occurred."
        ),
        "related_work": ["COMPLIANCE-TBD-SECRETS"],
    },
    {
        "id": "audit_evidence_pack",
        "area": "auditability",
        "priority": "P1",
        "status": "partial",
        "title": "Auditability exists, but not yet as an enterprise evidence pack",
        "current_state": (
            "Audit log, health, telemetry baseline, and ops checks exist, but there is no "
            "tamper-evident export, retention control, or tenant-scoped audit evidence package."
        ),
        "impact": (
            "Due diligence remains manual and expensive for customers who need traceable control evidence."
        ),
        "recommendation": (
            "Add exportable audit evidence, retention controls, and documented control ownership."
        ),
        "related_work": ["EPIC-015", "US-051", "US-053", "COMPLIANCE-TBD-AUDIT"],
    },
    {
        "id": "data_residency",
        "area": "deployment_governance",
        "priority": "P1",
        "status": "gap",
        "title": "Data residency controls are not defined",
        "current_state": (
            "UKIP has a PostgreSQL-first runtime path, but region pinning, residency commitments, "
            "and deployment boundary guidance are not yet defined."
        ),
        "impact": (
            "Limits commercial conversations with institutions that require regional hosting guarantees."
        ),
        "recommendation": (
            "Document supported deployment topologies and add region-specific hosting guidance before making residency claims."
        ),
        "related_work": ["COMPLIANCE-TBD-RESIDENCY"],
    },
    {
        "id": "privacy_legal_pack",
        "area": "legal_privacy",
        "priority": "P1",
        "status": "gap",
        "title": "Privacy and legal readiness artifacts are missing",
        "current_state": (
            "There is no standard DPA, subprocessor register, record of processing activity, "
            "or concise privacy control pack for customer review."
        ),
        "impact": (
            "Sales and procurement review stall even when the technical product fit is strong."
        ),
        "recommendation": (
            "Prepare a minimum privacy pack covering subprocessors, legal basis assumptions, and operational responsibilities."
        ),
        "related_work": ["COMPLIANCE-TBD-DPA", "COMPLIANCE-TBD-ROPA"],
    },
    {
        "id": "background_job_separation",
        "area": "operational_reliability",
        "priority": "P1",
        "status": "partial",
        "title": "Background jobs still share the app process lifecycle",
        "current_state": (
            "Schedulers, checks, and alerts exist, but scheduled imports and reports still run in-process."
        ),
        "impact": (
            "Raises reliability, recoverability, and separation-of-duties concerns for production operations."
        ),
        "recommendation": (
            "Advance the US-042 externalization path for queue-backed jobs and supervisor-managed workers."
        ),
        "related_work": ["US-042", "EPIC-009", "EPIC-015"],
    },
    {
        "id": "identity_lifecycle",
        "area": "identity_management",
        "priority": "P2",
        "status": "partial",
        "title": "Identity lifecycle is not enterprise-complete",
        "current_state": (
            "JWT, RBAC, API keys, and some SSO support exist, but SCIM, enterprise offboarding, "
            "and stronger session governance are incomplete."
        ),
        "impact": (
            "Creates manual admin work and weaker governance for larger customer environments."
        ),
        "recommendation": (
            "Prioritize identity lifecycle controls after tenant isolation and core privacy controls are in place."
        ),
        "related_work": ["EPIC-010", "EPIC-012", "COMPLIANCE-TBD-SCIM"],
    },
]


RESOLVED_GAPS = [
    {
        "id": "tenant_isolation",
        "area": "access_control",
        "priority": "P0",
        "status": "resolved",
        "title": "Hard tenant data isolation",
        "current_state": (
            "org_id is propagated and enforced across user-owned, collaboration, "
            "and agentic surfaces. Tenant-scoped queries are applied in routers, "
            "the GapAnalyzer, the agentic tool registry, ContextEngine, and ChromaDB "
            "retrieval. Isolation test suites pin the cross-tenant boundary."
        ),
        "impact": (
            "Closes the highest-risk data-segregation gap for enterprise accounts."
        ),
        "recommendation": (
            "Maintain the tenant_access helper pattern for any new tenant-scoped "
            "surface; run the post-deploy ChromaDB re-index so existing vectors "
            "gain org_id metadata."
        ),
        "related_work": ["EPIC-012", "US-043", "US-044", "US-045"],
        "resolved_at": "2026-06-05",
        "evidence": [
            "PR #30 (Wave 2-3 closure)",
            "PR #33 (GapAnalyzer scope)",
            "PR #35 (agentic tenant context)",
            "PR #36 (deploy runbook + re-index script)",
            "PR #37 (admin-gated re-index UI)",
            "docs/operating/EPIC012_TENANT_ISOLATION_DEPLOY_RUNBOOK.md",
        ],
    },
]


def _priority_counts(gaps: list[dict]) -> dict[str, int]:
    return {
        "P0": sum(1 for gap in gaps if gap["priority"] == "P0"),
        "P1": sum(1 for gap in gaps if gap["priority"] == "P1"),
        "P2": sum(1 for gap in gaps if gap["priority"] == "P2"),
    }


def _status_counts(gaps: list[dict]) -> dict[str, int]:
    return {
        "gap": sum(1 for gap in gaps if gap["status"] == "gap"),
        "partial": sum(1 for gap in gaps if gap["status"] == "partial"),
    }


def get_enterprise_readiness_report() -> dict:
    gaps = sorted(
        ENTERPRISE_READINESS_GAPS,
        key=lambda gap: (PRIORITY_ORDER[gap["priority"]], gap["title"]),
    )
    resolved = sorted(
        RESOLVED_GAPS,
        key=lambda gap: (PRIORITY_ORDER[gap["priority"]], gap["title"]),
    )
    return {
        "status": "baseline",
        "service": "ukip-backend",
        "focus_mvp": "research_intelligence",
        "updated_at": REGISTER_UPDATED_AT,
        "summary": {
            "total_gaps": len(gaps),
            "priority_counts": _priority_counts(gaps),
            "status_counts": _status_counts(gaps),
            "resolved_count": len(resolved),
        },
        "roadmap_hooks": [
            {
                "id": "COMPLIANCE-TBD-RETENTION",
                "label": "Data lifecycle: retention, export, and deletion controls",
                "why": "Top open P0; unblocks GDPR-style legal and procurement review.",
            },
            {
                "id": "COMPLIANCE-TBD-SECRETS",
                "label": "Secrets and credential rotation program",
                "why": "Open P0; required for enterprise security posture and incident response.",
            },
            {
                "id": "US-042",
                "label": "Background job externalization plan",
                "why": "Needed to harden scheduled work beyond in-process runtime.",
            },
            {
                "id": "COMPLIANCE-TBD-PRIVACY",
                "label": "Privacy and legal pack baseline (DPA, ROPA, subprocessors)",
                "why": "Needed before making enterprise privacy or procurement claims.",
            },
        ],
        "gaps": gaps,
        "resolved": resolved,
    }
