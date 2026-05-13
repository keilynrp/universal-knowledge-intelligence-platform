## ADDED Requirements

### Requirement: Live OpenAlex demo seed with offline fallback
The `POST /demo/seed` endpoint SHALL first attempt a live OpenAlex query (`concept.id: C41008148`, limit 1,000). On failure (network unavailable, rate limit, timeout) it SHALL fall back to a bundled JSON snapshot at `data/demo/openalex_snapshot.json`.

#### Scenario: Connected environment seed
- **WHEN** `POST /demo/seed` is called and the OpenAlex API is reachable
- **THEN** the endpoint queries OpenAlex for concept `C41008148` (knowledge management) with limit 1,000
- **THEN** results are ingested via `_ingest_records()` with `source="demo"` and `domain="science"`
- **THEN** the endpoint returns `{"seeded": <n>, "source": "openalex_live"}`

#### Scenario: Offline fallback seed
- **WHEN** `POST /demo/seed` is called and the OpenAlex API is unreachable (network error or timeout)
- **THEN** the endpoint loads `data/demo/openalex_snapshot.json` and ingests those records
- **THEN** the endpoint returns `{"seeded": <n>, "source": "openalex_snapshot"}`

#### Scenario: Snapshot file present in repo
- **WHEN** the repository is cloned fresh
- **THEN** `data/demo/openalex_snapshot.json` exists and contains at least 100 valid records (title, authors, year)

#### Scenario: Idempotent re-seed
- **WHEN** `POST /demo/seed` is called a second time
- **THEN** existing demo records (source="demo") are cleared before inserting new ones (no duplicates)

### Requirement: Snapshot generation script
The repository SHALL include `scripts/generate_openalex_snapshot.py` that fetches up to 1,000 records from OpenAlex (concept C41008148) and writes them to `data/demo/openalex_snapshot.json` in a format consumable by the fallback path.

#### Scenario: Script generates valid snapshot
- **WHEN** `python scripts/generate_openalex_snapshot.py` is run with network access
- **THEN** `data/demo/openalex_snapshot.json` is created with a list of record objects each containing `title`, `authors`, `year`, `doi`, `abstract`, `citation_count`, `concepts`, `affiliations`

#### Scenario: Script is safe to re-run
- **WHEN** the script is run again
- **THEN** it overwrites the existing snapshot file without error
