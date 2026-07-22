# UKIP API Reference

**Universal Knowledge Intelligence Platform — v1.0.0**

UKIP is a multi-domain knowledge management and enrichment platform. It ingests structured data (CSV, Excel, BibTeX, RIS, JSON, XML, Parquet, RDF), harmonises and de-duplicates records, enriches them via external academic APIs, and exposes analytics, reporting, and RAG-based AI search.

- **Base URL**: `http://localhost:8000`
- **Interactive docs**: `http://localhost:8000/docs` (Swagger UI)
- **OpenAPI schema**: `http://localhost:8000/openapi.json`
- **License**: MIT

---

## Authentication

All protected endpoints require a **Bearer JWT token** in the `Authorization` header.

```
Authorization: Bearer <token>
```

### Obtain a token

```
POST /auth/token
Content-Type: application/x-www-form-urlencoded

username=admin&password=yourpassword
```

**Response:**
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

**Account lockout**: After 5 consecutive failed login attempts, the account is locked for 15 minutes and HTTP 423 is returned.

### Role-Based Access Control (RBAC)

| Role | Permissions |
|---|---|
| `viewer` | Read-only: entities, analytics, RAG query, secondary labels, stats |
| `editor` | viewer + upload, edit/delete entities, rules, harmonization |
| `admin` | editor + optional source adapters, AI integrations, RAG indexing, domains |
| `super_admin` | admin + user management (full access) |

### API Keys (programmatic access)

Long-lived API keys prefixed `ukip_` can be used as Bearer tokens. Keys are shown **once** at creation; only a SHA-256 hash is stored. Manage via the `/api-keys` endpoints.

#### Scopes

A key carries one or more scopes. The scope required by a request is derived
from the route, not declared per endpoint:

| Request | Required scope |
|---|---|
| `GET`, `HEAD`, `OPTIONS` | `read` |
| `POST`, `PUT`, `PATCH`, `DELETE` | `write` |
| Any method on an administrative surface | `admin` |

Administrative surfaces are `/users` (except `/users/me`), `/api-keys`,
`/organizations`, `/stores`, `/admin/*`, `/ops/*`, `/settings/auth`,
`/auth/sso/settings`, `/webhooks`, `/alert-channels`, and `/workflows` — the
places where a leaked credential would expose stored secrets, mint further
credentials, destroy data, or configure a standing outbound data feed.

A small set of `POST` endpoints perform a query, preview, or export rather than
a mutation (`/rag/query`, `/nlq/query`, `/cube/query`, `/analyze`,
`/scientific/search`, `/upload/preview`, `/exports/*`, and similar). These
require only `read`, so an integrator does not need a write-scoped key to run a
search.

Scopes escalate: `admin` implies `write`, and `write` implies `read`.

**Scopes restrict; they never elevate.** The scope check runs in addition to
RBAC, so the effective permission is the intersection of the key's scopes and
the owning user's role. An `admin`-scoped key belonging to a `viewer` still has
viewer permissions.

A `403` naming a scope means the *credential* is too narrow — issue a new key
with wider scopes. A `403` naming a role means the *user* lacks permission, and
a new key will not help.

#### Rollout

Enforcement is controlled by `UKIP_API_KEY_SCOPES_ENFORCED`. While it is `0`
(warn mode), a request whose scope is insufficient still succeeds, and the
violation is recorded in the audit log under the action
`api_key.scope_violation`. Check `GET /health` → `features.api_key_scopes_enforced`
for the state of a running deployment.

### SSO (OAuth2 / OIDC)

| Method | Path | Description |
|---|---|---|
| `GET` | `/sso/login` | Initiate OAuth2/OIDC flow |
| `GET` | `/sso/callback` | OAuth2 callback; auto-provisions viewer account; redirects to frontend with token |

---

## Rate Limits

