## 1. Field grouping contract

- [ ] 1.1 Inventory current entity detail payload fields and map them to provenance layers.
- [ ] 1.2 Define frontend `EntityDetailLayer` / `EntityDetailField` types.
- [ ] 1.3 Implement grouping helper for original ingestion, normalized identity, external enrichment, and authority/audit.
- [ ] 1.4 Add tests for grouping representative uploaded, demo, and OpenAlex-enriched records.

## 2. Source terminology

- [ ] 2.1 Replace ambiguous "Source" label for `source` with "Ingestion source".
- [ ] 2.2 Replace ambiguous "Source" label for `enrichment_source` with "Enrichment provider".
- [ ] 2.3 Reserve "Authority source" for authority records/resolution providers.
- [ ] 2.4 Add EN/ES translations for all provenance labels.

## 3. Null semantics

- [ ] 3.1 Implement field-state helper returning `not_provided`, `pending_normalization`, `unresolved_enrichment`, `not_applicable`, or `unknown`.
- [ ] 3.2 Explain missing canonical ID with state-specific copy.
- [ ] 3.3 Explain missing entity type with state-specific copy.
- [ ] 3.4 Explain missing enrichment DOI/concepts/affiliations based on enrichment status/source.
- [ ] 3.5 Add tests for null-state copy.

## 4. Entity detail UI

- [ ] 4.1 Refactor entity detail page into provenance sections.
- [ ] 4.2 Render original ingestion fields separately from normalized UKIP identity.
- [ ] 4.3 Render external enrichment provider fields separately from ingestion fields.
- [ ] 4.4 Render structured scientific affiliations under external enrichment when available.
- [ ] 4.5 Add compact provenance badges for original, normalized, enrichment, and authority fields.

## 5. Backend/API follow-up

- [ ] 5.1 Evaluate whether current entity detail payload exposes enough import batch and original field metadata.
- [ ] 5.2 If needed, add a backend serializer helper for layered detail metadata.
- [ ] 5.3 Ensure serializer preserves backwards-compatible fields.
- [ ] 5.4 Add API tests if serializer is introduced.

## 6. Validation

- [ ] 6.1 Add frontend tests or component snapshots for layered detail rendering.
- [ ] 6.2 Run `npx tsc --noEmit`.
- [ ] 6.3 Run `npx openspec validate entity-provenance-layering --strict`.
- [ ] 6.4 Smoke test entity details for uploaded, demo, and OpenAlex-enriched entities.
