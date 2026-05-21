## Context

UKIP is evolving into a scientific intelligence platform. That evolution requires enterprise architecture discipline without becoming bureaucratic. TOGAF-inspired thinking is useful, but UKIP needs a practical architecture method tailored to its own product thesis:

- scientific and institutional intelligence,
- evidence-based enrichment,
- semantic canonical modeling,
- authority resolution,
- linked-data interoperability,
- executive reporting,
- stakeholder-specific decision support,
- GenAI as a transversal accelerator.

This spec acts as UKIP's enterprise architecture organizer. It does not replace detailed specs. It governs how they fit together.

## Goals / Non-Goals

**Goals:**
- Define UKIP's enterprise architecture domains.
- Require strategic specs and major implementation decisions to declare their architectural impact.
- Connect business/stakeholder goals with data, services, UX/UI, infrastructure, operations, security, and AI.
- Establish an architecture decision record contract.
- Treat GenAI as a governed cross-cutting capability.
- Position `canonical-semantic-data-governance` as the data architecture backbone under the enterprise architecture layer.

**Non-Goals:**
- Fully implement TOGAF ADM artifacts.
- Create heavyweight approval gates for every small code change.
- Replace OpenSpec as the change-management mechanism.
- Replace product discovery, UX research, security review, or operational runbooks.
- Treat GenAI as a substitute for data quality, evidence, or authority resolution.

## Enterprise Architecture Domains

### 1. Business and stakeholder architecture

Defines why UKIP exists and who it serves.

Includes:

- stakeholder segments,
- research decision contexts,
- executive intelligence outcomes,
- institutional value propositions,
- adoption and success metrics,
- capability maturity,
- product-market assumptions.

Representative stakeholders:

- research executives,
- research office leaders,
- institutional strategy teams,
- data stewards,
- librarians and knowledge managers,
- grant and portfolio managers,
- scientific intelligence analysts,
- policy and impact teams.

### 2. Data and semantic architecture

Defines UKIP's knowledge backbone.

Includes:

- semantic canonical layer,
- source profiling,
- mapping suggestions,
- entity and relationship modeling,
- provenance and field states,
- authority resolution,
- evidence-based enrichment,
- linked-data alignment,
- data quality and review workflows.

`canonical-semantic-data-governance` is the principal subordinate spec for this domain.

### 3. Application and service architecture

Defines how the product is decomposed into capabilities and services.

Includes:

- backend APIs,
- ingestion services,
- enrichment adapters,
- reconciliation services,
- analytics services,
- reporting services,
- scheduler/worker patterns,
- integration contracts,
- inter-service dependencies,
- failure boundaries.

### 4. UX/UI experience architecture

Defines how users perceive and operate UKIP.

Includes:

- navigation architecture,
- dashboards,
- entity detail views,
- mapping and review workflows,
- evidence traceability UI,
- executive reporting experiences,
- visual language,
- accessibility,
- progressive disclosure for technical evidence.

UX/UI must express architecture truth: source, canonical, enrichment, authority, confidence, and AI-generated content should be visually distinguishable where relevant.

### 5. Infrastructure and operations architecture

Defines how UKIP runs reliably.

Includes:

- deployment topology,
- environments,
- containerization,
- database migrations,
- background workers,
- health checks,
- observability,
- logging,
- backup/restore,
- operational runbooks,
- scalability,
- cost posture.

### 6. Security, privacy, and compliance architecture

Defines trust and protection concerns.

Includes:

- authentication and authorization,
- data access boundaries,
- audit trails,
- personally identifiable information,
- source licensing constraints,
- provider API terms,
- retention policies,
- secure configuration,
- secrets management.

### 7. GenAI cross-cutting capability

Defines how GenAI participates across the platform.

GenAI may assist:

- source profiling,
- mapping suggestion generation,
- entity reconciliation review,
- anomaly and inconsistency detection,
- report narrative generation,
- evidence explanation,
- stakeholder-specific brief generation,
- architecture decision drafting.

GenAI must be governed by:

- provenance,
- evidence grounding,
- confidence,
- review thresholds,
- non-overwrite rules,
- auditability,
- stakeholder impact measurement.

## Decisions

### D1: Enterprise architecture sits above semantic data governance

**Decision:** `ukip-enterprise-architecture-governance` SHALL govern strategic UKIP specs across business, data, services, UX/UI, infrastructure, operations, security, and AI. `canonical-semantic-data-governance` SHALL be treated as its data architecture backbone.

**Rationale:** UKIP's semantic model is central, but enterprise architecture must also govern business value, user experience, service boundaries, deployment, security, and operational readiness.

### D2: Strategic specs declare architecture impact

**Decision:** Any strategic spec SHALL identify affected architecture domains and describe impact, dependencies, risks, and success criteria.

**Rationale:** This keeps implementation aligned with stakeholder outcomes and prevents isolated technical decisions.

### D3: Architecture decisions are lightweight but traceable

**Decision:** UKIP SHALL use lightweight architecture decision records for decisions that change strategic direction, core data semantics, service boundaries, infrastructure posture, security posture, UX architecture, or GenAI behavior.

**Rationale:** UKIP needs architectural memory without slowing routine development.

### D4: GenAI is transversal and governed

**Decision:** GenAI SHALL be modeled as a cross-cutting capability across architecture domains, not as an isolated product feature.

**Rationale:** GenAI can influence ingestion, mapping, enrichment, UX, reporting, and governance. Treating it as transversal makes its risks and value visible.

### D5: UX/UI reflects data and trust architecture

**Decision:** UX/UI architecture SHALL expose provenance, confidence, authority, enrichment, and AI-generated status when those distinctions affect user trust or decision-making.

**Rationale:** Research stakeholders need to understand why UKIP is recommending or reporting something.

### D6: Infrastructure choices must support product trust

**Decision:** Infrastructure and operations decisions SHALL be evaluated against reliability, observability, deployment safety, data integrity, and recovery.

**Rationale:** Scientific intelligence loses credibility if the system is unstable, opaque, or difficult to recover.

## Architecture Decision Record Shape

Strategic decisions should capture:

- decision title,
- date,
- status,
- context,
- business/stakeholder driver,
- affected architecture domains,
- options considered,
- decision,
- rationale,
- data/provenance impact,
- service/API impact,
- UX/UI impact,
- infrastructure/operations impact,
- security/privacy impact,
- GenAI impact,
- risks and mitigations,
- validation evidence,
- related specs.

## Spec Subordination Rules

New specs should state whether they affect:

- business/stakeholder architecture,
- data/semantic architecture,
- application/service architecture,
- UX/UI experience architecture,
- infrastructure/operations architecture,
- security/privacy/compliance architecture,
- GenAI cross-cutting capability.

Specs that affect more than one domain should identify the primary domain and secondary impacts.

## Open Questions

- Should architecture decision records live under `openspec/architecture-decisions/` or inside each change?
- What level of change requires an architecture decision record?
- Should UKIP maintain a formal capability map artifact outside OpenSpec?
- How should GenAI impact be scored: risk, value, automation level, or evidence dependency?
- Which stakeholder metrics best represent platform maturity?

## Rollout Plan

1. Establish the enterprise architecture governance spec.
2. Classify active specs by architecture domain.
3. Add lightweight architecture decision record templates.
4. Define UKIP capability map v1.
5. Connect semantic data governance to enterprise architecture.
6. Connect stakeholder demo/reporting specs to business and UX architecture.
7. Connect production readiness specs to infrastructure and operations architecture.
8. Define GenAI governance principles and review thresholds.