| Endpoint | Limit |
|---|---|
| `POST /auth/token` | 60 req/min per IP (5 attempts before lockout) |
| `POST /upload` | 60 req/min |
| `POST /users` | 100 req/hour |
| `POST /users/me/password` | 60 req/min |
| `POST /enrich/row/{id}` | 30 req/min |
| `POST /enrich/bulk` | 5 req/min |
| `POST /rag/index` | 60 req/min |
| `POST /stores/{id}/test` | 10 req/min |
| `POST /stores/{id}/pull` | 60 req/min |
| `POST /disambiguate/ai-resolve` | 10 req/min |
| All other endpoints | No explicit limit (subject to server capacity) |

Exceeding a rate limit returns **HTTP 429 Too Many Requests**.

---

## Security Headers

All responses include:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

---

## Endpoints by Tag

---

### Auth & SSO

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/token` | No | Obtain Bearer JWT (OAuth2 password flow) |
| `GET` | `/sso/login` | No | Initiate OAuth2/OIDC SSO login |
| `GET` | `/sso/callback` | No | OAuth2 callback — auto-provisions viewer account |

**POST /auth/token** — Body (form-encoded): `username`, `password`.
Response: `{ access_token, token_type }`.

---

### Users

Requires `super_admin` for all management endpoints. Any authenticated user can access `/users/me`.

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/users/me` | any | Current user profile |
| `PATCH` | `/users/me/profile` | any | Update own email, display_name, bio |
| `POST` | `/users/me/password` | any | Change own password |
| `POST` | `/users/me/avatar` | any | Upload avatar (base64 data URL) |
| `DELETE` | `/users/me/avatar` | any | Remove avatar |
| `GET` | `/users` | super_admin | List all users (`skip`, `limit` up to 500) |
| `POST` | `/users` | super_admin | Create user |
| `GET` | `/users/stats` | super_admin | User count by role, active/inactive |
| `GET` | `/users/{id}` | super_admin | Get user by ID |
| `PUT` | `/users/{id}` | super_admin | Update user (email, password, role, is_active) |
| `DELETE` | `/users/{id}` | super_admin | Soft-deactivate user |
| `POST` | `/users/{id}/activate` | super_admin | Reactivate deactivated user |

**POST /users** body:
```json
{ "username": "alice", "email": "alice@example.com", "password": "secret", "role": "editor" }
```
Roles: `viewer`, `editor`, `admin`, `super_admin`.

**PATCH /users/me/profile** body: any subset of `{ email, display_name, bio }`.

**POST /users/me/password** body: `{ current_password, new_password }`.

---

