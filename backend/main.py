"""
UKIP — Universal Knowledge Intelligence Platform
FastAPI application entry point (slim orchestrator).

All domain logic lives in backend/routers/*.py
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend import database, enrichment_worker, models
from backend.routers.limiter import limiter

# ── Domain routers ────────────────────────────────────────────────────────────
from backend.routers import (
    ai_rag,
    alert_channels,
    analytics,
    annotations,
    api_keys,
    artifacts,
    audit_log,
    auth_users,
    authority,
    branding,
    context,
    dashboards,
    demo,
    disambiguation,
    domains,
    entities,
    entity_linker,
    graph_export,
    harmonization,
    ingest,
    nlq,
    notifications,
    organizations,
    scheduled_reports,
    quality,
    relationships,
    reports,
    sales_deck,
    scheduled_imports,
    scrapers,
    search,
    stores,
    transformations,
    webhooks,
    onboarding,
    widgets,
    workflows,
    ws,
)

logger = logging.getLogger(__name__)


# ── Schema migrations via Alembic ─────────────────────────────────────────────

def _run_migrations() -> None:
    """Run alembic upgrade head at startup. Idempotent and safe to call every boot."""
    from alembic import command
    from alembic.config import Config as AlembicConfig

    alembic_cfg = AlembicConfig("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    logger.info("Alembic migrations applied (upgrade head)")

_run_migrations()


# ── Lifespan ──────────────────────────────────────────────────────────────────

_BUILTIN_TEMPLATES = [
    {
        "name": "Executive Summary",
        "sections": '["entity_stats","enrichment_coverage","top_brands"]',
        "description": "KPIs + enrichment coverage + top brands for decision-makers",
        "default_title": "Executive Summary Report",
    },
    {
        "name": "Research Analysis",
        "sections": '["topic_clusters","enrichment_coverage","entity_stats"]',
        "description": "Concept clusters + semantic coverage for researchers",
        "default_title": "Research Analysis Report",
    },
    {
        "name": "Data Quality Audit",
        "sections": '["entity_stats","harmonization_log","enrichment_coverage"]',
        "description": "Validation status + harmonization trail + enrichment",
        "default_title": "Data Quality Audit Report",
    },
    {
        "name": "Full Report",
        "sections": '["entity_stats","enrichment_coverage","top_brands","topic_clusters","harmonization_log"]',
        "description": "All sections combined — comprehensive view",
        "default_title": "Full Platform Report",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    with database.SessionLocal() as db:
        enrichment_worker.reset_stale_processing_records(db)

        if db.query(models.User).count() == 0:
            from backend.auth import hash_password as _hash_pw
            bootstrap_user = models.User(
                username=os.environ.get("ADMIN_USERNAME", "admin"),
                password_hash=_hash_pw(os.environ.get("ADMIN_PASSWORD", "changeit")),
                role="super_admin",
                is_active=True,
            )
            db.add(bootstrap_user)
            db.commit()
            logger.info("Bootstrap: super_admin '%s' created", bootstrap_user.username)

        # Seed built-in artifact templates (only on first run)
        if db.query(models.ArtifactTemplate).count() == 0:
            import json as _json
            for t in _BUILTIN_TEMPLATES:
                db.add(models.ArtifactTemplate(
                    name=t["name"],
                    description=t["description"],
                    sections=t["sections"],
                    default_title=t["default_title"],
                    is_builtin=True,
                ))
            db.commit()
            logger.info("Bootstrap: %d built-in artifact templates seeded", len(_BUILTIN_TEMPLATES))

    def get_db_gen():
        while True:
            db = database.SessionLocal()
            try:
                yield db
            finally:
                db.close()

    asyncio.create_task(enrichment_worker.background_enrichment_worker(get_db_gen()))

    # Start the scheduled-imports scheduler (Sprint 61)
    scheduled_imports.start_scheduler()
    # Start the scheduled-reports scheduler (Sprint 79)
    scheduled_reports.start_scheduler()

    yield  # Server is running


# ── App ───────────────────────────────────────────────────────────────────────

_OPENAPI_DESCRIPTION = """
## Universal Knowledge Intelligence Platform

UKIP is a multi-domain knowledge management and enrichment platform.
It ingests structured data (CSV, Excel, BibTeX, RIS), harmonises and
de-duplicates records, enriches them via external academic APIs, and
exposes analytics, reporting, and RAG-based AI search.

### Authentication
All protected endpoints use **Bearer JWT** tokens.
Obtain a token via `POST /auth/token` (OAuth2 password flow), then click
**Authorize** above and paste the token.

### Rate limiting
Login endpoint: **5 requests / minute** per IP.

