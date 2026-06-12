# EPIC-018 - Enterprise Assurance and Operational Readiness

## 1. Summary

Move UKIP from enterprise-capable software to an evidence-backed,
enterprise-operable platform for demanding private academic and commercial
stakeholders.

## 2. Problem

UKIP has strong product and technical controls, but several controls remain
incomplete as operating systems: background work shares the web lifecycle,
recovery objectives are not measured, security supply-chain gates are incomplete,
and customer assurance artifacts are not yet packaged for procurement.

## 3. Objective

Deliver the P0/P1 controls in the enterprise control register through
spec-driven lifecycles, operational exercises, and exportable evidence.

## 4. Non-goals

- claiming certification without independent assessment;
- treating policy documents as proof of operation;
- adding heavyweight infrastructure without a supported workload or control need;
- hiding residual risk behind a readiness score.

## 5. Success criteria

- no P0 or P1 control remains below `operated`;
- customer-relevant P0/P1 controls reach `auditable`;
- recovery, incident, identity, and deletion drills are completed;
- security gates block releases on agreed severity thresholds;
- an enterprise assurance pack can be delivered without ad hoc reconstruction.

## 6. Workstreams

| Story | Strategic feature | Priority | State |
| --- | --- | --- | --- |
| US-042 | External background-job runtime | P1 | Specifying |
| US-073 | Backup, restore, RTO/RPO, and disaster recovery | P0 | Planned |
| US-074 | Secure SDLC, SBOM, and vulnerability management | P0 | Planned |
| US-075 | Audit evidence pack and integrity verification | P1 | Planned |
| US-076 | Privacy, legal, and subprocessor assurance pack | P1 | Planned |
| US-077 | Enterprise identity lifecycle and MFA | P1 | Planned |
| US-078 | Deployment topology and data residency governance | P1 | Planned |
| US-079 | Incident response and customer notification readiness | P0 | Planned |
| US-080 | Capacity, load, and degradation envelope | P1 | Planned |
| US-081 | Independent assurance and enterprise pilot exit gate | P0 | Planned |

## 6.1 Control mapping

| Control | Delivery | Current maturity | Target |
| --- | --- | --- | --- |
| ER-CTRL-001 | EPIC-018 governance | specified | auditable |
| ER-OPS-001 | US-042 | specified | operated |
| ER-BCP-001 | US-073 | identified | auditable |
| ER-SDLC-001 | US-074 | implemented | operated |
| ER-AUD-001 | US-075 | identified | auditable |
| ER-PRIV-001 | US-076 | specified | auditable |
| ER-IAM-001 | US-077 | identified | operated |
| ER-DEP-001 | US-078 | identified | auditable |
| ER-IR-001 | US-079 | identified | operated |
| ER-PERF-001 | US-080 | identified | operated |
| ER-ASSURE-001 | US-081 | identified | auditable |

Delivery sequence: governance; BCP/SDLC/incident response; background-job
separation; audit/privacy/residency packaging; identity lifecycle; capacity and
independent assurance. Story completion and control maturity remain separate.

## 7. Governance

All stories follow `docs/product/ENTERPRISE_READINESS_PROGRAM.md` and update
`docs/product/ENTERPRISE_CONTROL_REGISTER.md`. A story's sprint status and its
control maturity are separate.

## 8. Architecture impact

- Primary: infrastructure and operations; security, privacy, and compliance.
- Secondary: application/service, business/stakeholder, data/semantic, UX/UI.
- GenAI: affected features must preserve evidence, tenant scope, and human
  approval where AI output influences control decisions or customer claims.

## 9. Release posture

Completion of this epic is a prerequisite for an unqualified enterprise-ready
claim. Individual stories may support controlled enterprise pilots earlier when
their limitations are disclosed.

