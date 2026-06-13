# Record of Processing Activities (ROPA) — UKIP

> **DISCLAIMER / AVISO:** Base template prepared by the UKIP engineering team.
> NOT legal advice. Requires review by qualified counsel before being signed
> or relied upon in any contract or compliance representation.

This record describes the processing activities performed by the UKIP operator
as data processor (*encargado*) on behalf of customers acting as data
controllers (*responsables*). One section per activity.

---

## Activity 1 — Platform user account management

| Field | Description |
|-------|-------------|
| Purpose | Authenticate and authorize the customer's staff on the platform |
| Data categories | Username, email, role, bcrypt password hash, account status, failed-attempt counter, lockout timestamp |
| Data subjects | Customer staff (platform users) |
| Retention | For the life of the account; accounts are removed via user management (super_admin) or tenant deletion (EPIC-016) |
| Security measures | JWT auth, RBAC (super_admin/admin/editor/viewer), account lockout (5 attempts / 15 min), TLS in transit, audit logging |
| Recipients / transfers | Hosting provider (see [SUBPROCESSOR_REGISTER.md](SUBPROCESSOR_REGISTER.md)); no other recipients |

## Activity 2 — Research/bibliographic entity processing

| Field | Description |
|-------|-------------|
| Purpose | Ingest, harmonize, disambiguate, enrich, and analyze the customer's research-intelligence data (authors, affiliations, publications, concepts) |
| Data categories | Author names, affiliations, publication metadata, concepts, public identifiers (ORCID, VIAF, Wikidata, OpenAlex, DBpedia IDs) — predominantly professional, public-sphere data |
| Data subjects | Researchers referenced in the customer's datasets |
| Retention | Configurable per-organization retention policies (EPIC-016 Slice 4); data removable on demand via tenant/subject deletion |
| Security measures | Tenant isolation by `org_id` across DB and ChromaDB retrieval (EPIC-012), RBAC, TLS, audit evidence on lifecycle operations |
| Recipients / transfers | Hosting provider. During **authority resolution**, lookup queries (entity names/identifiers) are sent to PUBLIC bibliographic sources: Wikidata, VIAF, ORCID, OpenAlex, DBpedia. If the customer enables an AI integration, selected text may be sent to the configured LLM provider (default OFF; see register) |

## Activity 3 — Operational logging and audit

| Field | Description |
|-------|-------------|
| Purpose | Security accountability, troubleshooting, and compliance evidence |
| Data categories | Audit log entries (actor, action, timestamp), data-lifecycle events (`DataLifecycleEvent`), secret-rotation evidence (`secret_rotation_events` — no secret material, metadata only), application logs |
| Data subjects | Customer staff (as acting users) |
| Retention | Operational logs per hosting configuration; lifecycle and rotation evidence retained as compliance records |
| Security measures | Admin-gated access (`GET /admin/data-lifecycle/events` admin-only; `GET /ops/secrets` admin+, read-only, no secret values), RBAC, TLS |
| Recipients / transfers | Hosting provider. Sentry error telemetry only if explicitly enabled (`SENTRY_ENABLED`, default OFF) |

## Activity 4 — Encrypted third-party credential storage

| Field | Description |
|-------|-------------|
| Purpose | Store connection credentials the customer configures for its own data stores and AI integrations |
| Data categories | API keys, connection strings, custom headers (credentials — not personal data, but customer-confidential) |
| Data subjects | N/A (credential material) |
| Retention | Until the customer deletes the store/integration or the tenant is deleted |
| Security measures | Encrypted at rest with Fernet/MultiFernet (`backend/encryption.py`); decrypted only at point of use; key rotation program with 90-day cadence and evidence trail (EPIC-017); admin-gated CRUD |
| Recipients / transfers | Hosting provider only |

## Activity 5 — Backups

| Field | Description |
|-------|-------------|
| Purpose | Disaster recovery (target RTO 4h / RPO 24h) |
| Data categories | Encrypted database backups covering all of the above |
| Data subjects | Same as activities 1–4 |
| Retention | Per backup retention cycle in `docs/operating/BACKUP_RESTORE_RUNBOOK.md` (EPIC-018) |
| Security measures | Repository-side backup evidence, freshness monitoring, restore validation, and the operator runbook target RPO 24h and RTO 4h. **Repository controls and runbook implemented; provider configuration, two successful backup cycles, and the first isolated restore drill remain pending.** |
| Recipients / transfers | Backup storage provider `[OPERATOR TO FILL: S3 backup provider]` in `[OPERATOR TO FILL: backup storage region]` (see register) |

---

## Cross-cutting notes

- All activities are scoped per tenant (`org_id`) with isolation regression
  tests (EPIC-012, PRs #30/#33/#35/#36/#37).
- Data subject rights are serviced through the EPIC-016 endpoints
  (`/admin/data-lifecycle/export`, `/admin/data-lifecycle/delete`) with audit
  evidence; see [DPA_BASELINE.md](DPA_BASELINE.md) Section 10.
- Data residency depends on the hosting provider's region and is not yet a
  contractual commitment (open item ER-DEP-001; see
  [PRIVACY_CONTROLS_OVERVIEW.md](PRIVACY_CONTROLS_OVERVIEW.md)).
