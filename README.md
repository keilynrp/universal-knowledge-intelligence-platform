# UKIP

Universal Knowledge Intelligence Platform.

UKIP is a FastAPI + Next.js platform for importing, normalizing, enriching, exploring, and reporting on knowledge datasets. The current product focus is research intelligence: publication portfolios, authors, affiliations, concepts, citations, semantic signals, graph relationships, and executive reporting.

The project is an advanced product prototype moving toward a production-ready platform. Some areas are already usable; others are intentionally being hardened through specs and regression-control work.

## What Works Today

- Import structured datasets through CSV, Excel, BibTeX, RIS, scientific API import flows, and connector-oriented ingestion paths.
- Store records as universal entities with domain, entity type, canonical ID, labels, raw attributes, enrichment fields, quality score, and provenance.
- Enrich scientific records with metadata from OpenAlex and optional BYOK/provider integrations such as Crossref, PubMed, Web of Science, Scopus, Semantic Scholar, and controlled Scholar fallback paths.
- Explore entities through list and detail views, including normalized metadata, enrichment status, quality, semantic keyword signals, and local graph context.
- Build graph relationships from bibliometric and semantic evidence: authorship, venue, concepts, same-as, related-to, co-word, semantic-neighbor, derived-keyword, external-signal-for, and emerging-from.
- Review dashboards for home, executive analytics, graph visualization, topic signals, OLAP, reports, catalogs, and operational status.
- Use RAG and agentic research features over indexed records, with active work around index freshness and evidence quality.
- Generate reports and artifacts, including executive-style summaries and export-oriented delivery flows.
- Run backend tests in CI across Python 3.11 and 3.12, plus PostgreSQL migration smoke checks.

## Areas Being Hardened

These areas are intentionally tracked as technical debt because they have caused recurring regressions:

- A single domain-scope contract for `all`, concrete domains, and historical default records.
- Derived data freshness for enrichment, graph, semantic signals, RAG index, dashboard snapshots, and report readiness.
- A canonical entity metadata view so DOI, entity type, affiliation, abstract, authors, journal, year, and keywords are not deduplicated differently per screen.
- Read-model extraction for executive dashboard and graph modules.
- Workflow regression tests that cover authentication, domain switching, enrichment, graph materialization, dashboard updates, semantic signals, and entity detail metadata.
- Documentation cleanup so README, specs, and product docs describe the real system without historical noise.

The source of truth for this hardening plan is:

- [system-hardening-and-regression-control](openspec/specs/system-hardening-and-regression-control/spec.md)

## Architecture

```text
backend/      FastAPI API, SQLAlchemy models, routers, services, enrichment, graph, analytics, RAG
frontend/     Next.js app router, React UI, contexts, dashboards, graph views, entity detail screens
alembic/      Database migrations
openspec/     Capability specs and future planning contracts
docs/         Product, architecture, operating, and roadmap documentation
scripts/      Local utility scripts
docker/       Deployment helpers
```

Important backend modules:

- `backend/models.py`: ORM models for entities, relationships, users, organizations, reports, notifications, and derived resources.
- `backend/routers/`: HTTP API routes.
- `backend/services/analytics_service.py`: dashboard and analytics read logic.
- `backend/services/graph_materializer.py`: graph relationship materialization.
- `backend/services/semantic_keyword_signal_engine.py`: semantic keyword and opportunity signal generation.
- `backend/enrichment_worker.py`: enrichment processing and downstream materialization hooks.

Important frontend modules:

- `frontend/app/contexts/DomainContext.tsx`: active domain state.
- `frontend/app/page.tsx`: home dashboard.
- `frontend/app/analytics/dashboard/page.tsx`: executive dashboard.
- `frontend/app/analytics/graph/page.tsx`: graph visualization.
- `frontend/app/entities/[id]/page.tsx`: entity detail view.

## Specs

Current active specs live in `openspec/specs`.

Key specs:

- [system-hardening-and-regression-control](openspec/specs/system-hardening-and-regression-control/spec.md)
- [bibliometric-graph-engine](openspec/specs/bibliometric-graph-engine/spec.md)
- [semantic-keyword-signal-engine](openspec/specs/semantic-keyword-signal-engine/spec.md)
- [enrichment-progress-tracking](openspec/specs/enrichment-progress-tracking/spec.md)
- [enrichment-failure-details](openspec/specs/enrichment-failure-details/spec.md)
- [epistemic-analytics-ui](openspec/specs/epistemic-analytics-ui/spec.md)
- [epistemic-classification-engine](openspec/specs/epistemic-classification-engine/spec.md)
- [concept-tree-materialization](openspec/specs/concept-tree-materialization/spec.md)
- [concept-hierarchy-ui](openspec/specs/concept-hierarchy-ui/spec.md)

Archived change proposals live in `openspec/changes/archive`.

## Local Setup

Python 3.11 or 3.12 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -c requirements.lock
```

Frontend:

```powershell
cd frontend
npm install
```

Copy environment values from `.env.example` or `.env.dokploy.example` as needed.

For local SQLite compatibility:

```powershell
$env:UKIP_DB_MODE="sqlite"
$env:DATABASE_URL="sqlite:///./sql_app.db"
```

For PostgreSQL-first development, configure:

```powershell
$env:UKIP_DB_MODE="postgres"
$env:DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/ukip"
```

## Running

Backend:

```powershell
uvicorn backend.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm run dev
```

The frontend defaults to port `3004`.

## Testing

Backend:

```powershell
pytest backend/tests -q
```

Backend with coverage:

```powershell
pytest backend/tests --tb=short --cov=backend --cov-report=term-missing -q
```

Frontend type check:

```powershell
cd frontend
npm exec tsc -- --noEmit --pretty false
```

Frontend unit tests:

```powershell
cd frontend
npm test
```

Frontend E2E:

```powershell
cd frontend
npm run e2e
```

## Deployment Notes

- PostgreSQL is the preferred production database path.
- SQLite remains useful for small local scenarios and test compatibility.
- Background enrichment and scheduled jobs currently run in-process; external job orchestration is part of the hardening roadmap.
- Sentry/telemetry is opt-in and should be enabled explicitly in deployed environments.
- Google Scholar fallback should remain disabled by default unless the operational risk is understood.

## Documentation Map

- [Architecture](docs/ARCHITECTURE.md)
- [API notes](API.md)
- [Operating docs](docs/operating/README.md)
- [Product docs](docs/product/README.md)
- [System evaluation](docs/ukip_system_evaluation.md)
- [Enterprise roadmap](docs/UKIP_ENTERPRISE_ROADMAP.md)

## License

Apache 2.0. See [LICENSE](LICENSE).