### Entities

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/entities` | viewer | List entities with filtering, sorting, pagination |
| `GET` | `/entities/grouped` | viewer | Entities grouped by primary_label |
| `GET` | `/entities/facets` | viewer | Value counts for facet fields |
| `GET` | `/entities/{id}` | viewer | Single entity by ID |
| `PUT` | `/entities/{id}` | editor | Update entity fields |
| `DELETE` | `/entities/{id}` | editor | Delete single entity |
| `DELETE` | `/entities/bulk` | editor | Delete list of entities by IDs (max 500) |
| `POST` | `/entities/bulk-update` | editor | Batch field updates for list of entities |
| `DELETE` | `/entities/all` | editor | Purge all entities (optionally with rules) |

**GET /entities** query params:

| Param | Default | Description |
|---|---|---|
| `skip` | 0 | Offset for pagination |
| `limit` | 100 | Page size (max 500) |
| `search` | — | Full-text filter on label, type, canonical_id |
| `sort_by` | `id` | `id`, `quality_score`, `primary_label`, `enrichment_status` |
| `order` | `asc` | `asc` or `desc` |
| `min_quality` | — | Float 0.0–1.0 quality score threshold |
| `ft_entity_type` | — | Exact facet filter |
| `ft_domain` | — | Exact facet filter |
| `ft_validation_status` | — | Exact facet filter |
| `ft_enrichment_status` | — | Exact facet filter |
| `ft_source` | — | Exact facet filter |

Response header: `X-Total-Count` = total matching records.

**DELETE /entities/all** query: `include_rules=true` to also purge normalization rules.

**POST /entities/bulk-update** body: `{ ids: [1,2,3], updates: { validation_status: "confirmed" } }`.

---

### Enrichment

| Method | Path | Min Role | Description |
|---|---|---|---|
| `POST` | `/enrich/row/{id}` | editor | Enrich single entity immediately |
| `POST` | `/enrich/bulk` | editor | Queue unenriched records for background enrichment |
| `POST` | `/enrich/bulk-ids` | editor | Queue specific entity IDs for enrichment |
| `GET` | `/enrich/stats` | viewer | Enrichment coverage stats + top concepts + citation distribution |
| `GET` | `/enrich/montecarlo/{id}` | viewer | Monte Carlo citation trajectory (5-year, 5000 simulations) |

**GET /enrich/stats** response shape:
```json
{
  "total_entities": 0, "enriched_count": 0, "pending_count": 0,
  "failed_count": 0, "enrichment_coverage_pct": 0.0,
  "top_concepts": [{"concept": "...", "count": 0}],
  "citations": { "average": 0, "max": 0, "total": 0, "distribution": {} }
}
```

---

### Ingestion

| Method | Path | Min Role | Description |
|---|---|---|---|
| `POST` | `/upload` | editor | Upload and import a data file |
| `POST` | `/upload/preview` | editor | Parse file without importing; return columns and sample rows |
| `POST` | `/upload/suggest-mapping` | editor | LLM-assisted column-to-field mapping suggestion |
| `POST` | `/analyze` | editor | Analyze file structure (columns, keys, types) |
| `GET` | `/export` | editor | Export entities to Excel (.xlsx) |

**POST /upload** — multipart form:

| Field | Type | Description |
|---|---|---|
| `file` | File | CSV, Excel, JSON, XML, Parquet, JSONLD, RDF, TTL, BibTeX, RIS |
| `domain` | string | Target domain ID (default: `"default"`) |
| `field_mapping` | JSON string | Custom column-to-field map from wizard |

Limits: 20 MB file size, 100,000 rows per upload. Returns HTTP 413 if exceeded.

**POST /upload/preview** — multipart: `file`. Returns `{ format, row_count, columns, sample_rows, auto_mapping, is_science_format }`.

**POST /upload/suggest-mapping** body:
```json
{ "columns": ["Title", "DOI", "Authors"], "sample_rows": [{...}] }
```
Returns `{ mapping: { "Title": "primary_label", ... }, provider, available }`.

**GET /export** query: `search` (filter string), `limit` (default 5000, max 50000). Returns Excel stream.

---

### Domains

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/domains` | viewer | List all domain schemas |
| `POST` | `/domains` | admin | Create custom domain schema |
| `GET` | `/domains/{id}` | viewer | Get single domain schema |
| `DELETE` | `/domains/{id}` | admin | Delete custom domain (403 for built-ins) |
| `GET` | `/olap/{domain_id}` | viewer | OLAP summary for a domain |
| `GET` | `/cube/dimensions/{domain_id}` | viewer | Available OLAP dimensions |
| `POST` | `/cube/query` | viewer | Cross-tab OLAP query (1–2 dimensions, filters, 200-row cap) |
| `GET` | `/cube/export/{domain_id}` | viewer | Export OLAP cube as Excel |

Built-in domains: `default`, `science`, `healthcare`. These cannot be deleted.

---

### Harmonization

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/harmonization/steps` | viewer | List available cleaning pipeline steps |
| `POST` | `/harmonization/preview/{step_id}` | editor | Preview step changes without applying |
| `POST` | `/harmonization/apply/{step_id}` | editor | Apply a specific harmonization step |
| `POST` | `/harmonization/apply-all` | editor | Apply all steps sequentially |
| `GET` | `/harmonization/logs` | viewer | Harmonization history log |
| `POST` | `/harmonization/undo/{log_id}` | editor | Undo a logged harmonization step |
| `POST` | `/harmonization/redo/{log_id}` | editor | Redo a reverted step |

Available step IDs: `normalize_labels`, `normalize_canonical_ids`, `normalize_entity_types`, `set_default_validation`, and others. Preview is capped at 10,000 rows.

---

### Disambiguation

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/disambiguate/{field}` | viewer | Find near-duplicate clusters for a field |
| `POST` | `/disambiguate/ai-resolve` | editor | AI-assisted canonical name resolution |
| `GET` | `/rules` | viewer | List normalization rules |
| `POST` | `/rules/bulk` | editor | Create rules in bulk |
| `DELETE` | `/rules/{id}` | editor | Delete a normalization rule |
| `POST` | `/rules/apply` | editor | Apply all active rules to entities |

