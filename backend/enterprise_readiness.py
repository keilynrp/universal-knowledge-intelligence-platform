"""Enterprise readiness and compliance gap baseline for commercial planning."""
from __future__ import annotations

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}
REGISTER_UPDATED_AT = "2026-06-11"

ENTERPRISE_READINESS_GAPS = [
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
        "status": "partial",
        "title": "Baseline privacy pack exists but is pending professional legal review",
        "current_state": (
            "A baseline privacy pack exists in docs/legal/ (DPA baseline, subprocessor register, "
            "ROPA, privacy controls overview, and a Mexico/LFPDPPP annex). It remains pending "
            "professional legal review before it can be signed or relied upon."
        ),
        "impact": (
            "Sales and procurement review stall even when the technical product fit is strong."
        ),
        "recommendation": (
            "Obtain external legal review of the docs/legal/ pack, then move this gap to resolved."
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
        "id": "secrets_rotation",
        "area": "security_operations",
        "priority": "P0",
        "status": "resolved",
        "title": "Secrets and credentials have a documented rotation program",
        "current_state": (
            "EPIC-017 delivered zero-downtime staged dual-key rotation for "
            "ENCRYPTION_KEY (MultiFernet + eager re-encrypt) and JWT_SECRET_KEY "
            "(multi-key verify), a secret_rotation_events evidence trail, a secrets "
            "ops health check, and a rotation runbook with ownership and cadence."
        ),
        "impact": (
            "Closes the last open P0 — strengthens enterprise security posture and "
            "speeds incident response after credential exposure."
        ),
        "recommendation": (
            "Follow the 90-day cadence in docs/operating/SECRETS_ROTATION_RUNBOOK.md; "
            "verify each rotation via /ops/checks and the secret_rotation_events table."
        ),
        "related_work": ["EPIC-017", "COMPLIANCE-TBD-SECRETS"],
        "resolved_at": "2026-06-05",
        "evidence": [
            "Slice 1 (MultiFernet core)",
            "Slice 2 (JWT multi-key verify)",
            "Slice 3 (evidence table + re-encrypt script)",
            "Slice 4 (ops check + runbook + register)",
            "Alembic migration e5f6a7b8c0d1 (secret_rotation_events)",
        ],
    },
    {
        "id": "data_lifecycle_controls",
        "area": "privacy_governance",
        "priority": "P0",
        "status": "resolved",
        "title": "Data retention, export, and deletion controls are formalized",
        "current_state": (
            "EPIC-016 delivered a policy-backed data lifecycle: lifecycle audit "
            "foundation, subject/tenant export (DSAR), cascade deletion (right to "
            "erasure), and retention policy management with a scoped purge that "
            "deletes only expired rows. Operations are super_admin-gated under "
            "/admin/data-lifecycle/* and retain audit evidence."
        ),
        "impact": (
            "Unblocks GDPR-style legal and procurement review and removes ambiguity "
            "during customer legal due diligence."
        ),
        "recommendation": (
            "Keep the RetentionPurger manual-only until env-flag gating "
            "(RETENTION_PURGE_ENABLED) and partial-deletion coverage are added before "
            "wiring the daily loop into the app lifespan."
        ),
        "related_work": [
            "EPIC-016",
            "US-070",
            "US-071",
            "US-072",
            "US-073",
            "COMPLIANCE-TBD-RETENTION",
            "COMPLIANCE-TBD-PRIVACY",
        ],
        "resolved_at": "2026-06-05",
        "evidence": [
            "PR #40 (US-070 lifecycle audit foundation + policy)",
            "PR #41 (US-071 subject/tenant export / DSAR)",
            "PR #42 (US-072 cascade deletion / right to erasure)",
            "PR #43 (US-073 retention policy management + purge)",
            "PR #44 (scoped purge fix: deletes only expired rows, not whole org)",
            "Alembic migration d4e5f6a7b8c0 (retention_policies table)",
        ],
    },
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
