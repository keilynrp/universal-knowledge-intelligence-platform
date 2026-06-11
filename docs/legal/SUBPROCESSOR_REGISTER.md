# Sub-processor Register (UKIP)

> **DISCLAIMER / AVISO:** Base template prepared by the UKIP engineering team.
> NOT legal advice. Requires review by qualified counsel before being signed
> or relied upon in any contract or compliance representation.

This register lists the third parties that may process, store, or transit
customer data (or operational data about the platform) as part of operating
UKIP. Optional services are **disabled by default** and engaged only when the
customer enables the corresponding feature.

## Register

| Name | Purpose | Data categories | Location | Status |
|------|---------|-----------------|----------|--------|
| `[OPERATOR TO FILL: VPS/hosting provider name]` | Hosting of the production VPS (Dokploy, FastAPI backend, Next.js frontend, Rust engine, PostgreSQL, ChromaDB, Redis) | All customer data processed by the platform | `[OPERATOR TO FILL: region]` | Active — core infrastructure |
| Cloudflare | DNS and TLS reverse proxy in front of the origin | Traffic metadata (IP addresses, request headers); payloads transit encrypted through the proxy | Global edge network | Active — core infrastructure |
| GitHub / GHCR (Microsoft) | Source code hosting, CI/CD, container image registry | Source code and container images only — **no customer data** | United States (global) | Active — development infrastructure |
| `[TO FILL when EPIC-018 bucket provisioned: S3 backup provider + region]` | Off-site storage of encrypted database backups (EPIC-018 program) | Encrypted database backups (all customer data, encrypted) | `[TO FILL: region]` | Pending — backup program defined, bucket not yet provisioned |
| Sentry | Error telemetry for the backend | Error events and stack traces; may incidentally include request metadata | United States / EU (per DSN configuration) | **Optional — flag-gated, default OFF** (`SENTRY_ENABLED`, default false; see `backend/telemetry.py`) |
| OpenAI | LLM features (AI enrichment / RAG answering) when the customer configures an OpenAI integration | Text snippets submitted to LLM features (may include research-entity data the customer chooses to process) | United States | **Optional — default OFF**; engaged only if the customer creates and activates an AI integration |

Notes:

- Public bibliographic authority sources queried during authority resolution
  (Wikidata, VIAF, ORCID, OpenAlex, DBpedia) are **not** sub-processors: UKIP
  sends lookup queries (entity names/identifiers) to these public registries
  and receives public records back; they do not process customer data on the
  operator's behalf. They are documented as recipients in
  [ROPA.md](ROPA.md) activity 2 for transparency.
- No entry in this register is invented: provider-specific values the
  engineering team cannot attest to are left as `[OPERATOR TO FILL]`.

## Review and change management

| Item | Value |
|------|-------|
| Last reviewed | 2026-06-11 |
| Review cadence | Quarterly |
| Change-notice process | Customers are notified in writing before a sub-processor is added or replaced, with an objection window per Section 8 of [DPA_BASELINE.md](DPA_BASELINE.md). Changes are recorded in this file's git history. |

## Change log

| Date | Change |
|------|--------|
| 2026-06-11 | Initial register created (EPIC-020, Task 12). |
