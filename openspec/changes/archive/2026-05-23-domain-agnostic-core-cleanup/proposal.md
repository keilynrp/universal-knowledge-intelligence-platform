## Why

UKIP evolved from an early e-commerce/catalog normalization tool into a domain-agnostic scientific intelligence platform. Some foundational commerce assumptions still appear in generic product surfaces: dataset import, entity detail, harmonization, import/export, dashboards, analytics, reports, API docs, tests, and mapping prompts.

These residues create strategic ambiguity. Research stakeholders may see `product`, `brand`, `SKU`, `store`, or `mapped products` in workflows that should describe publications, authors, institutions, concepts, datasets, grants, patents, places, or arbitrary entities. At the same time, commerce support may remain valuable as a future domain adapter or enrichment niche.

This change defines how UKIP cleans the core while preserving e-commerce as an optional adapter/domain pack.

## What Changes

- **New**: Domain-agnostic core boundary rules for UI, mapping, analytics, reports, docs, and backend contracts.
- **New**: Legacy commerce adapter containment requirements.
- **New**: UI copy neutrality requirements for generic dataset workflows.
- **Modified**: Commerce-specific examples move out of core mapping prompts and generic labels into adapter/domain-pack documentation.
- **Modified**: Active docs should distinguish historical evolution from current product architecture.

## Capabilities

### New Capabilities

- `domain-agnostic-core-boundary`: Defines which terms and assumptions are allowed in the UKIP core.
- `legacy-commerce-adapter-containment`: Preserves commerce connectors as optional adapters without making them core model concepts.
- `ui-copy-domain-neutrality`: Ensures generic product surfaces use entity/source/evidence language rather than commerce-first terminology.

### Governed / Subordinate Capabilities

- `canonical-semantic-governance`
- `source-profiling-contract`
- `mapping-suggestion-contract`
- `entity-provenance-layering`
- `authority-enrichment-bridge`
- `ukip-enterprise-architecture-governance`

## Impact

- **Frontend**: Import, entity detail, harmonization, import/export, dashboards, integrations, and translations should use domain-neutral wording unless a commerce adapter is explicitly active.
- **Backend**: Universal column mapping and LLM mapping descriptions should separate core aliases from domain-specific alias packs.
- **Engine**: Analytics defaults should prefer domain-neutral/scientific fields while retaining legacy compatibility where required.
- **Docs**: Active docs should describe UKIP as a domain-agnostic scientific intelligence platform; historical commerce references should be marked as evolution context.
- **Tests**: Core tests should avoid brand/SKU/product fixtures unless testing commerce adapters or backward compatibility.

## Success Criteria

- Generic import and entity detail workflows no longer foreground products, brands, SKUs, or barcodes.
- Commerce connector routes and adapters remain available only as explicit source adapters or feature-flagged modules.
- Mapping suggestions distinguish universal identifiers from commerce identifiers.
- Dashboards and reports no longer label generic secondary labels as brands by default.
- Documentation clearly separates historical origin from current UKIP architecture.
