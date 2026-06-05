# EPIC-012 Tenant Isolation — Deploy Runbook

Operational steps to run **after deploying** the tenant-isolation work
(PRs #30, #33, #35 — closes issues #31, #32). The code is merged to `main`;
these are data/operational actions that cannot be done in code.

Run them **in order**. Steps 1 and 2 are required for correct behavior; step 3
is a data-hygiene check.

---

## 1. Re-index ChromaDB (REQUIRED — do this first)

**Why:** Before #32, indexed vector documents had no `org_id` in their
metadata. After #32 the RAG retrieval path filters by `org_id`, so any document
missing that key is excluded from org-scoped queries. **Until re-indexed, RAG /
agentic-chat returns empty results for every org-scoped user** — the assistant
will look broken for tenants.

**Action** — on a host with access to the production DB and ChromaDB volume:

```bash
# Preview: counts eligible entities + per-org distribution, touches nothing.
python -m scripts.reindex_chromadb_org_scope --dry-run

# Re-index (upserts org_id into every enriched entity's vector metadata).
python -m scripts.reindex_chromadb_org_scope

# Optional: drop stale documents (entities deleted since last index) first.
python -m scripts.reindex_chromadb_org_scope --wipe
```

**Prerequisites:**
- `DATABASE_URL` (or `POSTGRES_*`) points at the target DB.
- An **active** AI integration is configured (Integrations → AI Language Models) —
  it provides the embedding adapter. Without it the script exits with code 2.
- `chromadb` installed; `CHROMADB_PATH` writable.

**Idempotent:** documents upsert by `entity-<id>`, so it is safe to re-run.

**Verify:** after it completes, run an agentic-chat / `POST /rag/query` as a user
with an active org and confirm sources come back (non-empty). Legacy-global
entities (no org) are stored with the `-1` sentinel and remain visible only to
legacy-global scope.

---

## 2. Re-assign pre-existing `alert_channels` (if any)

**Why:** `AlertChannel` has no owner column, so the EPIC-012 migration could not
derive a tenant for rows created before the change — they were intentionally
left `org_id = NULL` (legacy-global scope). New channels created via the API are
stamped with the creator's org automatically; only **pre-existing** rows need
attention.

**Action:**

```sql
-- 1. List channels with no tenant.
SELECT id, name, type FROM alert_channels WHERE org_id IS NULL;
```

- If the result is empty → nothing to do.
- Otherwise, for each channel an admin either:
  - re-creates it from within the owning organization (re-encrypts the webhook
    and stamps the org), **or**
  - runs a one-off update by someone who knows the correct owner:
    ```sql
    UPDATE alert_channels SET org_id = <org> WHERE id = <id>;
    ```

Leaving them `NULL` is acceptable: they stay visible only under legacy-global
scope (users with no active org).

---

## 3. Manual cross-org spot-check

**Why:** CI proves the change doesn't break; it does not prove isolation holds
end-to-end. Do a quick manual pass on a multi-tenant environment.

**Checklist** — with two users in different orgs (A and B):

- [ ] User B requesting an A-owned record by id on the scoped surfaces
      (annotations, dashboards, widgets, alert_channels, artifact templates,
      context sessions) returns **404**, not the record.
- [ ] List endpoints for B never include A's rows.
- [ ] `GET /context/snapshot/{domain}` and the executive/gap stats reflect only
      the caller's org (entity counts differ between A and B).
- [ ] Agentic chat / `POST /rag/query` as user A never surfaces B's catalog
      documents or tool results (run after step 1's re-index).
- [ ] A user who belongs to two orgs switching active org cannot reach a
      dashboard created in the other org.

If any check leaks cross-org data, **stop and escalate** — do not treat it as a
minor issue.

---

## References

- PRs: #30 (Wave 2-3 closure), #33 (GapAnalyzer scope), #35 (agentic tenant context)
- Issues: #31, #32 (both closed)
- Helper module: `backend/tenant_access.py`
- Re-index script: `scripts/reindex_chromadb_org_scope.py`
