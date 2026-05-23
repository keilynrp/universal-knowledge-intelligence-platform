## 1. Enterprise architecture baseline

- [x] 1.1 Define UKIP enterprise architecture domains and owners.
- [x] 1.2 Classify active specs by primary and secondary architecture domains.
- [x] 1.3 Document relationship between enterprise architecture governance and canonical semantic data governance.
- [x] 1.4 Define what qualifies as a strategic architecture decision.
- [x] 1.5 Create architecture decision record template.

## 2. Business and stakeholder architecture

- [x] 2.1 Define stakeholder segments and decision contexts.
- [x] 2.2 Map UKIP business capabilities to stakeholder outcomes.
- [x] 2.3 Define executive intelligence value propositions.
- [x] 2.4 Define success metrics for research stakeholders.
- [x] 2.5 Map `research-stakeholder-executive-demo` to business/stakeholder capabilities.

## 3. Data and semantic architecture

- [x] 3.1 Position `canonical-semantic-data-governance` as the data architecture backbone.
- [x] 3.2 Map source profiling, mapping suggestions, canonical model, authority resolution, enrichment, and linked-data alignment into the enterprise architecture.
- [x] 3.3 Define data quality and provenance principles for strategic decisions.
- [x] 3.4 Define how new data-model specs declare enterprise architecture impact.
- [x] 3.5 Validate active data specs against enterprise architecture domains.

## 4. Application and service architecture

- [x] 4.1 Inventory backend services, routers, adapters, schedulers, workers, and analytics services.
- [x] 4.2 Define service boundary principles for ingestion, enrichment, reconciliation, analytics, reports, and AI assistance.
- [x] 4.3 Define API contract expectations for stakeholder-facing capabilities.
- [x] 4.4 Define integration dependency rules and failure boundaries.
- [x] 4.5 Add service architecture review checklist for future implementation specs.

## 5. UX/UI experience architecture

- [x] 5.1 Define navigation and product surface architecture for dashboards, entity detail, ingestion/mapping, review, and reports.
- [x] 5.2 Define UX principles for provenance, authority, enrichment, confidence, null states, and AI-generated content.
- [x] 5.3 Map stakeholder workflows to UX surfaces.
- [x] 5.4 Define executive report and dashboard experience requirements.
- [x] 5.5 Add UX/UI architecture review checklist for future frontend specs.

## 6. Infrastructure and operations architecture

- [x] 6.1 Inventory deployment topology, containers, health checks, migrations, background jobs, and environment variables.
- [x] 6.2 Define production readiness principles for reliability, observability, rollback, backup, and recovery.
- [x] 6.3 Define operational health metrics and alerts.
- [x] 6.4 Define deployment safety requirements for specs that modify startup, database, jobs, or external integrations.
- [x] 6.5 Add infrastructure/operations review checklist for future specs.

## 7. Security, privacy, and compliance architecture

- [x] 7.1 Define authentication, authorization, and data access principles.
- [x] 7.2 Define audit and provenance requirements for sensitive decisions and AI-assisted outputs.
- [x] 7.3 Define source licensing and provider terms review requirements.
- [x] 7.4 Define privacy expectations for person, affiliation, institutional, and geographic data.
- [x] 7.5 Add security/privacy review checklist for future specs.

## 8. GenAI cross-cutting capability

- [x] 8.1 Define allowed GenAI roles across ingestion, mapping, reconciliation, enrichment, analytics, reporting, UX, and architecture governance.
- [x] 8.2 Define evidence-grounding rules for GenAI-generated suggestions and narratives.
- [x] 8.3 Define confidence, review, and non-overwrite rules for AI-assisted outputs.
- [x] 8.4 Define AI impact metadata for architecture decision records.
- [x] 8.5 Add GenAI governance checklist for future specs.

## 9. Validation

- [x] 9.1 Run `npx openspec validate ukip-enterprise-architecture-governance --strict`.
- [x] 9.2 Run `npx openspec list`.
- [x] 9.3 Review consistency with `canonical-semantic-data-governance` and active subordinate specs.
