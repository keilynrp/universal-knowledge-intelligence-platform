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
- `pull_works.py` — API puller for the targeted subset.

## Default subset (day one)

270 scored journals (ISSN-L from `journal_metrics`) × **2010–2025**, citations off.
Estimated ~10⁴–10⁵ works ≈ a few hundred MB DuckDB.

```bash
# polite pool (free) — set a contact e-mail; a premium key lifts rate limits
export OPENALEX_MAILTO="you@example.org"
# export OPENALEX_API_KEY="..."           # optional, faster
export OPENALEX_LAKE_DB="data/openalex_lake.duckdb"

python -m backend.openalex_lake.pull_works                 # full pull
python -m backend.openalex_lake.pull_works --incremental   # only works updated since last run
python -m backend.openalex_lake.pull_works --include-citations   # add the reference graph (heavy)
```

## Cross-source joins (in DuckDB)

`dim_source.issn_l` ↔ app `journal_metrics.issn_l` · `fact_works.doi` ↔
`raw_entities.enrichment_doi` · `dim_author.orcid` / `dim_institution.ror` ↔ your
author/institution tables.

## Scaling to the full corpus (when storage allows)

1. **Dimensions** — one-time + monthly:
   ```bash
   aws s3 sync s3://openalex/data/sources     ./snap/sources     --no-sign-request
   aws s3 sync s3://openalex/data/institutions ./snap/institutions --no-sign-request
   aws s3 sync s3://openalex/data/topics       ./snap/topics       --no-sign-request
   # then COPY the gz JSONL into dim_* via DuckDB read_json_auto()
   ```
2. **Works** — either keep the API path with a widened scope (e.g. by field +
   year) or, for the whole corpus, stream the works snapshot through
   `transform_work` + `LakeStore` (same code, snapshot reader instead of API).

## Automated periodic updates

The puller is watermark-driven (`_meta.works` holds the last successful run
date), so `--incremental` is safe to schedule. Recommended: an external cron /
Dokploy scheduled job, e.g. monthly:

```
0 3 1 * *  cd /app && python -m backend.openalex_lake.pull_works --incremental
```

(OpenAlex refreshes the snapshot ~monthly; incremental API pulls can run more
often.) Deletions/merges are handled on the snapshot path via `merged_ids`.
