# Enterprise Readiness Operational Source of Truth

**Status:** Approved design  
**Date:** 2026-06-12  
**Target:** Regulated institutional customers and demanding procurement reviews

## 1. Purpose

Align UKIP's enterprise-readiness documentation into one governed operational
system. The system must show what is required, what is implemented, what has
been operated, and what evidence supports each claim.

This work does not declare UKIP enterprise-ready. It defines the authoritative
path and evidence gates required to earn that claim.

## 2. Target Outcome

UKIP may make an unqualified `enterprise-ready` claim only when it can pass
demanding institutional procurement and regulated-customer review without
reconstructing controls or evidence ad hoc.

The target includes:

- durable and recoverable production operations;
- tenant-safe identity, data, audit, and job execution;
- measurable recovery, capacity, and incident-response behavior;
- legally reviewed privacy and subprocessor artifacts;
- explicit deployment and data-residency boundaries;
- independently assessed security posture;
- exportable, integrity-verifiable control evidence.

Certification claims remain out of scope unless granted by the corresponding
independent assessment.

## 3. Authority Model

The operational source of truth uses the following hierarchy:

1. `docs/product/ENTERPRISE_CONTROL_REGISTER.md`
   - Authority for control objective, priority, maturity, ownership, risk,
     evidence, dependencies, and closure criteria.
2. `docs/product/ENTERPRISE_READINESS_PROGRAM.md`
   - Authority for target posture, governance, lifecycle, maturity semantics,
     waves, reviews, and claim policy.
3. `docs/product/epics/EPIC-018-enterprise-assurance-and-operational-readiness.md`
   - Program execution scope and consolidated outcome.
4. `docs/product/stories/US-073` through `US-081`
   - Implementable outcomes with acceptance, operational, and evidence gates.
   - `US-042` remains the existing story for background-job externalization.
5. `docs/product/PROGRAM_BACKLOG.md`
   - Portfolio priority, sequence, and delivery status.
6. `docs/product/TRACEABILITY_MATRIX.md`
   - Control-to-story-to-spec-to-code-to-test-to-operational-evidence mapping.
7. `backend/enterprise_readiness.py`
   - Runtime projection of the authoritative register, not an independent
     control inventory.

If these artifacts conflict, the control register governs control status and
the program document governs maturity and claim semantics.

## 4. Maturity Model

Every control uses the same monotonic maturity model:

`identified -> specified -> implemented -> verified -> operated -> auditable`

| State | Required proof |
| --- | --- |
| `identified` | Risk, priority, accountable role, and intended outcome |
| `specified` | Testable objective, acceptance criteria, failure analysis, rollout, and rollback |
| `implemented` | Reviewed implementation, migration or flag where needed, and automated tests |
| `verified` | Positive, negative, isolation, recovery, and security verification appropriate to the control |
| `operated` | Production-like execution for a defined observation window with metrics, alerts, and runbook evidence |
| `auditable` | Versioned, attributable, scoped, exportable, and integrity-verifiable evidence |

Sprint completion does not raise a control automatically. Status is always the
lowest maturity supported by evidence.

## 5. Control Schema

Each active control row must provide or link to:

- stable control ID;
- objective and business/procurement blocker;
- priority and current maturity;
- target maturity;
- control, implementation, and operational owners;
- affected data classes and tenant boundaries;
- dependencies and related stories/specs;
- implementation evidence;
- verification evidence;
- operational observation window;
- audit evidence and retention rule;
- residual risk, exception owner, and expiry where applicable;
- explicit entry and exit criteria for the next maturity state.

The Markdown register remains human-authoritative. The runtime representation
must use stable IDs and validation tests to detect missing or divergent controls.

## 6. Program Scope

EPIC-018 covers these control families:

