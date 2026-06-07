# UKIP Conceptual Knowledge Base

## Purpose

This document is the governed starting point for UKIP's internal conceptual
knowledge base. It separates product concepts from implementation names and
provides definitions reusable in UI tooltips, onboarding, API documentation,
architecture specs, and customer-facing explanations.

The UI source of truth for concise definitions is
`frontend/app/lib/conceptGlossary.ts`. This document owns the broader conceptual
context. Changes to either source must keep both aligned.

## Entry template

Each concept should include:

- preferred term in English and Spanish;
- concise UI definition;
- expanded conceptual definition;
- examples and counterexamples;
- relationships to other UKIP concepts;
- owning module and architecture layer;
- implementation references;
- review owner and last-reviewed date.

## Entity / Entidad

### Concise definition

An entity is the canonical, traceable, and relatable unit UKIP uses to represent
an object of knowledge. It may consolidate multiple source records without
erasing their provenance.

Una entidad es la unidad canónica, trazable y relacionable que UKIP utiliza para
representar un objeto de conocimiento. Puede consolidar varios registros fuente
sin borrar su procedencia.

### Expanded definition

An entity is not merely an imported row. It is the stable knowledge object UKIP
constructs or identifies after source profiling and mapping. An entity can be a
person, institution, publication, concept, place, dataset, project, venue, or
another type declared by a domain.

Entities can carry normalized attributes, canonical identifiers, quality and
enrichment state, provenance, authority links, and relationships to other
entities.

### Examples

- A publication reconciled from CSV and Crossref records.
- An author linked to an ORCID authority record.
- An institution represented by several source-name variants.
- A concept extracted from and related to multiple publications.

### Counterexamples

- A raw CSV row before mapping is a source record, not necessarily a canonical entity.
- A provider response is enrichment evidence, not automatically the entity itself.
- A dashboard aggregate is a metric over entities, not an entity.
- A candidate authority match is a proposal until reviewed or accepted.

### Related concepts

- Source record
- Canonical identity
- Entity type
- Provenance
- Authority record
- Enrichment observation
- Relationship
- Domain

### Ownership and references

- Primary architecture layer: Data and semantic architecture
- Secondary layers: Application/service, UX/UI, security/governance
- Model: `backend/models.py`
- API: `backend/routers/entities.py`
- UI: `frontend/app/entities/`
- UI tooltip: `frontend/app/lib/conceptGlossary.ts`
- Last reviewed: 2026-06-07

## Governance backlog

The next concepts should be added in this order:

1. Source record
2. Canonical identity
3. Entity type
4. Domain
5. Provenance
6. Authority record
7. Enrichment observation
8. Quality score
9. Readiness
10. Evidence