**GET /disambiguate/{field}** query params:

| Param | Default | Options |
|---|---|---|
| `threshold` | 80 | 0–100 fuzzy match score |
| `algorithm` | `token_sort` | `token_sort`, `fingerprint`, `ngram`, `phonetic` |

**POST /disambiguate/ai-resolve** body:
```json
{ "field_name": "primary_label", "variations": ["Apple Inc", "Apple Incorporated"] }
```

---

### Authority

External authority linking against Wikidata, VIAF, ORCID, DBpedia, and OpenAlex.

| Method | Path | Min Role | Description |
|---|---|---|---|
| `POST` | `/authority/resolve` | editor | Resolve a value against external authorities |
| `POST` | `/authority/resolve/batch` | editor | Batch resolve multiple values |
| `GET` | `/authority/records` | viewer | List authority records (`?field_name=`, `?status=`) |
| `GET` | `/authority/queue/summary` | viewer | Queue summary counts by status |
| `POST` | `/authority/records/{id}/confirm` | editor | Confirm a candidate record |
| `POST` | `/authority/records/{id}/reject` | editor | Reject a candidate record |
| `POST` | `/authority/records/bulk-confirm` | editor | Bulk confirm pending records |
| `POST` | `/authority/records/bulk-reject` | editor | Bulk reject pending records |
| `DELETE` | `/authority/records/{id}` | editor | Delete an authority record |
| `GET` | `/authority/metrics` | viewer | Stats: total, by status, avg confidence |
| `GET` | `/authority/{field}` | viewer | Browse authority values for a field |

**POST /authority/resolve** body:
```json
{
  "field_name": "author",
  "original_value": "Einstein, Albert",
  "entity_type": "person",
  "context_affiliation": "Princeton IAS",
  "context_orcid_hint": "0000-0000-0000-0000"
}
```

Resolution statuses: `exact_match` (score ≥ 0.85), `probable_match` (≥ 0.65), `ambiguous` (≥ 0.45), `unresolved` (< 0.45).

---

