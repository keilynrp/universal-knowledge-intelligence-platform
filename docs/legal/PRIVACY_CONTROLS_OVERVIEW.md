# Privacy & Security Controls Overview (UKIP)

> **DISCLAIMER / AVISO:** Base template prepared by the UKIP engineering team.
> NOT legal advice. Requires review by qualified counsel before being signed
> or relied upon in any contract or compliance representation.

One-page summary for procurement and security questionnaires. Every row points
to verifiable evidence (pull requests, test suites, runbooks, or live
endpoints). Items not yet in place are listed in the Open Items section — we
prefer an honest register over an impressive one.

## Implemented controls

| Control | Implementation | Evidence pointer |
|---------|----------------|------------------|
| Tenant isolation | `org_id` enforced across API routers, gap analysis, agentic registry, and ChromaDB vector retrieval | EPIC-012; PRs #30, #33, #35, #36, #37; regression suites incl. `backend/tests/test_issue31_gap_analyzer_org_scope.py`, `backend/tests/test_issue32_agentic_tenant_context.py` |
| Credential encryption at rest | Fernet (AES-128-CBC + HMAC-SHA256) wrapped in MultiFernet for zero-downtime key rotation | `backend/encryption.py` |
| Encryption in transit | TLS via Cloudflare (edge) + Traefik (origin) | Dokploy deployment configuration |
| Authentication & authorization | JWT + RBAC (super_admin/admin/editor/viewer); account lockout 5 attempts / 15 min | `backend/auth.py`; per-endpoint `require_role` dependencies |
| Audit logging | Audit log + `DataLifecycleEvent` evidence on export/delete operations | `GET /admin/data-lifecycle/events` (admin-only) |
| DSAR export (access/portability) | Org-scoped portable JSON export with audit evidence | EPIC-016 Slice 2 (PR #41); `POST /admin/data-lifecycle/export` |
| Right to erasure | Cascade deletion across DB + ChromaDB with confirmation echo + audit evidence | EPIC-016 Slice 3 (PR #42, hardened by #44); `POST /admin/data-lifecycle/delete` |
| Retention policies | Configurable per-org retention + purge mechanism (operator-triggered) | EPIC-016 Slice 4 (PR #43); `docs/operating/DATA_LIFECYCLE_POLICY.md` |
| Secrets rotation program | Staged dual-key zero-downtime rotation; 90-day cadence; evidence table; first production rotation executed 2026-06-06 | EPIC-017 (PRs #48–#51); `docs/operating/SECRETS_ROTATION_RUNBOOK.md`; `GET /ops/secrets`; `secret_rotation_events` table |
| Operational health & secrets posture checks | Automated checks flag insecure defaults, missing encryption key, stale (>90d) or lingering retiring keys | `GET /ops/checks`; `backend/ops_checks.py` |
| Backup & restore program | RPO 24h / RTO 4h repository controls, freshness monitor, restore validator, and operator runbook. **Repository controls and runbook implemented; provider configuration, two successful backup cycles, and the first isolated restore drill remain pending.** | US-073 / ER-BCP-001; `docs/operating/BACKUP_RESTORE_RUNBOOK.md`; backup assurance tests |
| CI security gates | CodeQL SAST, gitleaks, pip-audit, npm-audit, Trivy image scan, SBOM. **Implemented; operator enforcement steps pending** | EPIC-019; `.github/workflows/` |
| Optional telemetry / LLM egress off by default | Sentry gated by `SENTRY_ENABLED` (default false); LLM providers engaged only via customer-activated AI integration | `backend/telemetry.py`; [SUBPROCESSOR_REGISTER.md](SUBPROCESSOR_REGISTER.md) |

## Open items (honesty section)

| Open item | Tracking ID | Status |
|-----------|-------------|--------|
| Formal incident response plan (incl. breach-notification SLA backing) | ER-IR-001 | Open — DPA breach clause carries a placeholder timeframe until this lands |
| External penetration test | ER-ASSURE-001 | Open — no third-party assessment report available yet |
| Data residency commitments | ER-DEP-001 | Open — residency follows hosting region; no contractual commitment defined |
| Backup provider configuration and evidence cycles | US-073 / ER-BCP-001 | Pending — configure the provider, observe two successful backup cycles, and complete the first isolated restore drill |
| Professional legal review of this pack | EPIC-020 | Pending — gap register `privacy_legal_pack` = partial |

## Questions

Security and privacy questions: `[OPERATOR TO FILL: security contact email]`.