### Roles
| Role | Description |
|---|---|
| `viewer` | Read-only access to entities and analytics |
| `editor` | Upload, edit entities, manage rules |
| `admin` | Store integrations, AI config, RAG indexing |
| `super_admin` | User management + all admin rights |
"""

_OPENAPI_TAGS = [
    {"name": "auth",           "description": "Login, token refresh, and SSO."},
    {"name": "users",          "description": "User management and profile (RBAC)."},
    {"name": "entities",       "description": "Entity CRUD, search, enrichment, and Monte-Carlo scoring."},
    {"name": "ingestion",      "description": "File upload (CSV, Excel, BibTeX, RIS), analysis, and export."},
    {"name": "domains",        "description": "Domain registry, schema management, and OLAP cube."},
    {"name": "harmonization",  "description": "Multi-step data-cleaning pipeline with undo/redo."},
    {"name": "disambiguation", "description": "Cluster detection, AI resolution, and normalization rules."},
    {"name": "authority",      "description": "External authority linking (Wikidata, VIAF, ORCID, DBpedia, OpenAlex)."},
    {"name": "analytics",      "description": "KPI dashboard, domain comparison, topic modeling, and OLAP."},
    {"name": "ai-rag",         "description": "AI integrations (OpenAI / Anthropic) and RAG vector search."},
    {"name": "stores",         "description": "Store connector configuration and sync queue."},
    {"name": "reports",        "description": "Report builder, PDF/Excel exports, and artifact templates."},
    {"name": "annotations",    "description": "Free-form entity annotations and notes."},
    {"name": "webhooks",       "description": "Outbound webhook subscriptions and delivery logs."},
    {"name": "notifications",  "description": "In-app notification centre and per-user settings."},
    {"name": "scheduled-imports",  "description": "Cron-style import schedules for connected stores."},
    {"name": "scheduled-reports",  "description": "Cron-style report schedules with email delivery."},
    {"name": "dashboards",         "description": "Per-user custom dashboards with drag-and-drop widget layout."},
    {"name": "alert-channels",     "description": "Slack/Teams/Discord/webhook push notifications for platform events."},
    {"name": "api-keys",           "description": "Long-lived API keys for programmatic access with scope control."},
    {"name": "search",         "description": "Full-text search index (FTS5) across entities and annotations."},
    {"name": "entity-linker",  "description": "Find and merge duplicate entity pairs."},
    {"name": "audit",          "description": "Immutable audit log of all mutating API calls."},
    {"name": "branding",       "description": "Platform branding and white-label settings."},
    {"name": "context",        "description": "Contextual intelligence snippets for entities."},
    {"name": "artifacts",      "description": "Report artifact storage and template library."},
    {"name": "demo",           "description": "Demo-mode seed/reset for sandboxed evaluation."},
    {"name": "sso",            "description": "OAuth2 / SAML single-sign-on flows."},
    {"name": "exports",        "description": "One-click PDF and Excel exports."},
]

app = FastAPI(
    title="UKIP — Universal Knowledge Intelligence Platform",
    version="1.0.0",
    description=_OPENAPI_DESCRIPTION,
    contact={"name": "UKIP Team", "url": "https://github.com/ukip"},
    license_info={"name": "MIT"},
    openapi_tags=_OPENAPI_TAGS,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "tryItOutEnabled": False,
        "displayRequestDuration": True,
        "filter": True,
        "syntaxHighlight.theme": "monokai",
    },
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

from backend.audit import AuditMiddleware  # noqa: E402 — after app init
app.add_middleware(AuditMiddleware)

_cors_origins_env = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3004,http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["X-Total-Count"],
)

from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SESSION_SECRET_KEY", os.environ.get("JWT_SECRET_KEY", "fallback_cookie_secret")),
    max_age=3600
)

# ── Register routers ──────────────────────────────────────────────────────────

app.include_router(auth_users.router)
app.include_router(ingest.router)
app.include_router(domains.router)
app.include_router(analytics.router)
app.include_router(quality.router)
app.include_router(entities.router)
app.include_router(disambiguation.router)
app.include_router(harmonization.router)
app.include_router(authority.router)
app.include_router(stores.router)
app.include_router(ai_rag.router)
app.include_router(reports.router)
app.include_router(webhooks.router)
app.include_router(demo.router)
app.include_router(annotations.router)
app.include_router(notifications.router)
app.include_router(branding.router)
app.include_router(artifacts.router)
app.include_router(context.router)
app.include_router(audit_log.router)
app.include_router(search.router)
app.include_router(entity_linker.router)
app.include_router(scheduled_imports.router)
app.include_router(relationships.router)
app.include_router(graph_export.router)
app.include_router(nlq.router)
app.include_router(scheduled_reports.router)
app.include_router(dashboards.router)
app.include_router(alert_channels.router)
app.include_router(api_keys.router)
app.include_router(sales_deck.router)
app.include_router(organizations.router)
app.include_router(transformations.router)
app.include_router(scrapers.router)
app.include_router(onboarding.router)
app.include_router(widgets.router)
app.include_router(workflows.router)
app.include_router(ws.router)

# ── Static file serving (uploaded logos etc.) ─────────────────────────────────
_static_dir = pathlib.Path("static")
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
