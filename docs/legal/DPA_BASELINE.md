# Data Processing Agreement — Baseline Template (UKIP)

> **DISCLAIMER / AVISO:** Base template prepared by the UKIP engineering team.
> NOT legal advice. Requires review by qualified counsel before being signed
> or relied upon in any contract or compliance representation.

This template defines baseline data-processing terms between a customer of the
Universal Knowledge Intelligence Platform (UKIP) and the UKIP operator. It is a
negotiation starting point. Sections marked `[NEGOTIATED]` or `[OPERATOR TO
FILL]` are commercial or operator-specific and must be completed before
signature.

## 1. Parties and roles

| Role | Party |
|------|-------|
| Data controller (Spanish: *responsable*) | The Customer — the research institution that determines the purposes and means of processing |
| Data processor (Spanish: *encargado*) | The UKIP operator — `[OPERATOR TO FILL: legal entity name and address]` |

The Customer instructs the UKIP operator to process personal data on its
behalf, solely as described in this agreement.

## 2. Subject matter and duration

- **Subject matter:** Hosting and processing of research-intelligence data
  (bibliographic and scientometric records, platform user accounts, and
  associated operational records) on the UKIP platform.
- **Duration:** The term of the underlying service agreement, plus the
  deletion/return period in Section 9.

## 3. Nature and purpose of processing

UKIP ingests, harmonizes, disambiguates, enriches, and analyzes research data
on behalf of the Customer. Processing operations include: storage, structuring,
deduplication and disambiguation, authority resolution against public
bibliographic registries, analytics/aggregation, retrieval-augmented search,
export, and deletion.

## 4. Categories of data and data subjects

| Category | Description | Data subjects |
|----------|-------------|---------------|
| Platform user accounts | Username, email, role, password hash, login/lockout metadata | Customer staff who use the platform |
| Research entities | Author names, affiliations, publications, concepts, public identifiers (ORCID, VIAF, Wikidata, OpenAlex, DBpedia IDs) | Researchers referenced in the Customer's datasets — predominantly professional, public-sphere data |
| Operational records | Audit log entries, data-lifecycle events, secret-rotation evidence | Customer staff (actor attribution) |
| Third-party credentials | Connection credentials the Customer configures for its own data stores / AI integrations | N/A (credentials, not personal data; encrypted at rest) |

UKIP is not designed for, and the Customer agrees not to submit, special
categories of personal data (health, biometric, etc.) or data of minors.

## 5. Documented instructions

The processor shall process personal data only on documented instructions from
the controller, including with regard to transfers, unless required to do so by
law. The platform's configuration surface (org settings, retention policies,
AI-integration toggles, store connections) constitutes part of the controller's
documented instructions. The processor shall inform the controller if, in its
opinion, an instruction infringes applicable data-protection law.

## 6. Confidentiality

The processor shall ensure that persons authorized to process the personal data
have committed themselves to confidentiality or are under an appropriate
statutory obligation of confidentiality. Access to production systems is
restricted to the operator's authorized personnel.

## 7. Annex A — Technical and organizational measures

All measures below are implemented and verifiable in the UKIP codebase and
operating documentation, except where explicitly marked otherwise.

