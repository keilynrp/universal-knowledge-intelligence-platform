# UKIP Enterprise Control Register

Updated: 2026-06-12

This register is stricter than `backend/enterprise_readiness.py`. That endpoint
tracks known commercial gaps; this register tracks whether controls are
specified, implemented, verified, operated, and auditable.

## Status rules

- Status is the lowest maturity state supported by current evidence.
- Missing evidence lowers status even when code exists.
- Risk acceptance requires an accountable owner, expiry date, and compensating
  control. It does not convert a failed control into a passed control.
- P0 and P1 controls may not be closed by documentation-only PRs.

## Register

| ID | Control objective | Priority | Current maturity | Target | Accountable role | Evidence gap |
| --- | --- | --- | --- | --- | --- | --- |
| ER-CTRL-001 | Strategic controls have governed lifecycle and evidence | P0 | specified | auditable | Product/security owner | Operational use of register and release evidence index |
| ER-OPS-001 | Critical jobs execute outside the web process with durable state | P1 | specified | operated | Platform owner | Queue runtime, recovery tests, observation window |
| ER-BCP-001 | PostgreSQL and required state can be restored within measured objectives | P0 | specified | auditable | Operations owner | Provider configuration, two successful backup cycles, first isolated restore drill, and approved evidence |
| ER-SDLC-001 | Releases pass enforceable security and supply-chain gates | P0 | implemented | operated | Security/platform owner | Operator: enable push protection + required checks; first month of gate operation |
| ER-AUD-001 | Tenant-scoped control evidence is integrity-verifiable and exportable | P1 | identified | auditable | Security/compliance owner | Evidence schema, signed export, retention, verification tool |
| ER-PRIV-001 | Customer privacy review has a maintained legal/operational pack | P1 | specified | auditable | Privacy/legal owner | External legal review of the docs/legal pack |
| ER-IAM-001 | Joiner/mover/leaver lifecycle prevents orphaned access | P1 | identified | operated | Security/platform owner | MFA, SCIM or governed alternative, session/API-key revocation drills |
| ER-DEP-001 | Supported deployment and residency boundaries are explicit and testable | P1 | identified | auditable | Architecture/operations owner | Topology matrix, region policy, data-flow inventory, exit procedure |
| ER-IR-001 | Security incidents are detected, classified, contained, and evidenced | P0 | identified | operated | Security/operations owner | Incident plan, severity model, tabletop exercise, notification workflow |
| ER-PERF-001 | Capacity and degradation behavior are known for supported workloads | P1 | identified | operated | Platform owner | Load model, performance tests, saturation alerts, capacity envelope |
| ER-ASSURE-001 | Independent assessment validates security posture before broad GA | P0 | identified | auditable | Executive/security owner | External pentest and closure report |

## Control detail and next gates

| ID | Delivery | Implementation owner | Operational owner | Next gate | Observation / evidence requirement |
| --- | --- | --- | --- | --- | --- |
| ER-CTRL-001 | EPIC-018 governance | Product owner | Security owner | Operate the register on a release candidate | Versioned release evidence index and owner attestation |
| ER-OPS-001 | US-042 | Platform owner | Operations owner | Implement durable queue runtime and recovery tests | 14-day window with job SLO, retry, replay, and saturation evidence |
| ER-BCP-001 | US-073 | Platform owner | Operations owner | Configure the provider, observe two successful backup cycles, and complete the first isolated restore drill. | Retain approved backup and drill evidence for 12 months |
| ER-SDLC-001 | US-074 | Platform owner | Security owner | Enable required checks and push protection | 30 days of blocking gate operation and retained SBOM/security artifacts |
| ER-AUD-001 | US-075 | Backend owner | Security/compliance owner | Approve evidence schema, integrity, redaction, and retention | Independently verifiable tenant-scoped evidence export |
| ER-PRIV-001 | US-076 | Privacy owner | Legal/privacy owner | Complete external legal review | Approved versioned pack with annual review ownership |
| ER-IAM-001 | US-077 | Platform owner | Security owner | Specify MFA, provisioning, revocation, and break-glass | Joiner/mover/leaver and emergency-access drills |
| ER-DEP-001 | US-078 | Architecture owner | Operations owner | Approve topology matrix and region policy | Versioned data-flow, residency, subprocessor, and exit evidence |
| ER-IR-001 | US-079 | Security owner | Security/operations owner | Approve severity and notification workflow | Tabletop exercise, timeline, decisions, and corrective actions |
| ER-PERF-001 | US-080 | Platform owner | Operations owner | Approve workload profiles and performance objectives | Repeatable load report, saturation alerts, and supported envelope |
| ER-ASSURE-001 | US-081 | Security owner | Executive owner | Approve pentest and pilot-exit scope | Independent report, remediation/retest, pilot record, executive decision |

ER-BCP-001 status: **Repository controls and runbook implemented; provider
configuration, two successful backup cycles, and the first isolated restore
drill remain pending.** Its maturity remains `specified` until Dokploy/S3 is
configured. It must not advance to `verified` until the backup cycles and drill
evidence are reviewed.

Control maturity remains the lowest state supported by evidence.

## Existing controls requiring continued evidence

| Existing capability | Current assessment | Required continuation |
| --- | --- | --- |
| Tenant isolation | implemented and tested | Add release-level isolation evidence and regression gate |
| Data lifecycle controls | implemented and tested | Exercise DSAR, deletion, and retention drills periodically |
| Secret rotation | implemented and documented | Execute cadence and preserve rotation evidence |
| Health, telemetry, and ops checks | implemented | Define SLOs, alert ownership, and incident linkage |
| JWT/RBAC/API keys/SSO | implemented, enterprise lifecycle partial | Complete ER-IAM-001 |

## Review cadence

- Review on every release candidate.
- Review after a severity-one or severity-two incident.
- Review after material topology, identity, data-flow, or provider changes.
- Full executive review at least quarterly during enterprise-readiness delivery.

