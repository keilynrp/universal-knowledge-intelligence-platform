## Why

Once UKIP preserves structured affiliation data, the next strategic step is reconciliation: turning raw or provider-specific institution mentions into canonical institutional identities. Research stakeholders need to trust that "UNAM", "Universidad Nacional Autónoma de México", OpenAlex institution IDs, and ROR identifiers can be understood as the same organization when appropriate.

Without institutional reconciliation, UKIP can show publications and authors, but institution-level intelligence remains brittle:

- Collaboration networks fragment across spelling variants.
- Geographic analytics depend on weak text parsing.
- Benchmarking by institution or country is unreliable.
- Stakeholder briefs cannot defend institution-level claims.
- Integration with Research Organization Registry (ROR) remains manual.

This change defines a reconciliation layer that resolves affiliation candidates against standardized international registries, with ROR as the primary authority and OpenAlex/Wikidata as supporting evidence.

## What Changes

- **New**: Institution affiliation reconciliation service.
- **New**: ROR-backed institutional authority candidate model.
- **New**: Candidate scoring model using identifiers, names, aliases, country, location, domains, and provider context.
- **New**: Persisted institutional authority records and links from authors/publications to canonical institutions.
- **New**: API endpoints for previewing, accepting, rejecting, and auditing institution matches.
- **Modified**: Scientific affiliation normalization output becomes the input to reconciliation.

## Capabilities

### New Capabilities

- `institution-reconciliation-service`: Resolve institution mentions to canonical international registry identities.
- `ror-registry-adapter`: Query and parse ROR organization candidates.
- `institution-authority-records`: Persist canonical institution identities, aliases, external IDs, and confidence.
- `institution-affiliation-review`: Review, accept, reject, and audit institution affiliation matches.

### Modified Capabilities

- `scientific-affiliation-contract`: Structured affiliation data feeds institution reconciliation.
- `evidence-traceability-ui`: Stakeholder-facing evidence can reference canonical institution identities once resolved.

## Impact

- **Backend**: New resolver service, ROR adapter, candidate scoring helpers, API router, and persistence path.
- **Data model**: Reuse existing authority models where possible; add fields only if current authority records cannot represent ROR/OpenAlex/Wikidata institution identities cleanly.
- **Frontend**: Review queue or compact institution reconciliation panel for admin/editor workflows.
- **Analytics**: Future institution-level dashboards can rely on canonical institution IDs.
- **Tests**: Contract tests for ROR candidate resolution, scoring, dedupe, persistence, and review actions.

## Success Criteria

- Given an affiliation with a ROR ID, UKIP resolves it with high confidence without text search.
- Given an affiliation with only text and country, UKIP can find and rank ROR/OpenAlex candidates.
- Given common aliases, UKIP can reconcile variants to the same canonical institution.
- Given ambiguous institution names, UKIP marks them for review instead of auto-linking unsafely.
- Accepted institution matches become reusable authority records for future imports.