### Analytics

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/stats` | viewer | Platform-wide entity statistics |
| `GET` | `/health` | public | Liveness + DB connectivity probe |
| `GET` | `/secondary-labels` | viewer | Secondary labels/facets with counts |
| `GET` | `/brands` | viewer | Legacy alias for `/secondary-labels` |
| `GET` | `/product-types` | viewer | Entity type distribution (legacy path name) |
| `GET` | `/classifications` | viewer | Classification distribution |
| `GET` | `/dashboard/summary` | viewer | Executive KPI dashboard for a domain |
| `GET` | `/dashboard/compare` | viewer | Side-by-side KPI comparison for 2–4 domains |
| `GET` | `/analyzers/topics/{domain_id}` | viewer | Top concepts by frequency |
| `GET` | `/analyzers/cooccurrence/{domain_id}` | viewer | Concept co-occurrence pairs with PMI score |
| `GET` | `/analyzers/clusters/{domain_id}` | viewer | Greedy concept clusters |
| `GET` | `/analyzers/correlation/{domain_id}` | viewer | Cramér's V pairwise field correlations |
| `POST` | `/analytics/roi` | viewer | Monte Carlo ROI projection |
| `POST` | `/analytics/cache/invalidate` | admin | Bust the in-memory analytics cache |

**GET /dashboard/summary** query: `domain_id` (default `"default"`).

Response includes: `kpis` (total entities, enrichment %, avg citations, concept count), `type_distribution`, `label_year_matrix` (plus legacy alias `brand_year_matrix`), `top_concepts`, `top_entities`, `quality`.

**GET /dashboard/compare** query: `domains=default,science` (comma-separated, 2–4 domains).

**GET /analyzers/topics/{domain_id}** query: `top_n` (default 30, max 100).

**GET /analyzers/cooccurrence/{domain_id}** query: `top_n` (default 20, max 100).

**GET /analyzers/clusters/{domain_id}** query: `n_clusters` (default 6, range 2–20).

**GET /analyzers/correlation/{domain_id}** query: `top_n` (default 20, max 50).

**POST /analytics/roi** body:
```json
{
  "investment": 1000000,
  "horizon_years": 5,
  "base_adoption_rate": 0.15,
  "adoption_volatility": 0.05,
  "revenue_per_unit": 50,
  "market_size": 100000,
  "annual_cost": 50000,
  "n_simulations": 2000
}
```

Analytics results are cached in memory: topic/correlation results have a 5-minute TTL; dashboard snapshots have a 2-minute TTL.

---

### AI & RAG

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/ai-integrations` | admin | List configured AI providers |
| `POST` | `/ai-integrations` | admin | Add AI provider (OpenAI, Anthropic, etc.) |
| `PUT` | `/ai-integrations/{id}` | admin | Update provider config |
| `POST` | `/ai-integrations/{id}/activate` | admin | Set as active provider (deactivates others) |
| `DELETE` | `/ai-integrations/{id}` | admin | Remove provider |
| `POST` | `/rag/index` | admin | Bulk index all enriched entities into ChromaDB |
| `POST` | `/rag/query` | viewer | Natural language query via ChromaDB + active LLM |
| `GET` | `/rag/stats` | viewer | ChromaDB vector index statistics |
| `DELETE` | `/rag/index` | admin | Clear entire vector index |

**POST /ai-integrations** body:
```json
{ "provider_name": "openai", "api_key": "sk-...", "model_name": "gpt-4o", "base_url": null }
```
API keys are encrypted at rest with Fernet symmetric encryption.

**POST /rag/query** body:

| Field | Default | Description |
|---|---|---|
| `question` | required | Query string (1–5000 chars) |
| `top_k` | 5 | Context chunks to retrieve (1–20) |
| `use_context` | false | Inject live domain context into system prompt |
| `domain_id` | null | Domain for context injection |
| `session_id` | null | Memory recall session ID (takes priority over domain context) |
| `use_tools` | false | Enable agentic tool-calling mode |

---

### Commerce Source Adapters

Commerce source adapters sync external platform records through the canonical entity model. These endpoints keep the historical `/stores` path for compatibility, but Shopify/WooCommerce-style concepts are adapter-specific rather than UKIP core model fields. Credentials are encrypted at rest. The frontend can hide this surface with `NEXT_PUBLIC_ENABLE_COMMERCE_ADAPTERS=false`.

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/stores` | admin | List all commerce source adapters |
| `POST` | `/stores` | admin | Create source adapter connection |
| `GET` | `/stores/stats/summary` | admin | Aggregated adapter stats |
| `GET` | `/stores/{id}` | admin | Get adapter details |
| `PUT` | `/stores/{id}` | admin | Update adapter config |
| `DELETE` | `/stores/{id}` | admin | Delete adapter and associated data |
| `POST` | `/stores/{id}/toggle` | admin | Toggle adapter active/inactive |
| `POST` | `/stores/{id}/test` | admin | Test adapter connection |
| `POST` | `/stores/{id}/pull` | admin | Pull records from remote source into review queue |
| `GET` | `/stores/{id}/mappings` | admin | List sync mappings for an adapter |
| `GET` | `/stores/{id}/queue` | admin | List sync queue items |
| `GET` | `/stores/{id}/logs` | admin | Sync operation logs |
| `POST` | `/stores/queue/{item_id}/approve` | admin | Approve a single queue item |
| `POST` | `/stores/queue/{item_id}/reject` | admin | Reject a single queue item |
| `POST` | `/stores/queue/bulk-approve` | admin | Approve all pending items for an adapter |
| `POST` | `/stores/queue/bulk-reject` | admin | Reject all pending items for an adapter |

**POST /stores** body:
```json
{
  "name": "My Shopify Adapter",
  "platform": "shopify",
  "base_url": "https://mystore.myshopify.com",
  "api_key": "...",
  "api_secret": "...",
  "access_token": "...",
  "sync_direction": "bidirectional"
}
```

`sync_direction` options: `"bidirectional"`, `"pull"`, `"push"`.

Queue item statuses: `pending`, `approved`, `rejected`. Attempting to approve/reject a non-pending item returns HTTP 409.

---

### Reports & Exports

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/reports/sections` | editor | List available report section IDs |
| `POST` | `/reports/generate` | editor | Generate self-contained HTML report |
| `POST` | `/exports/pdf` | editor | Export domain report as PDF (requires WeasyPrint) |
| `POST` | `/exports/excel` | editor | Export branded 4-sheet Excel workbook |

