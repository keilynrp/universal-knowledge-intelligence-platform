"""
UKIP — Universal Knowledge Intelligence Platform
FastAPI application entry point (slim orchestrator).

All domain logic lives in backend/routers/*.py
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import inspect, text

from backend import database, enrichment_worker, models
from backend.routers.limiter import limiter

# ── Domain routers ────────────────────────────────────────────────────────────
from backend.routers import (
    ai_rag,
    analytics,
    annotations,
    auth_users,
    authority,
    branding,
    demo,
    disambiguation,
    domains,
    entities,
    harmonization,
    ingest,
    notifications,
    reports,
    stores,
    webhooks,
)

logger = logging.getLogger(__name__)


# ── Schema creation + lightweight migrations ──────────────────────────────────

models.Base.metadata.create_all(bind=database.engine)

with database.engine.connect() as _conn:
    _inspector = inspect(database.engine)

    if "harmonization_logs" in _inspector.get_table_names():
        _cols = [c["name"] for c in _inspector.get_columns("harmonization_logs")]
        if "reverted" not in _cols:
            _conn.execute(text("ALTER TABLE harmonization_logs ADD COLUMN reverted BOOLEAN DEFAULT 0"))
            _conn.commit()

    if "raw_entities" in _inspector.get_table_names():
        _cols = [c["name"] for c in _inspector.get_columns("raw_entities")]
        if "enrichment_doi" not in _cols:
            _conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_doi VARCHAR"))
            _conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_citation_count INTEGER DEFAULT 0"))
            _conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_concepts TEXT"))
            _conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_source VARCHAR"))
            _conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_status VARCHAR DEFAULT 'none'"))
            _conn.commit()

    if "users" in _inspector.get_table_names():
        _cols = [c["name"] for c in _inspector.get_columns("users")]
        if "failed_attempts" not in _cols:
            _conn.execute(text("ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0"))
            _conn.execute(text("ALTER TABLE users ADD COLUMN locked_until VARCHAR"))
            _conn.commit()

    if "authority_records" in _inspector.get_table_names():
        _cols = [c["name"] for c in _inspector.get_columns("authority_records")]
        if "resolution_status" not in _cols:
            _conn.execute(text("ALTER TABLE authority_records ADD COLUMN resolution_status VARCHAR DEFAULT 'unresolved'"))
            _conn.execute(text("ALTER TABLE authority_records ADD COLUMN score_breakdown TEXT"))
            _conn.execute(text("ALTER TABLE authority_records ADD COLUMN evidence TEXT"))
            _conn.execute(text("ALTER TABLE authority_records ADD COLUMN merged_sources TEXT"))
            _conn.commit()

    if "raw_entities" in _inspector.get_table_names():
        _cols = [c["name"] for c in _inspector.get_columns("raw_entities")]
        if "source" not in _cols:
            _conn.execute(text("ALTER TABLE raw_entities ADD COLUMN source VARCHAR DEFAULT 'user'"))
            _conn.commit()


# ── Lifespan ──────────────────────────────────────────────────────────────────

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

    def get_db_gen():
        while True:
            db = database.SessionLocal()
            try:
                yield db
            finally:
                db.close()

    asyncio.create_task(enrichment_worker.background_enrichment_worker(get_db_gen()))

    yield  # Server is running


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="UKIP — Universal Knowledge Intelligence Platform",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

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

# ── Register routers ──────────────────────────────────────────────────────────

app.include_router(auth_users.router)
app.include_router(ingest.router)
app.include_router(domains.router)
app.include_router(analytics.router)
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