| Control | Delivery unit | Required target |
| --- | --- | --- |
| ER-CTRL-001 | Program governance and evidence index | auditable |
| ER-OPS-001 | US-042 external background-job runtime | operated |
| ER-BCP-001 | US-073 backup, restore, RTO/RPO, DR | auditable |
| ER-SDLC-001 | US-074 secure SDLC, SBOM, vulnerability management | operated |
| ER-AUD-001 | US-075 audit evidence pack and integrity verification | auditable |
| ER-PRIV-001 | US-076 privacy, legal, and subprocessor assurance | auditable |
| ER-IAM-001 | US-077 identity lifecycle, MFA, and offboarding | operated |
| ER-DEP-001 | US-078 topology and data-residency governance | auditable |
| ER-IR-001 | US-079 incident response and notification | operated |
| ER-PERF-001 | US-080 capacity, load, and degradation envelope | operated |
| ER-ASSURE-001 | US-081 independent assurance and pilot exit | auditable |

Existing tenant isolation, data lifecycle, secret rotation, observability, and
authentication controls remain prerequisite capabilities. They require ongoing
release and drill evidence even when their implementation work is complete.

## 7. Delivery Sequence

The recommended sequence is dependency-driven:

1. **Governance baseline**
   - Normalize the register, owners, evidence schema, and traceability.
2. **Operational foundations**
   - ER-BCP-001, ER-SDLC-001, and ER-IR-001.
3. **Runtime separation**
   - ER-OPS-001, enabling safe horizontal scaling and durable jobs.
4. **Assurance packaging**
   - ER-AUD-001, ER-PRIV-001, and ER-DEP-001.
5. **Enterprise administration**
   - ER-IAM-001.
6. **Scale and independent validation**
   - ER-PERF-001 and ER-ASSURE-001.

Work may proceed in parallel where dependencies permit, but control maturity
cannot advance until its required evidence exists.

## 8. Story Contract

Each enterprise story must contain:

- linked control IDs and procurement outcome;
- current and target maturity;
- scope and non-goals;
- architecture and data-boundary impact;
- abuse cases, failure modes, and recovery behavior;
- implementation slices and dependencies;
- automated acceptance tests;
- operational drill and observation window;
- evidence artifacts and retention;
- rollout, rollback, and residual risk;
- Definition of Enterprise Done.

Story state and control maturity are separate fields.

## 9. Runtime Projection

`backend/enterprise_readiness.py` must stop maintaining a smaller, manually
curated gap taxonomy that can contradict the register.

The implementation should use one of these guarded approaches:

1. Generate or load a structured control manifest validated against the
   Markdown register.
2. Maintain a structured manifest as the machine-readable companion and test
   exact stable-ID parity with the Markdown register.

The second approach is recommended because it avoids parsing Markdown at
runtime while preserving explicit synchronization checks.

The API should expose:

- register update date and target claim;
- control counts by priority and maturity;
- controls with owners, next gate, evidence summary, and related work;
- prerequisite capabilities requiring recurring evidence;
- a clear non-certification disclaimer.

## 10. Historical Documentation

`docs/UKIP_ENTERPRISE_ROADMAP.md` and other superseded enterprise assessments
must not remain implied operational authorities.

They will:

- receive a prominent `Historical` notice;
- link to the program and control register;
- be indexed in `docs/reference/HISTORICAL_REFERENCE_INDEX.md`;
- retain useful context without contributing current status or priorities.

`docs/ukip_system_evaluation.md` will be classified as a dated assessment, not
as the current readiness baseline.

## 11. Consistency Controls

Documentation validation must detect:

- control IDs present in only one authoritative artifact;
- stories referenced by EPIC-018 but missing from the story directory;
- maturity values outside the approved model;
- stale update dates after a control change;
- runtime controls that diverge from the register;
- active documents that still cite historical roadmaps as operational sources.

Focused tests or a documentation lint script should run in CI.

## 12. Completion Criteria

This documentation alignment is complete when:

- the authority hierarchy is documented in governance and product indexes;
- all EPIC-018 controls have complete register metadata;
- US-073 through US-081 exist with enterprise story contracts;
- backlog and traceability show control dependencies and current maturity;
- the runtime projection has stable-ID parity with the register;
- old roadmaps are classified and indexed as historical;
- CI detects future authority drift;
- no document claims readiness beyond the evidence-backed claim policy.

## 13. Rollout

The update should be delivered in small reviewable slices:

1. authority and governance alignment;
2. register normalization;
3. epic, stories, backlog, and traceability;
4. runtime projection synchronization;
5. historical-document classification;
6. documentation drift checks and final consistency review.

No control maturity is raised solely by this documentation update.