**POST /reports/generate** body:
```json
{
  "domain_id": "science",
  "sections": ["entity_stats", "enrichment_coverage", "top_secondary_labels"],
  "title": "My Report"
}
```

`top_brands` remains accepted as a backward-compatible report section alias, but `/reports/sections` exposes `top_secondary_labels` as the canonical section ID.

**POST /exports/excel** body: `{ domain_id, title }`. Returns `.xlsx` stream with sheets: Summary, Entities (up to 5,000), Concepts, Harmonization.

**POST /exports/pdf**: Returns PDF stream. Returns HTTP 501 if WeasyPrint is not installed.

---

### Annotations

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/annotations` | viewer | List annotations for an entity or authority record |
| `POST` | `/annotations` | editor | Create annotation |
| `GET` | `/annotations/{id}` | viewer | Get single annotation |
| `PUT` | `/annotations/{id}` | editor | Update annotation (own or admin) |
| `DELETE` | `/annotations/{id}` | editor | Delete annotation (own or admin) |

**GET /annotations** query: `entity_id`, `authority_id`.

**POST /annotations** body: `{ entity_id, authority_id, content, annotation_type }`.

---

### Webhooks

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/webhooks` | viewer | List all webhooks |
| `POST` | `/webhooks` | editor | Create outbound webhook |
| `GET` | `/webhooks/stats` | viewer | Webhook delivery statistics |
| `GET` | `/webhooks/{id}` | viewer | Get webhook details |
| `PUT` | `/webhooks/{id}` | editor | Update webhook config |
| `DELETE` | `/webhooks/{id}` | editor | Delete webhook |
| `POST` | `/webhooks/{id}/test` | editor | Send a test delivery |
| `GET` | `/webhooks/{id}/deliveries` | viewer | Delivery history for a webhook |
| `GET` | `/audit/feed` | viewer | Immutable audit log of all mutating operations |

**POST /webhooks** body:
```json
{ "url": "https://example.com/hook", "events": ["upload", "entity.merge", "entity.delete"] }
```

Supported webhook events include: `upload`, `entity.delete`, `entity.merge`, `entity.bulk_update`.

---

### Entity Linker

| Method | Path | Min Role | Description |
|---|---|---|---|
| `POST` | `/entities/link/find` | viewer | Detect duplicate entity candidates by fuzzy similarity |
| `POST` | `/entities/link/merge` | editor | Merge secondary entities into a primary |
| `POST` | `/entities/link/dismiss` | viewer | Dismiss a candidate pair from future suggestions |

**POST /entities/link/find** body:
```json
{ "threshold": 0.82, "limit": 500 }
```
`threshold` range: 0.50–0.99. `limit` range: 50–2000.

**POST /entities/link/merge** body:
```json
{ "primary_id": 1, "secondary_ids": [2, 3], "strategy": "keep_non_empty" }
```

---