| Measure | Implementation | Evidence |
|---------|----------------|----------|
| Tenant isolation | `org_id` scoping enforced across API routers, gap analysis, agentic registry, and ChromaDB vector retrieval; legacy-data sentinel for pre-migration rows | EPIC-012, PRs #30/#33/#35/#36/#37; regression suites incl. `backend/tests/test_issue31_gap_analyzer_org_scope.py`, `backend/tests/test_issue32_agentic_tenant_context.py` |
| Encryption at rest (credentials) | Third-party store and AI-integration credentials encrypted with Fernet (AES-128-CBC + HMAC-SHA256), wrapped in MultiFernet for zero-downtime key rotation | `backend/encryption.py` |
| Encryption in transit | TLS termination at Cloudflare (edge) and Traefik (origin) | Deployment configuration (Dokploy) |
| Authentication | JWT-based authentication; account lockout after 5 failed attempts for 15 minutes | `backend/auth.py` |
| Authorization | Role-based access control: super_admin / admin / editor / viewer, enforced per endpoint | `backend/auth.py` (`require_role`), router dependencies |
| Audit logging | Audit log of security-relevant actions; data-lifecycle operations record `DataLifecycleEvent` audit evidence | `GET /admin/data-lifecycle/events`; audit log module |
| Data subject rights tooling | DSAR export (portable JSON bundle of all org-scoped data) and cascade deletion (DB + vector store), super_admin/admin-gated, with audit evidence | EPIC-016, PRs #40–#44; `POST /admin/data-lifecycle/export`, `POST /admin/data-lifecycle/delete` |
| Retention | Configurable per-org retention policies with purge mechanism (purge execution is currently operator-triggered, not scheduled) | EPIC-016 Slice 4; `docs/operating/DATA_LIFECYCLE_POLICY.md` |
| Secrets rotation | Staged dual-key zero-downtime rotation for encryption and JWT keys; 90-day cadence; rotation evidence table; first production rotation executed 2026-06-06 | EPIC-017, PRs #48–#51; `docs/operating/SECRETS_ROTATION_RUNBOOK.md`; `secret_rotation_events` table; `GET /ops/secrets` |
| Operational health checks | Automated checks including secrets posture (insecure defaults, stale keys) exposed to operators | `GET /ops/checks` |
| Backups & recovery | Program defined with RTO 4h / RPO 24h (daily encrypted backups to S3-compatible storage + CI freshness monitor + restore-drill procedure). **Status: program defined; first operational configuration and restore drill pending.** | EPIC-018; `docs/operating/BACKUP_RESTORE_RUNBOOK.md` (pending merge from `ops/epic018-backup-restore`) |
| Supply-chain / CI security gates | CodeQL SAST, gitleaks secret scanning, pip-audit, npm-audit, Trivy image scanning, SBOM generation. **Status: implemented in CI; operator enforcement steps pending (EPIC-019, PR #63 pending merge).** | `.github/workflows/` (EPIC-019 commits) |
| Data minimization — optional telemetry/LLM egress disabled by default | Sentry error telemetry gated by `SENTRY_ENABLED` (default false); LLM providers (OpenAI) engaged only via customer-activated AI integration (opt-in) | `backend/telemetry.py`; see Section 8 and [SUBPROCESSOR_REGISTER.md](SUBPROCESSOR_REGISTER.md) |

**Known open measures (disclosed, not represented as in place):** formal
incident response plan (ER-IR-001), external penetration test (ER-ASSURE-001),
contractual data-residency commitments (ER-DEP-001), first backup operational
configuration and restore drill (EPIC-018), and CI security-gate operator
enforcement steps (EPIC-019). See
[PRIVACY_CONTROLS_OVERVIEW.md](PRIVACY_CONTROLS_OVERVIEW.md) for the full
open-item register.

## 8. Sub-processors

The controller grants general authorization for the sub-processors listed in
[SUBPROCESSOR_REGISTER.md](SUBPROCESSOR_REGISTER.md). The processor shall:

- maintain that register and keep it current;
- give the controller at least `[NEGOTIATED: e.g. 30 days]` written notice of
  any intended addition or replacement of a sub-processor, giving the
  controller the opportunity to object;
- impose data-protection obligations on each sub-processor no less protective
  than those in this agreement, to the extent applicable to the service the
  sub-processor provides.

Optional sub-processors (error telemetry, LLM features) are disabled by
default and engaged only when the controller enables the corresponding feature.

## 9. Deletion and return on termination

On termination of the service agreement, at the controller's choice, the
processor shall:

- **return** the controller's data via the tenant export mechanism
  (`POST /admin/data-lifecycle/export` — portable JSON bundle of all
  org-scoped data), and/or
- **delete** the controller's data via the tenant cascade-deletion mechanism
  (`POST /admin/data-lifecycle/delete` — erases all org-scoped data in the
  relational database and the vector store, recording audit evidence),

within `[NEGOTIATED: e.g. 30 days]` of termination, except where retention is
required by law. Backup copies are deleted in line with the backup retention
cycle described in the backup runbook.

## 10. Assistance with data subject rights

Taking into account the nature of the processing, the processor shall assist
the controller in fulfilling its obligation to respond to data subject
requests, using the implemented tooling:

- **Access / portability:** DSAR export endpoint (org- and subject-scoped
  export with audit evidence) — EPIC-016 Slice 2.
- **Erasure:** cascade deletion endpoint (DB + vector store) — EPIC-016
  Slice 3.
- **Rectification:** entity edit endpoints available to the controller's
  authorized users.

The controller remains the point of contact for data subjects; the processor
acts on the controller's instructions.

## 11. Personal data breach notification

The processor shall notify the controller without undue delay after becoming
aware of a personal data breach affecting the controller's data, and in any
case within `[NEGOTIATED — pending ER-IR-001 incident response plan]`.

> **Pending control (disclosed):** A formal incident response plan is an open
> item in the operator's gap register (ER-IR-001). Until it lands, the
> notification timeframe above cannot be committed with operational backing
> and must be negotiated with that limitation in view. Notifications will
> include the nature of the breach, categories and approximate number of data
> subjects and records concerned, likely consequences, and measures taken or
> proposed.

## 12. Audit and information rights

The processor shall make available to the controller information reasonably
necessary to demonstrate compliance with this agreement, including:

- the controls overview and evidence pointers in
  [PRIVACY_CONTROLS_OVERVIEW.md](PRIVACY_CONTROLS_OVERVIEW.md);
- data-lifecycle audit events for the controller's tenant
  (`GET /admin/data-lifecycle/events`);
- secrets-rotation evidence (`GET /ops/secrets`, operator-mediated).

The controller may conduct audits (including inspections) at
`[NEGOTIATED: frequency, notice period, cost allocation]`. No external
penetration test report is currently available (ER-ASSURE-001 open).

## 13. Liability and jurisdiction

- Liability allocation, caps, and indemnities: `[NEGOTIATED]`.
- Governing law and jurisdiction: `[NEGOTIATED]`.

These are commercial terms outside the scope of this engineering baseline.

## Signatures

| | Controller (responsable) | Processor (encargado) |
|---|---|---|
| Entity | `[CUSTOMER]` | `[OPERATOR TO FILL]` |
| Name / title | | |
| Date | | |
