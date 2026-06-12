# UKIP Enterprise Readiness Program

Updated: 2026-06-12

## 1. Purpose

This program turns UKIP's enterprise-readiness gaps into governed, incremental
delivery lifecycles. It exists to prepare UKIP for serious technical, security,
legal, and procurement review by regulated institutional customers and
demanding procurement teams.

Documentation is not evidence that a control works. A PRD, spec, ADR, test, or
runbook can advance a control, but none of them alone makes UKIP
enterprise-ready.

## 2. Enterprise-ready target

UKIP may use the unqualified claim `enterprise-ready` only when:

- no P0 or P1 control is below `operated`;
- every customer-relevant P0 and P1 control is `auditable`;
- recovery objectives have been measured through restore and failure drills;
- an independent penetration test has no unresolved critical or high findings;
- the privacy, subprocessor, incident-response, and support artifacts are ready
  for customer review;
- the supported deployment and data-residency boundaries are contractually clear;
- at least one production-like pilot has completed its operational observation
  window without an unresolved severity-one incident.

Until then, the correct claim is `enterprise pilot ready`, qualified by the
deployment topology and the controls actually evidenced.

## 3. Governance layers

Every strategic enterprise feature SHALL declare impact across these layers:

| Layer | Required question |
| --- | --- |
| Business and stakeholder | Which procurement, risk, or operating decision does this unblock? |
| Data and semantic | Which data classes, provenance, retention, and tenant boundaries are affected? |
| Application and service | Which contracts, workers, APIs, state transitions, and failure boundaries change? |
| UX/UI | Which administrator or reviewer must understand or control the behavior? |
| Infrastructure and operations | How is it deployed, observed, recovered, scaled, and rolled back? |
| Security, privacy, and compliance | Which threats, controls, legal duties, and evidence obligations apply? |
| GenAI | Can model behavior affect data, decisions, exports, or claims, and what review gate applies? |

## 4. Control maturity model

| State | Meaning | Minimum evidence |
| --- | --- | --- |
| `identified` | Risk and owner are known. | Gap statement, priority, accountable role |
| `specified` | Behavior and control objective are testable. | PRD, OpenSpec, acceptance criteria, threat/failure analysis |
| `implemented` | The control exists behind a governed rollout path. | Reviewed code, migration/flag, automated tests |
| `verified` | The control survives relevant positive, negative, isolation, and recovery tests. | CI results, test report, security review |
| `operated` | The control has run in a production-like environment for its observation window. | Metrics, alerts, runbook execution, incident record |
| `auditable` | A third party can verify design and operation without reconstructing evidence manually. | Versioned evidence pack, owner attestation, timestamps |

`Done` in a sprint does not imply `operated` or `auditable`.

## 5. Spec-driven lifecycle

Each strategic feature follows:

`Gap -> control objective -> PRD -> OpenSpec -> ADR/threat model -> implementation plan -> incremental PRs -> verification -> operational acceptance -> evidence pack`

Required gates:

1. **Intake gate:** risk, priority, scope, owner, and commercial blocker agreed.
2. **Design gate:** PRD, OpenSpec, architecture impacts, abuse cases, failure
   modes, rollout, and rollback reviewed.
3. **Build gate:** implementation is tenant-safe, observable, feature-gated
   where appropriate, and covered by automated tests.
4. **Verification gate:** security, isolation, concurrency, recovery, and
   performance criteria pass.
5. **Operational gate:** runbook and alerts are exercised in a production-like
   environment for the feature's observation window.
6. **Evidence gate:** evidence is versioned, exportable, scoped, and attributable
   to an owner and release.

## 6. Definition of Enterprise Done

A strategic feature is enterprise-done only when:

- control objective and non-goals are explicit;
- data classification and tenant boundaries are documented;
- authorization, audit, and privacy requirements are tested;
- failure, retry, idempotency, concurrency, and recovery behavior are tested;
- service-level indicators and alerts exist;
- runbook, owner, escalation path, and rollback procedure exist;
- migration and rollback have been rehearsed where state changes;
- evidence can be exported without manual database reconstruction;
- operational acceptance is signed off;
- remaining limitations and residual risks are recorded.

## 7. Program sequence

| Wave | Strategic feature | Priority | Entry state | Exit requirement |
| --- | --- | --- | --- | --- |
| ER-0 | Control registry and evidence governance | P0 program gate | identified | auditable registry process |
| ER-1 | External background-job runtime | P1 blocker | specified | operated |
| ER-2 | Backup, restore, RTO, RPO, and disaster recovery | P0 blocker | identified | auditable |
| ER-3 | Secure software supply chain and vulnerability management | P0 blocker | identified | operated |
| ER-4 | Tenant-scoped tamper-evident audit evidence pack | P1 blocker | identified | auditable |
| ER-5 | Privacy/legal and subprocessor assurance pack | P1 blocker | identified | auditable |
| ER-6 | Enterprise identity lifecycle, MFA, and offboarding | P1 blocker | identified | operated |
| ER-7 | Deployment topology, residency, and contract boundaries | P1 blocker | identified | auditable |
| ER-8 | Independent assurance, load validation, and pilot exit | P0 release gate | identified | auditable |

Waves describe governance order, not necessarily serial implementation. ER-2
and ER-3 may start while ER-1 is being built, but UKIP SHALL NOT claim completion
until dependencies and evidence gates are satisfied.

The implementation order is governance baseline; operational foundations
(`ER-BCP-001`, `ER-SDLC-001`, `ER-IR-001`); runtime separation
(`ER-OPS-001`); assurance packaging (`ER-AUD-001`, `ER-PRIV-001`,
`ER-DEP-001`); enterprise administration (`ER-IAM-001`); and scale plus
independent validation (`ER-PERF-001`, `ER-ASSURE-001`).

## 8. Control ownership

Each control records three roles even if one person temporarily holds all three:

- **Control owner:** accountable for control design and residual risk.
- **Implementation owner:** accountable for code and delivery.
- **Operational owner:** accountable for monitoring, drills, incidents, and evidence.

The same person must not self-attest an independent security assessment.

## 9. Evidence rules

Evidence SHALL be:

- tied to a release, environment, tenant scope, and time window;
- reproducible or independently inspectable;
- free of secrets and unnecessary personal data;
- retained according to an explicit policy;
- immutable or integrity-verifiable where it supports audit claims;
- invalidated when a material architecture or control change occurs.

## 10. Claim policy

| Claim | Permitted condition |
| --- | --- |
| `advanced prototype` | Core workflows work, but material controls remain below verified |
| `production-like pilot` | P0 technical controls are verified and deployment is constrained |
| `enterprise pilot ready` | No P0 below operated; P1 limitations are disclosed contractually |
| `enterprise-ready` | Target in section 2 is fully met |
| `SOC 2/ISO 27001 compliant` | Never without the corresponding independent certification or formal scope |

## 11. Source of truth

- Control status: `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
- Program lifecycle: this document
- Product intent: epic and story PRDs under `docs/product/`
- Behavioral contracts: `openspec/specs/` and active `openspec/changes/`
- Architecture decisions: ADRs or `design.md` inside the related OpenSpec change
- Runtime evidence: tests, CI artifacts, operational reports, and evidence packs
- Machine-readable companion: `backend/enterprise_controls.py`, validated for
  stable-ID, priority, maturity, and related-work parity with the register