### Notifications

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/notifications` | viewer | List in-app notifications for current user |
| `POST` | `/notifications/{id}/read` | viewer | Mark notification as read |
| `POST` | `/notifications/read-all` | viewer | Mark all notifications as read |
| `DELETE` | `/notifications/{id}` | viewer | Delete a notification |
| `GET` | `/notifications/settings` | viewer | Get per-user notification preferences |
| `PUT` | `/notifications/settings` | viewer | Update notification preferences |

---

### Scheduled Imports

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/scheduled-imports` | admin | List import schedules |
| `POST` | `/scheduled-imports` | admin | Create import schedule |
| `PUT` | `/scheduled-imports/{id}` | admin | Update schedule |
| `DELETE` | `/scheduled-imports/{id}` | admin | Delete schedule |
| `POST` | `/scheduled-imports/{id}/run` | admin | Trigger schedule immediately |

---

### Scheduled Reports

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/scheduled-reports` | admin | List report schedules |
| `POST` | `/scheduled-reports` | admin | Create schedule (cron expression + email delivery) |
| `PUT` | `/scheduled-reports/{id}` | admin | Update schedule |
| `DELETE` | `/scheduled-reports/{id}` | admin | Delete schedule |

---

### Dashboards

Per-user custom dashboards with drag-and-drop widget layout.

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/dashboards` | viewer | List current user's custom dashboards |
| `POST` | `/dashboards` | viewer | Create dashboard |
| `GET` | `/dashboards/{id}` | viewer | Get dashboard with widget layout |
| `PUT` | `/dashboards/{id}` | viewer | Update dashboard |
| `DELETE` | `/dashboards/{id}` | viewer | Delete dashboard |

---

### Alert Channels

Push notifications for platform events to Slack, Teams, Discord, or webhooks.

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/alert-channels` | admin | List configured alert channels |
| `POST` | `/alert-channels` | admin | Create alert channel |
| `PUT` | `/alert-channels/{id}` | admin | Update channel config |
| `DELETE` | `/alert-channels/{id}` | admin | Delete channel |
| `POST` | `/alert-channels/{id}/test` | admin | Send test alert |

---

### API Keys

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/api-keys` | viewer | List own API keys (prefix only, never full key) |
| `POST` | `/api-keys` | viewer | Create API key (full key shown **once**) |
| `DELETE` | `/api-keys/{id}` | viewer | Revoke API key |
| `GET` | `/api-keys/scopes` | viewer | List available scope definitions |

**POST /api-keys** body:
```json
{ "name": "CI Pipeline", "scopes": ["read", "write"], "expires_at": "2027-01-01T00:00:00Z" }
```

Available scopes: `read`, `write`, `admin`. Key format: `ukip_<40 chars>`.

---

### Search

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/search` | viewer | Full-text search across entities and annotations |

**GET /search** query: `q` (query string), `limit`, `skip`.

---

### Audit Log

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/audit/feed` | viewer | Paginated immutable audit log of all mutating API calls |

Query params: `skip`, `limit`, `action` (filter by event type), `user_id`.

---

### Demo Mode

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/demo/status` | viewer | Check demo mode status and entity count |
| `POST` | `/demo/seed` | admin | Seed 1,000 demo entities from bundled dataset |
| `DELETE` | `/demo/reset` | admin | Remove all demo-sourced entities |

Demo entities carry `source="demo"` and are cleanly isolated from user data.

---

### Branding

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/branding` | viewer | Get platform branding settings |
| `PUT` | `/branding` | admin | Update branding (logo, colours, name) |

---

### Artifacts

Report artifact storage with template library.

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/artifacts` | viewer | List stored report artifacts |
| `POST` | `/artifacts` | editor | Save a report artifact |
| `GET` | `/artifacts/templates` | viewer | List artifact templates |
| `GET` | `/artifacts/{id}` | viewer | Get single artifact |
| `DELETE` | `/artifacts/{id}` | editor | Delete artifact |

Built-in templates: Executive Summary, Research Analysis, Data Quality Audit, Full Report.

---

### Context & Memory

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/context/sessions` | viewer | List analysis context sessions |
| `POST` | `/context/sessions` | editor | Save an analysis context snapshot |
| `GET` | `/context/sessions/{id}` | viewer | Retrieve a context session |
| `DELETE` | `/context/sessions/{id}` | editor | Delete a context session |

