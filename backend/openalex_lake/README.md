# OpenAlex analytical lake

A controlled, filtered ingestion of **OpenAlex** (CC0 / public domain) into a
persistent **DuckDB** star schema for historical + cross-source scientometric
analysis. Legal note: the OpenAlex release is CC0 — download, cross, and reuse
freely; only attribution is courteous. Third-party enrichment you *add* keeps
its own terms.

## Why this shape

The `works` snapshot is partitioned by `updated_date`, **not** by year/field, so
"give me field X, 2010-2025" against the snapshot means streaming all ~250M
works. To stay controlled we take a **hybrid** approach:

| Layer | Source | Rationale |
|-------|--------|-----------|
| Works (fact) | **API**, server-side filtered + cursor paging | pulls only the subset — no 300 GB download |
| Dimensions (sources, institutions, topics…) | **S3 snapshot** (`--no-sign-request`) | small; loaded full once, then monthly |
| Authors (dim) | **derived** from works' authorships | the full authors entity (~90M) is never needed |

Widening to the **full corpus** later is a config change, not a rewrite: relax
`LakeScope` (drop the ISSN filter) and/or set `works_source="snapshot"`. The
`transform` + `store` stay identical.

## Modules

- `config.py` — `LakeScope` (what to ingest) + `LakeSettings` (db path, mailto, api key).
- `schema.py` — DuckDB DDL (fact_works, fact_authorship, fact_work_topic, fact_citation, dim_*).
- `transform.py` — pure `transform_work(work) -> rows` (fully unit-tested).
- `store.py` — idempotent DuckDB upsert + incremental watermark.
- `pull_works.py` — API puller for the targeted subset (works / fact tables).
- `sync_dimensions.py` — S3-snapshot loader for the dimensions (sources, institutions, topics).
- `views.py` — DuckDB analysis views for the 4 axes (auto-registered by the store).
- `status.py` — operational snapshot (watermark, counts, coverage) to verify scheduled runs.

## Default subset (day one)

270 scored journals (ISSN-L from `journal_metrics`) × **2010–2025**, citations off.
Estimated ~10⁴–10⁵ works ≈ a few hundred MB DuckDB.

```bash
# polite pool (free) — set a contact e-mail; a premium key lifts rate limits
export OPENALEX_MAILTO="you@example.org"
# export OPENALEX_API_KEY="..."           # optional, faster
export OPENALEX_LAKE_DB="data/openalex_lake.duckdb"

python -m backend.openalex_lake.pull_works --issn 0028-0836 --limit 5   # any env: pass ISSNs directly (no journal_metrics needed)
python -m backend.openalex_lake.pull_works --issn-file journals.txt     # one ISSN-L per line
python -m backend.openalex_lake.pull_works --limit 25      # smoke test: ~25 real works, prints a table summary, no watermark advance
python -m backend.openalex_lake.pull_works                 # full pull
python -m backend.openalex_lake.pull_works --incremental   # only works updated since last run
python -m backend.openalex_lake.pull_works --include-citations   # add the reference graph (heavy)
```

## Analysis views (the 4 axes)

`store.py` auto-registers DuckDB views over the star schema (in `views.py`), so
they stay in sync with the facts and cost nothing until queried:

| Axis | Views |
|------|-------|
| Journal scientometrics | `v_journal_yearly`, `v_journal_citation_trend` |
| Collaboration networks | `v_coauthor_pairs`, `v_institution_collab` |
| Topic trends | `v_topic_yearly`, `v_field_yearly` |
| Coverage / cross-source | `v_source_coverage`, `v_work_keys` |

```sql
-- journals ranked by output in 2020
SELECT issn_l, works, citations FROM v_journal_yearly
WHERE publication_year = 2020 ORDER BY works DESC LIMIT 20;
```

## Cross-source joins (in DuckDB)

`dim_source.issn_l` ↔ app `journal_metrics.issn_l` · `fact_works.doi` ↔
`raw_entities.enrichment_doi` · `dim_author.orcid` / `dim_institution.ror` ↔ your
author/institution tables.

To join the lake against the app's SQLite/Postgres directly, ATTACH it:

```sql
INSTALL sqlite; LOAD sqlite;
ATTACH 'sql_app.db' AS app (TYPE SQLITE);
-- coverage of our scored journals in the lake
SELECT jm.issn_l, jm.display_name, cov.works, cov.first_year, cov.last_year
FROM app.journal_metrics jm
LEFT JOIN v_source_coverage cov ON cov.issn_l = jm.issn_l;
```

## Scaling to the full corpus (when storage allows)

1. **Dimensions** — one-time + monthly, via `sync_dimensions.py`:
   ```bash
   # download from the public bucket AND load into dim_* (needs aws-cli + storage)
   python -m backend.openalex_lake.sync_dimensions --download
   # or load already-synced parts from a local dir
   python -m backend.openalex_lake.sync_dimensions --snapshot-dir ./data/openalex-snapshot
   ```
   It streams the gzipped JSON-Lines parts through the pure dimension transforms
   into `dim_source` / `dim_institution` / `dim_topic` (idempotent upsert).
2. **Works** — either keep the API path with a widened scope (e.g. by field +
   year) or, for the whole corpus, stream the works snapshot through
   `transform_work` + `LakeStore` (same code, snapshot reader instead of API).

## Performance notes

- **Bulk insert**: rows are buffered across works and written with a vectorized
  `INSERT OR REPLACE ... SELECT * FROM <df>` (deduped by PK). Measured on 600
  Nature works this cut the DB write from **226 s → 0.8 s** (~280×); the pull is
  now fetch-bound.
- **`select=`** trims each page from ~8.9 MB to ~4.6 MB (only the fields the
  transform reads).
- **Always set `OPENALEX_MAILTO`** — the polite pool is far less throttled than
  the anonymous common pool; without it, sustained pagination hits 429 backoffs.
- At ~80–90 works/s (polite pool) the first full subset pull is a multi-hour,
  one-time batch; `--incremental` afterwards is cheap.

## Automated periodic updates (Dokploy)

The puller is watermark-driven (`_meta.works` holds the last successful run
date), so `--incremental` is safe to schedule. The persistence is already wired
in `docker-compose.prod.yml`: the `ukip_openalex_lake` volume is mounted at
`/data` on `ukip-backend` and `OPENALEX_LAKE_DB=/data/openalex_lake.duckdb`, so
the file and its watermark survive redeploys. Remaining steps:

**1. Set the polite-pool contact** (Dokploy → Environment). Reuses the existing
`OPENALEX_EMAIL` (the anonymous pool is heavily throttled):

```
OPENALEX_EMAIL=ops@inbounduxd.com
```

**2. First full pull (one-time).** Fetch-bound, so it runs for a while — do it
once in the running backend container (Dokploy → Terminal, or a one-off
Schedule). ISSNs come from `journal_metrics` (self-maintaining as journals are
added):

```
python -m backend.openalex_lake.pull_works
```

**3. Monthly incremental (the schedule).** Dokploy → app → Schedules → new
schedule on the `ukip-backend` service, cron `0 3 1 * *`, command:

```
python -m backend.openalex_lake.pull_works --incremental
```

Overlap is safe: DuckDB is single-writer, so a second concurrent run simply
fails to open the file and exits (logged) rather than corrupting anything.

**Verify a run:** `python -m backend.openalex_lake.status` prints the watermark,
per-table counts, journal coverage and year span (read-only, safe while the job
holds the file).

OpenAlex refreshes the snapshot ~monthly; incremental API pulls can run more
often. Deletions/merges are handled on the snapshot path via `merged_ids`.