Context sessions can be injected into RAG queries via `session_id` to provide memory recall.

---

### Quality

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/quality/report` | viewer | Data quality report for a domain |
| `POST` | `/quality/score` | editor | Trigger quality score recomputation |

---

### Relationships & Graph

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/relationships` | viewer | List entity relationships |
| `POST` | `/relationships` | editor | Create relationship between entities |
| `DELETE` | `/relationships/{id}` | editor | Delete relationship |
| `GET` | `/graph/export` | viewer | Export entity relationship graph (JSON or GraphML) |

---

### Natural Language Query (NLQ)

| Method | Path | Min Role | Description |
|---|---|---|---|
| `POST` | `/nlq/query` | viewer | Translate natural language to structured entity filter |

---

### Workflows

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/workflows` | viewer | List defined workflows |
| `POST` | `/workflows` | admin | Create automation workflow |
| `PUT` | `/workflows/{id}` | admin | Update workflow |
| `DELETE` | `/workflows/{id}` | admin | Delete workflow |
| `POST` | `/workflows/{id}/run` | editor | Trigger workflow manually |

---

### Scrapers

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/scrapers` | admin | List configured web scrapers |
| `POST` | `/scrapers` | admin | Create scraper config |
| `PUT` | `/scrapers/{id}` | admin | Update scraper |
| `DELETE` | `/scrapers/{id}` | admin | Delete scraper |
| `POST` | `/scrapers/{id}/run` | admin | Run scraper immediately |

---

### Transformations

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/transformations` | viewer | List field transformation rules |
| `POST` | `/transformations` | editor | Create transformation rule |
| `PUT` | `/transformations/{id}` | editor | Update transformation |
| `DELETE` | `/transformations/{id}` | editor | Delete transformation |
| `POST` | `/transformations/apply` | editor | Apply all transformations |

---

### Organizations & Onboarding

| Method | Path | Min Role | Description |
|---|---|---|---|
| `GET` | `/organizations` | admin | List organizations |
| `POST` | `/organizations` | super_admin | Create organization |
| `GET` | `/onboarding/status` | viewer | Current user onboarding checklist status |
| `POST` | `/onboarding/complete/{step}` | viewer | Mark an onboarding step complete |

---

## Common HTTP Status Codes

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Bad request or validation failure |
| 401 | Unauthenticated — missing or invalid token |
| 403 | Insufficient role |
| 404 | Resource not found |
| 409 | Conflict (duplicate or already resolved) |
| 413 | Payload too large (file > 20 MB or > 100k rows) |
| 422 | Unprocessable entity (schema validation error) |
| 423 | Account locked (too many failed login attempts) |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 501 | Feature not available (e.g., WeasyPrint not installed) |
| 502 | Upstream store or API connection failed |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ADMIN_USERNAME` | Yes | Bootstrap super_admin username |
| `ADMIN_PASSWORD` | Yes (first boot) | Bootstrap super_admin plaintext password |
| `JWT_SECRET_KEY` | Yes | Secret for JWT signing |
| `ENCRYPTION_KEY` | Yes | Fernet key for credential encryption |
| `ALLOWED_ORIGINS` | No | CORS origins, comma-separated (default: `localhost:3004,localhost:3000`) |
| `SESSION_SECRET_KEY` | No | Cookie session secret (falls back to `JWT_SECRET_KEY`) |
| `SSO_CLIENT_ID` | No | OAuth2 client ID for SSO |
| `SSO_CLIENT_SECRET` | No | OAuth2 client secret |
| `SSO_METADATA_URL` | No | OIDC well-known URL (default: Google) |
| `FRONTEND_URL` | No | Frontend base URL for SSO redirect (default: `http://localhost:3000`) |
| `DATABASE_URL` | No | SQLAlchemy DB URL (default: `sqlite:///./sql_app.db`) |
| `NEXT_PUBLIC_API_URL` | No | Frontend env: backend base URL |
