import asyncio
import io
import json
import logging
import math
import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Path, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text, func, or_, update
from sqlalchemy.orm import Session
from thefuzz import process, fuzz

from backend import models, schemas, database, enrichment_worker
from backend.database import get_db
from backend.adapters import get_adapter
from backend.analytics import rag_engine
from backend.analytics.montecarlo import simulate_citation_impact
from backend.analytics.vector_store import VectorStoreService
from backend.auth import authenticate_user, create_access_token, get_current_user, require_role
from backend.authority.resolver import resolve_all as _authority_resolve_all
from backend.authority.base import ResolveContext as _AuthorityContext
from backend.datasource_analyzer import DataSourceAnalyzer
from backend.encryption import encrypt, decrypt
from backend.llm_agent import resolve_canonical_name
from backend.analyzers.topic_modeling import TopicAnalyzer
from backend.analyzers.correlation import CorrelationAnalyzer
from backend.olap import olap_engine
from backend.schema_registry import registry, DomainSchema

_topic_analyzer = TopicAnalyzer()
_correlation_analyzer = CorrelationAnalyzer()

logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=database.engine)

# Lightweight migration: add columns introduced after initial schema creation
with database.engine.connect() as conn:
    inspector = inspect(database.engine)
    if "harmonization_logs" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("harmonization_logs")]
        if "reverted" not in columns:
            conn.execute(text("ALTER TABLE harmonization_logs ADD COLUMN reverted BOOLEAN DEFAULT 0"))
            conn.commit()

    if "raw_entities" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("raw_entities")]
        if "enrichment_doi" not in columns:
            conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_doi VARCHAR"))
            conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_citation_count INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_concepts TEXT"))
            conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_source VARCHAR"))
            conn.execute(text("ALTER TABLE raw_entities ADD COLUMN enrichment_status VARCHAR DEFAULT 'none'"))
            conn.commit()

    if "users" in inspector.get_table_names():
        user_cols = [col["name"] for col in inspector.get_columns("users")]
        if "failed_attempts" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE users ADD COLUMN locked_until VARCHAR"))
            conn.commit()

    if "authority_records" in inspector.get_table_names():
        ar_cols = [col["name"] for col in inspector.get_columns("authority_records")]
        if "resolution_status" not in ar_cols:
            conn.execute(text("ALTER TABLE authority_records ADD COLUMN resolution_status VARCHAR DEFAULT 'unresolved'"))
            conn.execute(text("ALTER TABLE authority_records ADD COLUMN score_breakdown TEXT"))
            conn.execute(text("ALTER TABLE authority_records ADD COLUMN evidence TEXT"))
            conn.execute(text("ALTER TABLE authority_records ADD COLUMN merged_sources TEXT"))
            conn.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    with database.SessionLocal() as db:
        # Reset stale "processing" records from a previous crashed session
        enrichment_worker.reset_stale_processing_records(db)

        # Bootstrap: auto-create super_admin from env vars if no users exist
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
                db.close()  # Safety net: worker also closes explicitly each iteration

    asyncio.create_task(enrichment_worker.background_enrichment_worker(get_db_gen()))

    yield  # Server is running
    # ── Shutdown (nothing to clean up currently) ──────────────────────────────


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan)
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

# ── Authentication ─────────────────────────────────────────────────────────

@app.post("/auth/token", tags=["auth"])
@limiter.limit("5/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Obtain a Bearer token. Credentials are managed in the users table.
    Rate-limited to 5 attempts per minute per IP.
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user.username, role=user.role)
    return {"access_token": token, "token_type": "bearer"}


# ── User Management (RBAC) ─────────────────────────────────────────────────

@app.get("/users/me", response_model=schemas.UserResponse, tags=["users"])
def get_my_profile(current_user: models.User = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return current_user


@app.post("/users/me/password", tags=["users"])
def change_my_password(
    payload: schemas.PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Change the authenticated user's own password."""
    from backend.auth import verify_password, hash_password as _hp
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = _hp(payload.new_password)
    db.commit()
    return {"message": "Password updated successfully"}


@app.get("/users", response_model=List[schemas.UserResponse], tags=["users"])
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin")),
):
    """List all users. Requires super_admin."""
    return db.query(models.User).offset(skip).limit(limit).all()


@app.post("/users", response_model=schemas.UserResponse, status_code=201, tags=["users"])
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin")),
):
    """Create a new user. Requires super_admin."""
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    from backend.auth import hash_password as _hash_pw
    new_user = models.User(
        username=payload.username,
        email=payload.email,
        password_hash=_hash_pw(payload.password),
        role=payload.role.value,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/users/{user_id}", response_model=schemas.UserResponse, tags=["users"])
def get_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin")),
):
    """Get a user by ID. Requires super_admin."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/users/{user_id}", response_model=schemas.UserResponse, tags=["users"])
def update_user(
    user_id: int = Path(..., ge=1),
    payload: schemas.UserUpdate = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin")),
):
    """Update a user's email, password, role, or active status. Requires super_admin."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Prevent self-role change
    if user.id == current_user.id and payload.role is not None and payload.role.value != current_user.role:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    # Prevent deactivating self
    if user.id == current_user.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    # Ensure at least one super_admin remains active
    if payload.role is not None and user.role == "super_admin" and payload.role.value != "super_admin":
        active_superadmins = db.query(models.User).filter(
            models.User.role == "super_admin", models.User.is_active == True
        ).count()
        if active_superadmins <= 1:
            raise HTTPException(status_code=400, detail="Cannot demote the last active super_admin")

    update_data = payload.model_dump(exclude_unset=True)
    if "password" in update_data:
        from backend.auth import hash_password as _hash_pw
        update_data["password_hash"] = _hash_pw(update_data.pop("password"))
    if "role" in update_data:
        update_data["role"] = update_data["role"].value if hasattr(update_data["role"], "value") else update_data["role"]

    for field, value in update_data.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@app.delete("/users/{user_id}", tags=["users"])
def delete_user(
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin")),
):
    """Soft-delete (deactivate) a user. Requires super_admin."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    # Ensure at least one super_admin remains active
    if user.role == "super_admin":
        active_superadmins = db.query(models.User).filter(
            models.User.role == "super_admin", models.User.is_active == True
        ).count()
        if active_superadmins <= 1:
            raise HTTPException(status_code=400, detail="Cannot deactivate the last active super_admin")
    user.is_active = False
    db.commit()
    return {"message": "User deactivated", "id": user_id}


COLUMN_MAPPING = {
    "Nombre del Producto": "entity_name",
    "Clasificación": "classification",
    "Tipo de Producto": "entity_type",
    "¿Posible vender en cantidad decimal?": "is_decimal_sellable",
    "¿Controlarás el stock del producto?": "control_stock",
    "Estado": "status",
    "Impuestos": "taxes",
    "Variante": "variant",
    "Código universal de producto": "entity_code_universal_1",
    "Codigo universal": "entity_code_universal_2",
    "Codigo universal del producto": "entity_code_universal_3",
    "CODIGO UNIVERSAL DEL PRODRUCTO ": "entity_code_universal_4", 
    "marca": "brand_lower",
    "Marca": "brand_capitalized",
    "modelo": "model",
    "GTIN": "gtin",
    "Motivo de GTIN": "gtin_reason",
    "Motivo de GTIN vacío": "gtin_empty_reason_1",
    "Motivo GTIN vacío ": "gtin_empty_reason_2",
    "Motivo GTIN vacia": "gtin_empty_reason_3",
    "Motivo GTIN de producto": "gtin_entity_reason",
    "motivo GTIN": "gtin_reason_lower",
    "Mtivo GTIN vacio": "gtin_empty_reason_typo",
    "EQUIMAPIENTO": "equipment",
    "MEDIDA": "measure",
    "TIPO DE UNION": "union_type",
    "¿permitirás ventas sin stock?": "allow_sales_without_stock",
    "Código de Barras": "barcode",
    "SKU": "sku",
    "Sucursales": "branches",
    "Fecha de creacion": "creation_date",
    "Estado Variante": "variant_status",
    "Clave de producto": "entity_key",
    "Unidad de medida": "unit_of_measure"
}

@app.post("/upload", status_code=201)
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    _MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

    filename = file.filename.lower()
    allowed_extensions = (".xlsx", ".csv", ".json", ".xml", ".parquet", ".jsonld", ".rdf", ".ttl")
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail=f"Invalid file format. Allowed: {', '.join(allowed_extensions)}")

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is 20 MB (received {len(contents) // (1024*1024)} MB).",
        )
    records = []
    
    try:
        if filename.endswith(".xlsx"):
            df = pd.read_excel(io.BytesIO(contents))
            records = df.to_dict("records")
        elif filename.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(contents), encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(contents), encoding='latin-1')
            records = df.to_dict("records")
        elif filename.endswith(".parquet"):
            df = pd.read_parquet(io.BytesIO(contents))
            records = df.to_dict("records")
        elif filename.endswith(".json") or filename.endswith(".jsonld"):
            data = json.loads(contents.decode("utf-8"))
            if isinstance(data, dict):
                # If root is dict, either single record or we unwrap the first list
                list_data = next((v for v in data.values() if isinstance(v, list)), [data])
                records = list_data
            elif isinstance(data, list):
                records = data
        elif filename.endswith(".xml"):
            root = ET.fromstring(contents.decode("utf-8"))
            for child in root:
                record = {}
                for subchild in child:
                    record[subchild.tag] = subchild.text
                if record:
                    records.append(record)
        elif filename.endswith(".rdf") or filename.endswith(".ttl"):
            import rdflib
            g = rdflib.Graph()
            format_type = "ttl" if filename.endswith(".ttl") else "xml"
            g.parse(data=contents.decode("utf-8"), format=format_type)
            
            # Very basic RDF to flat dict transformation grouped by subject
            entities = {}
            for s, p, o in g:
                subj = str(s)
                pred = str(p).split("/")[-1].split("#")[-1]
                obj = str(o)
                if subj not in entities:
                    entities[subj] = {"entity_key": subj}
                if pred in entities[subj]:
                    entities[subj][pred] += f"; {obj}"
                else:
                    entities[subj][pred] = obj
            records = list(entities.values())
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process file: {str(e)}")

    if not records:
        return {"message": "No valid data found or file is empty", "total_rows": 0, "matched_columns": [], "unmatched_columns": []}

    _MAX_ROWS = 100_000
    if len(records) > _MAX_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"File contains too many rows ({len(records):,}). Maximum allowed is {_MAX_ROWS:,} rows per upload.",
        )

    # Gather all unique keys from records
    all_keys = set()
    for row in records[:100]:
        if isinstance(row, dict):
            all_keys.update(row.keys())

    stripped_mapping = {k.strip(): v for k, v in COLUMN_MAPPING.items()}
    valid_model_keys = set(COLUMN_MAPPING.values())

    matched_columns = set()
    unmatched_columns = set()
    for col in all_keys:
        col_str = str(col).strip()
        if col_str in stripped_mapping or col_str in valid_model_keys:
            matched_columns.add(col_str)
        else:
            unmatched_columns.add(col_str)

    objects = []
    for row in records:
        if not isinstance(row, dict):
            continue
            
        row_data = {}
        unmatched_data = {}
        
        for k, val in row.items():
            # Check for NaN correctly
            is_nan = False
            if type(val) is float and math.isnan(val):
                is_nan = True
            elif pd.isna(val) if hasattr(pd, "isna") else False:
                # Handle Pandas NaT / NA
                try:
                    if pd.isna(val): is_nan = True
                except (TypeError, ValueError):
                    pass

            if is_nan:
                val = None
                
            sk = str(k).strip()
            
            if sk in stripped_mapping:
                model_field = stripped_mapping[sk]
                row_data[model_field] = str(val) if val is not None else None
            elif sk in valid_model_keys:
                row_data[sk] = str(val) if val is not None else None
            else:
                unmatched_data[sk] = val

        if unmatched_data:
            # Safely serialize using default=str to avoid datetime/NaN crash
            row_data["normalized_json"] = json.dumps(unmatched_data, default=str, ensure_ascii=False)

        objects.append(models.RawEntity(**row_data))

    _CHUNK_SIZE = 10_000
    for i in range(0, len(objects), _CHUNK_SIZE):
        db.bulk_save_objects(objects[i : i + _CHUNK_SIZE])
    db.commit()

    return {
        "message": f"Successfully imported {len(objects)} entities",
        "total_rows": len(objects),
        "matched_columns": list(matched_columns),
        "unmatched_columns": list(unmatched_columns),
    }


@app.post("/analyze")
async def analyze_datasource(file: UploadFile = File(...), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    """
    Analyzes the structure (columns, keys, tags, predicates) of a given file.
    Supports CSV, Excel, JSON, XML, Parquet, RDF, Logs, etc.
    """
    # Create a temporary file preserving the extension since DataSourceAnalyzer relies on it
    ext = os.path.splitext(file.filename)[1].lower()
    if not ext:
        raise HTTPException(status_code=400, detail="File must have an extension to be analyzed")

    fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd) # Close file descriptor so we can open it via shutil

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Run analyzer
        structure = DataSourceAnalyzer.analyze(temp_path)
        
        return {
            "filename": file.filename,
            "format": ext.strip("."),
            "structure": structure,
            "count": len(structure)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error analyzing file '%s'", file.filename)
        raise HTTPException(status_code=500, detail="Error analyzing file. Check server logs for details.")
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/domains", response_model=List[DomainSchema])
def get_domains(_: models.User = Depends(get_current_user)):
    """Returns all available domain schemas in the registry."""
    return registry.get_all_domains()

@app.post("/domains", response_model=DomainSchema, status_code=201)
def create_domain(
    schema: DomainSchema,
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Create a new custom domain schema. Persists as YAML in backend/domains/."""
    if registry.get_domain(schema.id):
        raise HTTPException(status_code=409, detail="A domain with this ID already exists")
    if not schema.attributes:
        raise HTTPException(status_code=422, detail="Domain must have at least one attribute")
    try:
        registry.save_domain(schema)
    except Exception as exc:
        logger.exception("Failed to save domain schema '%s'", schema.id)
        raise HTTPException(status_code=500, detail="Failed to persist domain schema") from exc
    return schema

@app.delete("/domains/{domain_id}")
def delete_domain(
    domain_id: str,
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Delete a custom domain schema. Built-in domains (default, science, healthcare) are protected."""
    if registry.is_builtin(domain_id):
        raise HTTPException(status_code=403, detail="Built-in domains cannot be deleted")
    if not registry.delete_domain(domain_id):
        raise HTTPException(status_code=404, detail="Domain schema not found")
    return {"deleted": domain_id}

@app.get("/domains/{domain_id}", response_model=DomainSchema)
def get_domain(domain_id: str, _: models.User = Depends(get_current_user)):
    domain = registry.get_domain(domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain schema not found")
    return domain

@app.get("/olap/{domain_id}")
def get_olap_cube(domain_id: str, _: models.User = Depends(get_current_user)):
    """
    Returns DuckDB OLAP distributions and multidimensional slice metrics for the given domain schema.
    """
    try:
        cube = olap_engine.generate_cube_metrics(domain_id)
        return cube
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("OLAP error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="OLAP processing error. Check server logs for details.")


# ── OLAP Cube Explorer endpoints ─────────────────────────────────────────────

class _CubeQueryPayload(BaseModel):
    domain_id: str = Field(min_length=1, max_length=64)
    group_by: List[str] = Field(min_length=1, max_length=2)
    filters: dict = {}


@app.get("/cube/dimensions/{domain_id}")
def cube_dimensions(domain_id: str, _: models.User = Depends(get_current_user)):
    """
    Returns the list of groupable dimensions for a domain with distinct-value counts.
    Used by the OLAP Cube Explorer dimension selector.
    """
    try:
        return olap_engine.get_dimensions(domain_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("cube_dimensions error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="OLAP error")


@app.post("/cube/query")
def cube_query(
    payload: _CubeQueryPayload,
    _: models.User = Depends(get_current_user),
):
    """
    GROUP BY query against the domain data cube.
    Accepts 1 or 2 dimensions and optional equality filters.
    """
    try:
        return olap_engine.query_cube(payload.domain_id, payload.group_by, payload.filters or None)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("cube_query error")
        raise HTTPException(status_code=500, detail="OLAP query error")


@app.get("/cube/export/{domain_id}")
def cube_export(
    domain_id: str,
    dimension: str = Query(min_length=1, max_length=64),
    _: models.User = Depends(get_current_user),
):
    """Export a single-dimension GROUP BY as an Excel (.xlsx) file."""
    try:
        xlsx_bytes = olap_engine.export_to_excel(domain_id, dimension)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("cube_export error for domain '%s', dimension '%s'", domain_id, dimension)
        raise HTTPException(status_code=500, detail="Export error")

    return StreamingResponse(
        iter([xlsx_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="cube_{domain_id}_{dimension}.xlsx"'},
    )

# ── Topic Modeling & Correlation endpoints ───────────────────────────────────

@app.get("/analyzers/topics/{domain_id}")
def analyzer_topics(
    domain_id: str,
    top_n: int = Query(default=30, ge=1, le=100),
    _: models.User = Depends(get_current_user),
):
    """Top concepts by frequency across enriched entities in a domain."""
    try:
        return _topic_analyzer.top_topics(domain_id, top_n=top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_topics error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@app.get("/analyzers/cooccurrence/{domain_id}")
def analyzer_cooccurrence(
    domain_id: str,
    top_n: int = Query(default=20, ge=1, le=100),
    _: models.User = Depends(get_current_user),
):
    """Concept co-occurrence pairs with PMI score."""
    try:
        return _topic_analyzer.cooccurrence(domain_id, top_n=top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_cooccurrence error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@app.get("/analyzers/clusters/{domain_id}")
def analyzer_clusters(
    domain_id: str,
    n_clusters: int = Query(default=6, ge=2, le=20),
    _: models.User = Depends(get_current_user),
):
    """Greedy concept clusters seeded by top concepts."""
    try:
        return _topic_analyzer.topic_clusters(domain_id, n_clusters=n_clusters)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_clusters error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@app.get("/analyzers/correlation/{domain_id}")
def analyzer_correlation(
    domain_id: str,
    top_n: int = Query(default=20, ge=1, le=50),
    _: models.User = Depends(get_current_user),
):
    """Cramér's V pairwise field correlations for categorical columns in a domain."""
    try:
        return _correlation_analyzer.top_correlations(domain_id, top_n=top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("analyzer_correlation error for domain '%s'", domain_id)
        raise HTTPException(status_code=500, detail="Analysis error")


@app.get("/entities", response_model=List[schemas.Entity])
def get_entities(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    search: str = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    query = db.query(models.RawEntity)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                models.RawEntity.entity_name.ilike(search_filter),
                models.RawEntity.brand_capitalized.ilike(search_filter),
                models.RawEntity.model.ilike(search_filter),
                models.RawEntity.sku.ilike(search_filter)
            )
        )

    total = query.count()
    entities = query.offset(skip).limit(limit).all()

    response.headers["X-Total-Count"] = str(total)
    return entities


@app.get("/entities/grouped")
def get_entities_grouped(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    search: str = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """
    Group products by entity_name and show all variants for each product.
    Similar to OpenRefine's clustering/faceting feature.
    """
    # Subquery to count variants per entity_name
    variant_counts = db.query(
        models.RawEntity.entity_name,
        func.count(models.RawEntity.id).label("variant_count")
    ).filter(
        models.RawEntity.entity_name != None
    ).group_by(models.RawEntity.entity_name).subquery()
    
    # Main query
    query = db.query(
        models.RawEntity.entity_name,
        variant_counts.c.variant_count
    ).join(
        variant_counts,
        models.RawEntity.entity_name == variant_counts.c.entity_name
    ).group_by(
        models.RawEntity.entity_name,
        variant_counts.c.variant_count
    )
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(models.RawEntity.entity_name.ilike(search_filter))
    
    # Order by variant count descending (products with most variants first)
    query = query.order_by(variant_counts.c.variant_count.desc())

    # Total distinct entity names (for pagination UI)
    total_groups = query.count()
    response.headers["X-Total-Count"] = str(total_groups)

    # Paginate
    product_groups = query.offset(skip).limit(limit).all()

    # Single query to fetch all variants for the current page in one round-trip
    entity_names = [row[0] for row in product_groups]
    if not entity_names:
        return []

    all_variants = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.entity_name.in_(entity_names))
        .all()
    )

    # Group variants by entity_name in Python (O(N) instead of N DB round-trips)
    variants_by_name: dict[str, list] = defaultdict(list)
    for v in all_variants:
        variants_by_name[v.entity_name].append(v)

    return [
        {
            "entity_name": entity_name,
            "variant_count": variant_count,
            "variants": variants_by_name.get(entity_name, []),
        }
        for entity_name, variant_count in product_groups
    ]


@app.get("/entities/{entity_id}", response_model=schemas.Entity)
def get_entity(
    entity_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@app.put("/entities/{entity_id}", response_model=schemas.Entity)
def update_entity(entity_id: int = Path(..., ge=1), payload: schemas.EntityBase = ..., db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entity, field, value)

    db.commit()
    db.refresh(entity)
    return entity




class _BulkIdsPayload(BaseModel):
    ids: List[int] = Field(..., min_length=1, max_length=500)


@app.delete("/entities/bulk", status_code=200)
def delete_entities_bulk(
    payload: _BulkIdsPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Delete a specific list of entities by id."""
    if not payload.ids:
        raise HTTPException(status_code=422, detail="ids list is empty")
    deleted = db.query(models.RawEntity).filter(models.RawEntity.id.in_(payload.ids)).delete(synchronize_session=False)
    db.commit()
    return {"deleted": deleted}


@app.delete("/entities/all")
def purge_all_entities(include_rules: bool = Query(False), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    entity_count = db.query(func.count(models.RawEntity.id)).scalar() or 0
    db.query(models.RawEntity).delete()

    rules_count = 0
    if include_rules:
        rules_count = db.query(func.count(models.NormalizationRule.id)).scalar() or 0
        db.query(models.NormalizationRule).delete()

    db.commit()
    return {
        "message": "Repository purged successfully",
        "entities_deleted": entity_count,
        "rules_deleted": rules_count,
    }


@app.delete("/entities/{entity_id}")
def delete_entity(entity_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    db.delete(entity)
    db.commit()
    return {"message": "Entity deleted", "id": entity_id}


@app.post("/enrich/row/{entity_id}", response_model=schemas.Entity)
def enrich_single_entity(entity_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    """Enriches a single row manually (e.g. from a UI click)"""
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Force single enrichment fetch
    enriched = enrichment_worker.enrich_single_record(db, entity)
    return enriched

@app.post("/enrich/bulk")
def enrich_bulk_queue(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    """Queues missing records for background enrichment"""
    count = enrichment_worker.trigger_enrichment_bulk(db, skip=skip, limit=limit)
    return {"message": "Bulk queue triggered", "queued_records": count}


@app.post("/enrich/bulk-ids", status_code=200)
def enrich_bulk_by_ids(
    payload: _BulkIdsPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Queue a specific list of entities for background enrichment."""
    updated = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.id.in_(payload.ids))
        .update({"enrichment_status": "pending"}, synchronize_session=False)
    )
    db.commit()
    return {"queued": updated}


@app.get("/enrich/stats")
def get_enrichment_stats(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    """Returns enrichment statistics for the predictive analytics dashboard."""
    total = db.query(func.count(models.RawEntity.id)).scalar() or 0

    # Status breakdown
    status_rows = db.query(
        models.RawEntity.enrichment_status,
        func.count(models.RawEntity.id)
    ).group_by(models.RawEntity.enrichment_status).all()
    status_breakdown = {row[0] or "none": row[1] for row in status_rows}

    enriched_count = status_breakdown.get("completed", 0)
    pending_count = status_breakdown.get("pending", 0)
    failed_count = status_breakdown.get("failed", 0)
    none_count = status_breakdown.get("none", 0)

    # Top concepts — parse comma-separated concepts from enrichment_concepts column
    enriched_entities = db.query(models.RawEntity.enrichment_concepts).filter(
        models.RawEntity.enrichment_concepts != None,
        models.RawEntity.enrichment_concepts != ""
    ).all()

    concept_freq: dict = {}
    for row in enriched_entities:
        if row[0]:
            for concept in row[0].split(","):
                concept = concept.strip()
                if concept:
                    concept_freq[concept] = concept_freq.get(concept, 0) + 1

    top_concepts = sorted(concept_freq.items(), key=lambda x: x[1], reverse=True)[:20]

    # Citation statistics
    citation_rows = db.query(models.RawEntity.enrichment_citation_count).filter(
        models.RawEntity.enrichment_status == "completed",
        models.RawEntity.enrichment_citation_count != None,
        models.RawEntity.enrichment_citation_count > 0
    ).all()
    citation_values = [r[0] for r in citation_rows if r[0]]

    avg_citations = round(sum(citation_values) / len(citation_values), 1) if citation_values else 0
    max_citations = max(citation_values) if citation_values else 0
    total_citations = sum(citation_values)

    # Citation distribution buckets
    buckets = {"0": 0, "1-10": 0, "11-50": 0, "51-200": 0, "200+": 0}
    for v in citation_values:
        if v == 0:
            buckets["0"] += 1
        elif v <= 10:
            buckets["1-10"] += 1
        elif v <= 50:
            buckets["11-50"] += 1
        elif v <= 200:
            buckets["51-200"] += 1
        else:
            buckets["200+"] += 1

    return {
        "total_entities": total,
        "enriched_count": enriched_count,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "none_count": none_count,
        "enrichment_coverage_pct": round((enriched_count / total * 100), 1) if total > 0 else 0,
        "top_concepts": [{"concept": c, "count": n} for c, n in top_concepts],
        "citations": {
            "average": avg_citations,
            "max": max_citations,
            "total": total_citations,
            "distribution": buckets,
        },
    }

@app.get("/enrich/montecarlo/{entity_id}")
def get_montecarlo_prediction(entity_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    """
    Phase 4: Performs a stochastic Monte Carlo simulation on the future citation trajectory
    of a single enriched entity, provided the entity has citations.
    """
    entity = db.query(models.RawEntity).filter(models.RawEntity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    if entity.enrichment_status != "completed":
        raise HTTPException(status_code=400, detail="Cannot predict raw or unenriched data")
        
    citations = entity.enrichment_citation_count or 0
    predictions = simulate_citation_impact(
        current_citations=citations, 
        simulation_years=5, 
        num_simulations=5000
    )
    
    return predictions

@app.get("/disambiguate/{field}")
def disambiguate_field(field: str, threshold: int = Query(default=80, ge=0, le=100), db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    try:
        groups = _build_disambig_groups(field, threshold, db)
        return {"groups": groups, "total_groups": len(groups)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class AIResolveRequest(BaseModel):
    field_name: str
    variations: List[str]
    api_key: Optional[str] = None

@app.post("/disambiguate/ai-resolve")
def ai_resolve_variations(payload: AIResolveRequest, _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    """
    Sends a cluster of lexical variations to the LLM agent to figure out the canonical name 
    and provide ontological reasoning.
    """
    try:
        # Pass to the LLM Agent
        resolution = resolve_canonical_name(
            field_name=payload.field_name, 
            variations=payload.variations,
            api_key=payload.api_key
        )
        return resolution
    except Exception as e:
        logger.exception("LLM AI-resolve error for field '%s'", payload.field_name)
        raise HTTPException(status_code=500, detail="AI resolution failed. Check server logs for details.")

@app.get("/stats")
def get_stats(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    total_entities = db.query(func.count(models.RawEntity.id)).scalar() or 0

    unique_brands = db.query(func.count(func.distinct(models.RawEntity.brand_capitalized))).filter(
        models.RawEntity.brand_capitalized != None
    ).scalar() or 0

    unique_models = db.query(func.count(func.distinct(models.RawEntity.model))).filter(
        models.RawEntity.model != None
    ).scalar() or 0

    unique_entity_types = db.query(func.count(func.distinct(models.RawEntity.entity_type))).filter(
        models.RawEntity.entity_type != None
    ).scalar() or 0

    # Validation status breakdown
    validation_rows = db.query(
        models.RawEntity.validation_status,
        func.count(models.RawEntity.id)
    ).group_by(models.RawEntity.validation_status).all()
    validation_status = {row[0] or "pending": row[1] for row in validation_rows}

    # Identifier coverage
    with_sku = db.query(func.count(models.RawEntity.id)).filter(
        models.RawEntity.sku != None, models.RawEntity.sku != ""
    ).scalar() or 0
    with_barcode = db.query(func.count(models.RawEntity.id)).filter(
        models.RawEntity.barcode != None, models.RawEntity.barcode != ""
    ).scalar() or 0
    with_gtin = db.query(func.count(models.RawEntity.id)).filter(
        models.RawEntity.gtin != None, models.RawEntity.gtin != ""
    ).scalar() or 0

    # Top brands (top 10)
    top_brands = db.query(
        models.RawEntity.brand_capitalized,
        func.count(models.RawEntity.id).label("count")
    ).filter(
        models.RawEntity.brand_capitalized != None
    ).group_by(
        models.RawEntity.brand_capitalized
    ).order_by(func.count(models.RawEntity.id).desc()).limit(10).all()

    # Product type distribution
    type_distribution = db.query(
        models.RawEntity.entity_type,
        func.count(models.RawEntity.id).label("count")
    ).filter(
        models.RawEntity.entity_type != None
    ).group_by(
        models.RawEntity.entity_type
    ).order_by(func.count(models.RawEntity.id).desc()).limit(10).all()

    # Status distribution
    status_distribution = db.query(
        models.RawEntity.status,
        func.count(models.RawEntity.id).label("count")
    ).filter(
        models.RawEntity.status != None
    ).group_by(
        models.RawEntity.status
    ).order_by(func.count(models.RawEntity.id).desc()).all()

    # Classification distribution
    classification_distribution = db.query(
        models.RawEntity.classification,
        func.count(models.RawEntity.id).label("count")
    ).filter(
        models.RawEntity.classification != None
    ).group_by(
        models.RawEntity.classification
    ).order_by(func.count(models.RawEntity.id).desc()).all()

    
    # Variant statistics
    products_with_variants = db.query(func.count(models.RawEntity.id)).filter(
        models.RawEntity.variant != None,
        models.RawEntity.variant != ""
    ).scalar() or 0
    
    # Count unique product names that have variants
    unique_products_with_variants = db.query(
        func.count(func.distinct(models.RawEntity.entity_name))
    ).filter(
        models.RawEntity.variant != None,
        models.RawEntity.variant != "",
        models.RawEntity.entity_name != None
    ).scalar() or 0

    return {
        "total_entities": total_entities,
        "unique_brands": unique_brands,
        "unique_models": unique_models,
        "unique_entity_types": unique_entity_types,
        "entities_with_variants": products_with_variants,
        "unique_entities_with_variants": unique_products_with_variants,
        "validation_status": validation_status,
        "identifier_coverage": {
            "with_sku": with_sku,
            "with_barcode": with_barcode,
            "with_gtin": with_gtin,
            "total": total_entities,
        },
        "top_brands": [{"name": b[0], "count": b[1]} for b in top_brands],
        "type_distribution": [{"name": t[0], "count": t[1]} for t in type_distribution],
        "classification_distribution": [{"name": c[0], "count": c[1]} for c in classification_distribution],
        "status_distribution": [{"name": s[0], "count": s[1]} for s in status_distribution],
    }


@app.get("/brands")
def get_all_brands(limit: int = Query(default=200, ge=1, le=1000), db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    brands = db.query(
        models.RawEntity.brand_capitalized,
        func.count(models.RawEntity.id).label("count")
    ).filter(
        models.RawEntity.brand_capitalized != None
    ).group_by(
        models.RawEntity.brand_capitalized
    ).order_by(func.count(models.RawEntity.id).desc()).limit(limit).all()

    return [{"name": b[0], "count": b[1]} for b in brands]


@app.get("/product-types")
def get_all_entity_types(limit: int = Query(default=200, ge=1, le=1000), db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    types = db.query(
        models.RawEntity.entity_type,
        func.count(models.RawEntity.id).label("count")
    ).filter(
        models.RawEntity.entity_type != None
    ).group_by(
        models.RawEntity.entity_type
    ).order_by(func.count(models.RawEntity.id).desc()).limit(limit).all()

    return [{"name": t[0], "count": t[1]} for t in types]


@app.get("/classifications")
def get_all_classifications(limit: int = Query(default=200, ge=1, le=1000), db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    classes = db.query(
        models.RawEntity.classification,
        func.count(models.RawEntity.id).label("count")
    ).filter(
        models.RawEntity.classification != None
    ).group_by(
        models.RawEntity.classification
    ).order_by(func.count(models.RawEntity.id).desc()).limit(limit).all()

    return [{"name": c[0], "count": c[1]} for c in classes]


# Reverse mapping: model_field -> original excel header
EXPORT_COLUMN_MAPPING = {v: k.strip() for k, v in COLUMN_MAPPING.items()}

# Fix typos in export column headers
EXPORT_COLUMN_MAPPING.update({
    "equipment": "EQUIPAMIENTO",
    "gtin_empty_reason_typo": "Motivo GTIN vacio",
    "entity_code_universal_4": "CODIGO UNIVERSAL DEL PRODUCTO",
})

@app.get("/export")
def export_entities(
    search: str = None,
    limit: int = Query(default=5000, ge=1, le=50000),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    query = db.query(models.RawEntity)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                models.RawEntity.entity_name.ilike(search_filter),
                models.RawEntity.brand_capitalized.ilike(search_filter),
                models.RawEntity.model.ilike(search_filter),
                models.RawEntity.sku.ilike(search_filter)
            )
        )

    entities = query.limit(limit).all()

    rows = []
    for p in entities:
        row = {}
        for model_field, excel_col in EXPORT_COLUMN_MAPPING.items():
            row[excel_col] = getattr(p, model_field, None)
        rows.append(row)

    df = pd.DataFrame(rows)

    # Preserve original column order
    ordered_cols = [k.strip() for k in COLUMN_MAPPING.keys()]
    existing_cols = [c for c in ordered_cols if c in df.columns]
    df = df[existing_cols]

    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=entities_export.xlsx"}
    )


# We are removing AUTHORITY_FIELDS entirely for agnosticism.

_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _build_disambig_groups(field: str, threshold: int, db: Session):
    """Shared disambiguation logic reused by /disambiguate and /authority."""
    if not _FIELD_RE.match(field):
        raise ValueError(
            f"Invalid field name '{field}'. Must be 1–64 lowercase alphanumeric/underscore characters starting with a letter."
        )
    if hasattr(models.RawEntity, field):
        column = getattr(models.RawEntity, field)
        entries = db.query(column).distinct().filter(column != None).all()
        values = [v[0] for v in entries if v[0] and str(v[0]).strip()]
    else:
        # Fallback to normalized JSON data using SQLite JSON extraction function
        json_col = func.json_extract(models.RawEntity.normalized_json, f"$.{field}")
        entries = db.query(json_col).distinct().filter(
            models.RawEntity.normalized_json != None,
            json_col != None
        ).all()
        values = [v[0] for v in entries if v[0] and str(v[0]).strip()]

    values.sort(key=len, reverse=True)

    groups = []
    processed = set()

    for val in values:
        if val in processed:
            continue
        matches = process.extract(val, values, scorer=fuzz.token_sort_ratio, limit=50)
        group_members = [m[0] for m in matches if m[1] >= threshold]

        if len(group_members) > 1:
            groups.append({
                "main": val,
                "variations": group_members,
                "count": len(group_members),
            })
            for g in group_members:
                processed.add(g)
        else:
            processed.add(val)

    return groups


@app.get("/rules", response_model=List[schemas.Rule])
def get_rules(
    field_name: str = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    query = db.query(models.NormalizationRule)
    if field_name:
        query = query.filter(models.NormalizationRule.field_name == field_name)
    return query.order_by(models.NormalizationRule.id.desc()).offset(skip).limit(limit).all()


@app.post("/rules/bulk", status_code=201)
def create_rules_bulk(payload: schemas.BulkRuleCreate, db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    # Delete existing rules for the same field + canonical so we can re-save cleanly
    for var in payload.variations:
        if var == payload.canonical_value:
            continue
        existing = db.query(models.NormalizationRule).filter(
            models.NormalizationRule.field_name == payload.field_name,
            models.NormalizationRule.original_value == var,
        ).first()
        if existing:
            existing.normalized_value = payload.canonical_value
        else:
            db.add(models.NormalizationRule(
                field_name=payload.field_name,
                original_value=var,
                normalized_value=payload.canonical_value,
            ))
    db.commit()
    return {"message": f"Rules saved for '{payload.canonical_value}'", "variations": len(payload.variations) - 1}


@app.delete("/rules/{rule_id}")
def delete_rule(rule_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    rule = db.query(models.NormalizationRule).filter(models.NormalizationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.delete(rule)
    db.commit()
    return {"message": "Rule deleted"}


@app.post("/rules/apply")
def apply_rules(field_name: str = None, db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    query = db.query(models.NormalizationRule)
    if field_name:
        query = query.filter(models.NormalizationRule.field_name == field_name)
    rules = query.all()

    total_updated = 0
    for rule in rules:
        if hasattr(models.RawEntity, rule.field_name):
            column = getattr(models.RawEntity, rule.field_name)

            if rule.is_regex:
                entities = db.query(models.RawEntity).filter(column != None).all()
                for p in entities:
                    original = getattr(p, rule.field_name)
                    if original:
                        try:
                            new_val = re.sub(rule.original_value, rule.normalized_value, original)
                            if new_val != original:
                                setattr(p, rule.field_name, new_val)
                                total_updated += 1
                        except re.error:
                            pass
            else:
                result = db.execute(
                    update(models.RawEntity)
                    .where(column == rule.original_value)
                    .values({rule.field_name: rule.normalized_value})
                )
                total_updated += result.rowcount
        else:
            # Updating JSON data inside normalized_json
            entities = db.query(models.RawEntity).filter(models.RawEntity.normalized_json != None).all()
            for entity in entities:
                try:
                    data = json.loads(entity.normalized_json or '{}')
                    original = data.get(rule.field_name)
                    if original:
                        if rule.is_regex:
                            new_val = re.sub(rule.original_value, rule.normalized_value, original)
                        else:
                            new_val = rule.normalized_value if original == rule.original_value else original
                            
                        if new_val != original:
                            data[rule.field_name] = new_val
                            entity.normalized_json = json.dumps(data)
                            db.add(entity)
                            total_updated += 1
                except Exception as exc:
                    logger.warning("Rule application skipped for entity %s: %s", entity.id, exc)
                    continue

    db.commit()
    return {
        "message": f"Applied {len(rules)} rules",
        "rules_applied": len(rules),
        "records_updated": total_updated,
    }


# ── Authority Resolution Layer ───────────────────────────────────────────

def _serialize_authority_record(r: models.AuthorityRecord) -> dict:
    """Convert ORM record to dict, deserializing all JSON fields."""
    return {
        "id":               r.id,
        "field_name":       r.field_name,
        "original_value":   r.original_value,
        "authority_source": r.authority_source,
        "authority_id":     r.authority_id,
        "canonical_label":  r.canonical_label,
        "aliases":          json.loads(r.aliases or "[]"),
        "description":      r.description,
        "confidence":       r.confidence,
        "uri":              r.uri,
        "status":           r.status,
        "created_at":       r.created_at,
        "confirmed_at":     r.confirmed_at,
        # Sprint 16
        "resolution_status": r.resolution_status or "unresolved",
        "score_breakdown":   json.loads(r.score_breakdown or "{}"),
        "evidence":          json.loads(r.evidence or "[]"),
        "merged_sources":    json.loads(r.merged_sources or "[]"),
    }


@app.post("/authority/resolve", status_code=201, tags=["authority"])
def resolve_authority(
    payload: schemas.AuthorityResolveRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Query all authority sources in parallel for a given value and persist
    the candidates with status='pending'.  Returns the persisted records.
    """
    ctx = _AuthorityContext(
        affiliation=payload.context_affiliation,
        orcid_hint=payload.context_orcid_hint,
        doi=payload.context_doi,
        year=payload.context_year,
    )
    candidates = _authority_resolve_all(payload.value, payload.entity_type.value, ctx)

    records = []
    for c in candidates:
        rec = models.AuthorityRecord(
            field_name=payload.field_name,
            original_value=payload.value,
            authority_source=c.authority_source,
            authority_id=c.authority_id,
            canonical_label=c.canonical_label,
            aliases=json.dumps(c.aliases),
            description=c.description,
            confidence=c.confidence,
            uri=c.uri,
            status="pending",
            resolution_status=c.resolution_status,
            score_breakdown=json.dumps(c.score_breakdown),
            evidence=json.dumps(c.evidence),
            merged_sources=json.dumps(c.merged_sources),
        )
        db.add(rec)
        records.append(rec)

    db.commit()
    for rec in records:
        db.refresh(rec)

    return [_serialize_authority_record(r) for r in records]


@app.post("/authority/resolve/batch", status_code=201, tags=["authority"])
def resolve_authority_batch(
    payload: schemas.BatchResolveRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Resolve all distinct values of a field against external authority sources.

    Finds every unique non-null value in raw_entities.{field_name}, optionally
    skips those that already have a pending or confirmed record, and resolves
    up to `limit` values sequentially (to avoid API rate-limiting).
    Returns a summary and the newly created AuthorityRecords.
    """
    field = payload.field_name
    entity_type = payload.entity_type.value

    # Validate field name against the SQL identifier regex (re-use existing check)
    _FIELD_RE = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
    if not _FIELD_RE.match(field):
        raise HTTPException(status_code=422, detail=f"Invalid field name: {field!r}")

    # Confirm the column actually exists in the raw_entities table
    _entity_cols = {col["name"] for col in inspect(database.engine).get_columns("raw_entities")}
    if field not in _entity_cols:
        raise HTTPException(status_code=422, detail=f"Field '{field}' not found in entity table")

    # Fetch all distinct non-null values for the field
    rows = db.execute(
        text(f'SELECT DISTINCT "{field}" FROM raw_entities WHERE "{field}" IS NOT NULL AND "{field}" != \'\'')
    ).fetchall()

    all_values = [row[0] for row in rows if row[0]]

    # Filter out values that already have a pending or confirmed record
    already_existed = 0
    if payload.skip_existing and all_values:
        existing_values = {
            r.original_value
            for r in db.query(models.AuthorityRecord.original_value).filter(
                models.AuthorityRecord.field_name == field,
                models.AuthorityRecord.status.in_(["pending", "confirmed"]),
            ).all()
        }
        filtered = [v for v in all_values if v not in existing_values]
        already_existed = len(all_values) - len(filtered)
        all_values = filtered

    to_resolve = all_values[:payload.limit]
    skipped = len(all_values) - len(to_resolve)

    ctx = _AuthorityContext()
    new_records: list[models.AuthorityRecord] = []

    for value in to_resolve:
        candidates = _authority_resolve_all(value, entity_type, ctx)
        for c in candidates:
            rec = models.AuthorityRecord(
                field_name=field,
                original_value=value,
                authority_source=c.authority_source,
                authority_id=c.authority_id,
                canonical_label=c.canonical_label,
                aliases=json.dumps(c.aliases),
                description=c.description,
                confidence=c.confidence,
                uri=c.uri,
                status="pending",
                resolution_status=c.resolution_status,
                score_breakdown=json.dumps(c.score_breakdown),
                evidence=json.dumps(c.evidence),
                merged_sources=json.dumps(c.merged_sources),
            )
            db.add(rec)
            new_records.append(rec)

    db.commit()
    for rec in new_records:
        db.refresh(rec)

    return {
        "field_name": field,
        "entity_type": entity_type,
        "resolved_count": len(to_resolve),
        "skipped_count": skipped,
        "already_existed_count": already_existed,
        "records_created": len(new_records),
        "records": [_serialize_authority_record(r) for r in new_records],
    }


@app.get("/authority/queue/summary", tags=["authority"])
def authority_queue_summary(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """
    Aggregated queue stats by field: pending / confirmed / rejected counts
    and average confidence per field.  Also returns workspace-level totals.
    """
    rows = db.query(
        models.AuthorityRecord.field_name,
        models.AuthorityRecord.status,
        func.count(models.AuthorityRecord.id),
        func.avg(models.AuthorityRecord.confidence),
    ).group_by(
        models.AuthorityRecord.field_name,
        models.AuthorityRecord.status,
    ).all()

    # Build per-field aggregates
    field_map: dict[str, dict] = {}
    totals = {"pending": 0, "confirmed": 0, "rejected": 0}

    for field_name, status, count, avg_conf in rows:
        if field_name not in field_map:
            field_map[field_name] = {"field_name": field_name, "pending": 0, "confirmed": 0, "rejected": 0, "avg_confidence": 0.0}
        if status in field_map[field_name]:
            field_map[field_name][status] = count
        if status in totals:
            totals[status] += count

    # avg_confidence: re-query per field (simpler than weighted average above)
    avg_rows = db.query(
        models.AuthorityRecord.field_name,
        func.avg(models.AuthorityRecord.confidence),
    ).group_by(models.AuthorityRecord.field_name).all()
    for field_name, avg_conf in avg_rows:
        if field_name in field_map:
            field_map[field_name]["avg_confidence"] = round(float(avg_conf or 0.0), 3)

    by_field = sorted(field_map.values(), key=lambda x: x["pending"], reverse=True)

    return {
        "total_pending":   totals["pending"],
        "total_confirmed": totals["confirmed"],
        "total_rejected":  totals["rejected"],
        "by_field":        by_field,
    }


@app.post("/authority/records/bulk-confirm", tags=["authority"])
def bulk_confirm_authority_records(
    payload: schemas.BulkActionRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Confirm multiple authority records in one request. Optionally create NormalizationRules."""
    confirmed = 0
    rules_created = 0
    now = datetime.now(timezone.utc).isoformat()

    for record_id in payload.ids:
        rec = db.query(models.AuthorityRecord).filter(
            models.AuthorityRecord.id == record_id
        ).first()
        if rec is None or rec.status == "confirmed":
            continue
        rec.status = "confirmed"
        rec.confirmed_at = now
        confirmed += 1

        if payload.also_create_rules:
            existing = db.query(models.NormalizationRule).filter(
                models.NormalizationRule.field_name == rec.field_name,
                models.NormalizationRule.original_value == rec.original_value,
            ).first()
            if not existing:
                db.add(models.NormalizationRule(
                    field_name=rec.field_name,
                    original_value=rec.original_value,
                    normalized_value=rec.canonical_label,
                    is_regex=False,
                ))
                rules_created += 1

    db.commit()
    return {"confirmed": confirmed, "rules_created": rules_created}


@app.post("/authority/records/bulk-reject", tags=["authority"])
def bulk_reject_authority_records(
    payload: schemas.BulkActionRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Reject multiple authority records in one request."""
    rejected = 0
    for record_id in payload.ids:
        rec = db.query(models.AuthorityRecord).filter(
            models.AuthorityRecord.id == record_id
        ).first()
        if rec is None or rec.status == "rejected":
            continue
        rec.status = "rejected"
        rejected += 1

    db.commit()
    return {"rejected": rejected}


@app.get("/authority/records", tags=["authority"])
def list_authority_records(
    field_name: Optional[str] = Query(None, max_length=64),
    status: Optional[str] = Query(None, pattern="^(pending|confirmed|rejected)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """List persisted authority candidates with optional filtering."""
    q = db.query(models.AuthorityRecord)
    if field_name:
        q = q.filter(models.AuthorityRecord.field_name == field_name)
    if status:
        q = q.filter(models.AuthorityRecord.status == status)
    q = q.order_by(models.AuthorityRecord.confidence.desc())
    total = q.count()
    records = q.offset(skip).limit(limit).all()
    return {
        "total": total,
        "records": [_serialize_authority_record(r) for r in records],
    }


@app.post("/authority/records/{record_id}/confirm", tags=["authority"])
def confirm_authority_record(
    record_id: int = Path(ge=1),
    payload: schemas.AuthorityConfirmRequest = schemas.AuthorityConfirmRequest(),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Confirm a candidate as the authoritative form.
    Optionally creates a NormalizationRule mapping original_value → canonical_label.
    """
    rec = db.get(models.AuthorityRecord, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="AuthorityRecord not found")

    rec.status = "confirmed"
    rec.confirmed_at = datetime.now(timezone.utc).isoformat()

    rule_created = False
    if payload.also_create_rule:
        existing = db.query(models.NormalizationRule).filter(
            models.NormalizationRule.field_name == rec.field_name,
            models.NormalizationRule.original_value == rec.original_value,
        ).first()
        if not existing:
            rule = models.NormalizationRule(
                field_name=rec.field_name,
                original_value=rec.original_value,
                normalized_value=rec.canonical_label,
                is_regex=False,
            )
            db.add(rule)
            rule_created = True

    db.commit()
    db.refresh(rec)
    return {**_serialize_authority_record(rec), "rule_created": rule_created}


@app.post("/authority/records/{record_id}/reject", tags=["authority"])
def reject_authority_record(
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Mark a candidate as rejected."""
    rec = db.get(models.AuthorityRecord, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="AuthorityRecord not found")

    rec.status = "rejected"
    db.commit()
    db.refresh(rec)
    return _serialize_authority_record(rec)


@app.delete("/authority/records/{record_id}", tags=["authority"])
def delete_authority_record(
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """Permanently delete an authority candidate record."""
    rec = db.get(models.AuthorityRecord, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="AuthorityRecord not found")

    db.delete(rec)
    db.commit()
    return {"message": "Deleted", "id": record_id}


@app.get("/authority/metrics", tags=["authority"])
def authority_metrics(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """
    Operational and quality KPIs for the Authority Resolution Layer.
    Returns counts by manual status, by resolution status, by source,
    average confidence, and confirm/reject rates.
    """
    total = db.query(func.count(models.AuthorityRecord.id)).scalar() or 0

    by_status: dict = {}
    for row in db.query(models.AuthorityRecord.status, func.count(models.AuthorityRecord.id)).group_by(models.AuthorityRecord.status).all():
        by_status[row[0]] = row[1]

    by_resolution: dict = {}
    for row in db.query(models.AuthorityRecord.resolution_status, func.count(models.AuthorityRecord.id)).group_by(models.AuthorityRecord.resolution_status).all():
        if row[0]:
            by_resolution[row[0]] = row[1]

    by_source: dict = {}
    for row in db.query(models.AuthorityRecord.authority_source, func.count(models.AuthorityRecord.id)).group_by(models.AuthorityRecord.authority_source).all():
        by_source[row[0]] = row[1]

    avg_conf = db.query(func.avg(models.AuthorityRecord.confidence)).scalar() or 0.0
    confirmed = by_status.get("confirmed", 0)
    rejected  = by_status.get("rejected", 0)

    return {
        "total_records":       total,
        "by_status":           by_status,
        "by_resolution_status": by_resolution,
        "by_source":           by_source,
        "avg_confidence":      round(float(avg_conf), 3),
        "confirm_rate":        round(confirmed / total, 3) if total > 0 else 0.0,
        "reject_rate":         round(rejected  / total, 3) if total > 0 else 0.0,
    }


@app.get("/authority/{field}")
def get_authority_view(field: str, threshold: int = Query(default=80, ge=0, le=100), db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    try:
        groups = _build_disambig_groups(field, threshold, db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch existing rules for this field
    rules = db.query(models.NormalizationRule).filter(
        models.NormalizationRule.field_name == field
    ).all()
    rules_by_original = {r.original_value: r.normalized_value for r in rules}

    # Annotate groups with rule status
    annotated = []
    for g in groups:
        resolved_to = None
        has_rules = False
        for var in g["variations"]:
            if var in rules_by_original:
                has_rules = True
                resolved_to = rules_by_original[var]
                break
        annotated.append({
            **g,
            "has_rules": has_rules,
            "resolved_to": resolved_to,
        })

    total_rules = db.query(func.count(models.NormalizationRule.id)).filter(
        models.NormalizationRule.field_name == field
    ).scalar() or 0

    return {
        "groups": annotated,
        "total_groups": len(annotated),
        "total_rules": total_rules,
        "pending_groups": sum(1 for g in annotated if not g["has_rules"]),
    }


# ── Harmonization Pipeline ──────────────────────────────────────────────

HARMONIZATION_STEPS = [
    {"step_id": "consolidate_brands",   "name": "Consolidate Brand Columns",          "description": "Merge brand_lower into brand_capitalized when empty and apply brand normalization rules.", "order": 1},
    {"step_id": "clean_entity_names",  "name": "Clean Product Names",                "description": "Remove double spaces, trim whitespace, and normalize special characters.",                "order": 2},
    {"step_id": "standardize_volumes",  "name": "Standardize Volume/Unit Variants",   "description": "Normalize volume formats (250ML → 250 mL, 1L → 1 L, 500gr → 500 g).",                  "order": 3},
    {"step_id": "consolidate_gtin",     "name": "Consolidate GTIN Columns",           "description": "Merge 4 product code columns and 7 GTIN reason fields into single authoritative values.","order": 4},
    {"step_id": "fix_export_typos",     "name": "Fix Export Column Name Typos",       "description": "Correct EQUIMAPIENTO → EQUIPAMIENTO, PRODRUCTO → PRODUCTO in export headers.",           "order": 5},
]

VOLUME_PATTERNS = [
    (r'(\d+)\s*(?:ML|Ml|ml)', r'\1 mL'),
    (r'(\d+(?:\.\d+)?)\s*(?:LT|Lt|lt|lts|LTS|Lts)\b', r'\1 L'),
    (r'(\d+(?:\.\d+)?)\s*[Ll]\b(?![\w])', r'\1 L'),
    (r'(\d+(?:\.\d+)?)\s*(?:KG|Kg|kg|kgs|KGS)\b', r'\1 kg'),
    (r'(\d+)\s*(?:GR|Gr|gr|grs|GRS)\b', r'\1 g'),
    (r'(\d+(?:\.\d+)?)\s*(?:CM|Cm|cm)\b', r'\1 cm'),
    (r'(\d+(?:\.\d+)?)\s*(?:MT|Mt|mt|mts|MTS)\b', r'\1 m'),
]

EXPORT_COLUMN_CORRECTIONS = {
    "equipment": "EQUIPAMIENTO",
    "gtin_empty_reason_typo": "Motivo GTIN vacio",
    "entity_code_universal_4": "CODIGO UNIVERSAL DEL PRODUCTO",
}


_PREVIEW_ROW_CAP = 10_000  # Max rows examined during preview to avoid OOM


def _step_consolidate_brands(db: Session, preview_only: bool):
    changes = []
    q = db.query(models.RawEntity)
    if preview_only:
        q = q.limit(_PREVIEW_ROW_CAP)
    entities = q.all()

    # Load existing brand normalization rules
    brand_rules = db.query(models.NormalizationRule).filter(
        models.NormalizationRule.field_name == "brand_capitalized",
        models.NormalizationRule.is_regex == False,
    ).all()
    brand_map = {r.original_value: r.normalized_value for r in brand_rules}

    for p in entities:
        new_brand = p.brand_capitalized

        if not new_brand or not new_brand.strip():
            if p.brand_lower and p.brand_lower.strip():
                new_brand = p.brand_lower.strip()
            else:
                continue

        new_brand = new_brand.strip()

        # Apply normalization rules
        if new_brand in brand_map:
            new_brand = brand_map[new_brand]

        if new_brand != p.brand_capitalized:
            changes.append({
                "record_id": p.id,
                "field": "brand_capitalized",
                "old_value": p.brand_capitalized,
                "new_value": new_brand,
            })
            if not preview_only:
                p.brand_capitalized = new_brand

    if not preview_only:
        db.commit()
    return changes


def _step_clean_entity_names(db: Session, preview_only: bool):
    changes = []
    q = db.query(models.RawEntity).filter(models.RawEntity.entity_name != None)
    if preview_only:
        q = q.limit(_PREVIEW_ROW_CAP)
    entities = q.all()

    for p in entities:
        original = p.entity_name
        if not original:
            continue

        cleaned = original
        cleaned = cleaned.replace('\u00a0', ' ')
        cleaned = cleaned.replace('\t', ' ')
        cleaned = re.sub(r'\s{2,}', ' ', cleaned)
        cleaned = cleaned.strip()

        if cleaned != original:
            changes.append({
                "record_id": p.id,
                "field": "entity_name",
                "old_value": original,
                "new_value": cleaned,
            })
            if not preview_only:
                p.entity_name = cleaned

    if not preview_only:
        db.commit()
    return changes


def _step_standardize_volumes(db: Session, preview_only: bool):
    changes = []
    target_fields = ["entity_name", "measure"]

    # Load regex normalization rules
    regex_rules = db.query(models.NormalizationRule).filter(
        models.NormalizationRule.is_regex == True
    ).all()

    for field_name in target_fields:
        column = getattr(models.RawEntity, field_name)
        q = db.query(models.RawEntity).filter(column != None)
        if preview_only:
            q = q.limit(_PREVIEW_ROW_CAP)
        entities = q.all()

        for p in entities:
            original = getattr(p, field_name)
            if not original:
                continue

            modified = original
            for pattern, replacement in VOLUME_PATTERNS:
                modified = re.sub(pattern, replacement, modified)

            for rule in regex_rules:
                if rule.field_name == field_name:
                    try:
                        modified = re.sub(rule.original_value, rule.normalized_value, modified)
                    except re.error:
                        pass

            if modified != original:
                changes.append({
                    "record_id": p.id,
                    "field": field_name,
                    "old_value": original,
                    "new_value": modified,
                })
                if not preview_only:
                    setattr(p, field_name, modified)

    if not preview_only:
        db.commit()
    return changes


def _step_consolidate_gtin(db: Session, preview_only: bool):
    changes = []
    q = db.query(models.RawEntity)
    if preview_only:
        q = q.limit(_PREVIEW_ROW_CAP)
    entities = q.all()

    code_fields = [
        "entity_code_universal_1",
        "entity_code_universal_2",
        "entity_code_universal_3",
        "entity_code_universal_4",
    ]

    reason_fields = [
        "gtin_empty_reason_1",
        "gtin_empty_reason_2",
        "gtin_empty_reason_3",
        "gtin_entity_reason",
        "gtin_reason_lower",
        "gtin_empty_reason_typo",
    ]

    for p in entities:
        # Consolidate product codes into gtin
        current_gtin = p.gtin
        if not current_gtin or not current_gtin.strip():
            for code_field in code_fields:
                val = getattr(p, code_field)
                if val and val.strip():
                    changes.append({
                        "record_id": p.id,
                        "field": "gtin",
                        "old_value": current_gtin,
                        "new_value": val.strip(),
                    })
                    if not preview_only:
                        p.gtin = val.strip()
                    break

        # Consolidate GTIN reasons into gtin_reason
        current_reason = p.gtin_reason
        if not current_reason or not current_reason.strip():
            for reason_field in reason_fields:
                val = getattr(p, reason_field)
                if val and val.strip():
                    changes.append({
                        "record_id": p.id,
                        "field": "gtin_reason",
                        "old_value": current_reason,
                        "new_value": val.strip(),
                    })
                    if not preview_only:
                        p.gtin_reason = val.strip()
                    break

    if not preview_only:
        db.commit()
    return changes


def _step_fix_export_typos(db: Session, preview_only: bool):
    changes = []
    for field, corrected_header in EXPORT_COLUMN_CORRECTIONS.items():
        current_header = EXPORT_COLUMN_MAPPING.get(field, "")
        if current_header != corrected_header:
            changes.append({
                "record_id": 0,
                "field": field,
                "old_value": current_header,
                "new_value": corrected_header,
            })
            if not preview_only:
                EXPORT_COLUMN_MAPPING[field] = corrected_header
    return changes


STEP_FUNCTIONS = {
    "consolidate_brands": _step_consolidate_brands,
    "clean_entity_names": _step_clean_entity_names,
    "standardize_volumes": _step_standardize_volumes,
    "consolidate_gtin": _step_consolidate_gtin,
    "fix_export_typos": _step_fix_export_typos,
}


@app.get("/harmonization/steps")
def get_harmonization_steps(db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    total_entities = db.query(func.count(models.RawEntity.id)).scalar() or 0

    steps_with_status = []
    for step in HARMONIZATION_STEPS:
        last_log = db.query(models.HarmonizationLog).filter(
            models.HarmonizationLog.step_id == step["step_id"]
        ).order_by(models.HarmonizationLog.id.desc()).first()

        steps_with_status.append({
            **step,
            "status": "completed" if last_log else "pending",
            "last_run": last_log.executed_at.isoformat() if last_log and last_log.executed_at else None,
            "last_records_updated": last_log.records_updated if last_log else None,
        })

    return {"steps": steps_with_status, "total_entities": total_entities}


@app.post("/harmonization/preview/{step_id}")
def preview_harmonization_step(step_id: str, db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    if step_id not in STEP_FUNCTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step_id}")

    step_def = next(s for s in HARMONIZATION_STEPS if s["step_id"] == step_id)
    changes = STEP_FUNCTIONS[step_id](db, preview_only=True)

    return {
        "step_id": step_id,
        "step_name": step_def["name"],
        "description": step_def["description"],
        "total_affected": len(changes),
        "changes": changes[:200],
        "sample_changes": changes[:50],
    }


@app.post("/harmonization/apply/{step_id}")
def apply_harmonization_step(step_id: str, db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    if step_id not in STEP_FUNCTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step_id}")

    step_def = next(s for s in HARMONIZATION_STEPS if s["step_id"] == step_id)
    changes = STEP_FUNCTIONS[step_id](db, preview_only=False)

    fields_modified = list(set(c["field"] for c in changes))
    log_entry = models.HarmonizationLog(
        step_id=step_id,
        step_name=step_def["name"],
        records_updated=len(changes),
        fields_modified=json.dumps(fields_modified),
        executed_at=datetime.now(timezone.utc),
        details=json.dumps({"sample": changes[:20]}),
        reverted=False,
    )
    db.add(log_entry)
    db.flush()  # Get log_entry.id before committing

    # Store all individual changes for undo/redo
    for c in changes:
        db.add(models.HarmonizationChangeRecord(
            log_id=log_entry.id,
            record_id=c["record_id"],
            field=c["field"],
            old_value=c["old_value"],
            new_value=c["new_value"],
        ))

    db.commit()

    return {
        "step_id": step_id,
        "step_name": step_def["name"],
        "records_updated": len(changes),
        "fields_modified": fields_modified,
        "log_id": log_entry.id,
    }


@app.post("/harmonization/apply-all")
def apply_all_harmonization_steps(db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    results = []
    for step in HARMONIZATION_STEPS:
        step_id = step["step_id"]
        changes = STEP_FUNCTIONS[step_id](db, preview_only=False)
        fields_modified = list(set(c["field"] for c in changes))

        log_entry = models.HarmonizationLog(
            step_id=step_id,
            step_name=step["name"],
            records_updated=len(changes),
            fields_modified=json.dumps(fields_modified),
            executed_at=datetime.now(timezone.utc),
            reverted=False,
        )
        db.add(log_entry)
        db.flush()

        for c in changes:
            db.add(models.HarmonizationChangeRecord(
                log_id=log_entry.id,
                record_id=c["record_id"],
                field=c["field"],
                old_value=c["old_value"],
                new_value=c["new_value"],
            ))

        results.append({
            "step_id": step_id,
            "step_name": step["name"],
            "records_updated": len(changes),
            "fields_modified": fields_modified,
            "log_id": log_entry.id,
        })

    db.commit()
    return {"results": results, "total_steps": len(results)}


@app.get("/harmonization/logs")
def get_harmonization_logs(db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    logs = db.query(models.HarmonizationLog).order_by(
        models.HarmonizationLog.id.desc()
    ).limit(50).all()

    return [{
        "id": log.id,
        "step_id": log.step_id,
        "step_name": log.step_name,
        "records_updated": log.records_updated,
        "fields_modified": json.loads(log.fields_modified) if log.fields_modified else [],
        "executed_at": log.executed_at.isoformat() if log.executed_at else None,
        "reverted": bool(log.reverted) if log.reverted is not None else False,
    } for log in logs]


@app.post("/harmonization/undo/{log_id}")
def undo_harmonization(log_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    log_entry = db.query(models.HarmonizationLog).filter(
        models.HarmonizationLog.id == log_id
    ).first()
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
    if log_entry.reverted:
        raise HTTPException(status_code=400, detail="This operation has already been reverted")

    # Fetch all stored changes for this log
    change_records = db.query(models.HarmonizationChangeRecord).filter(
        models.HarmonizationChangeRecord.log_id == log_id
    ).all()

    if not change_records and log_entry.records_updated > 0:
        raise HTTPException(status_code=400, detail="No change records found for this log entry (pre-undo data not available)")

    restored = 0
    for cr in change_records:
        entity = db.query(models.RawEntity).filter(
            models.RawEntity.id == cr.record_id
        ).first()
        if entity:
            setattr(entity, cr.field, cr.old_value)
            restored += 1

    log_entry.reverted = True
    db.commit()

    return {
        "log_id": log_id,
        "action": "undo",
        "records_restored": restored,
        "step_id": log_entry.step_id,
        "step_name": log_entry.step_name,
    }


@app.post("/harmonization/redo/{log_id}")
def redo_harmonization(log_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin", "editor"))):
    log_entry = db.query(models.HarmonizationLog).filter(
        models.HarmonizationLog.id == log_id
    ).first()
    if not log_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
    if not log_entry.reverted:
        raise HTTPException(status_code=400, detail="This operation has not been reverted, cannot redo")

    change_records = db.query(models.HarmonizationChangeRecord).filter(
        models.HarmonizationChangeRecord.log_id == log_id
    ).all()

    reapplied = 0
    for cr in change_records:
        entity = db.query(models.RawEntity).filter(
            models.RawEntity.id == cr.record_id
        ).first()
        if entity:
            setattr(entity, cr.field, cr.new_value)
            reapplied += 1

    log_entry.reverted = False
    db.commit()

    return {
        "log_id": log_id,
        "action": "redo",
        "records_restored": reapplied,
        "step_id": log_entry.step_id,
        "step_name": log_entry.step_name,
    }


# ── Store Integration Endpoints ─────────────────────────────────────────

@app.get("/stores")
def get_all_stores(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    stores = db.query(models.StoreConnection).order_by(models.StoreConnection.id.desc()).offset(skip).limit(limit).all()
    result = []
    for s in stores:
        result.append({
            "id": s.id,
            "name": s.name,
            "platform": s.platform,
            "base_url": s.base_url,
            "is_active": s.is_active,
            "last_sync_at": str(s.last_sync_at) if s.last_sync_at else None,
            "created_at": str(s.created_at) if s.created_at else None,
            "entity_count": s.entity_count or 0,
            "sync_direction": s.sync_direction or "bidirectional",
            "notes": s.notes,
        })
    return result


@app.get("/stores/{store_id}")
def get_store(store_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    store = db.query(models.StoreConnection).filter(models.StoreConnection.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")
    return {
        "id": store.id,
        "name": store.name,
        "platform": store.platform,
        "base_url": store.base_url,
        "is_active": store.is_active,
        "last_sync_at": str(store.last_sync_at) if store.last_sync_at else None,
        "created_at": str(store.created_at) if store.created_at else None,
        "entity_count": store.entity_count or 0,
        "sync_direction": store.sync_direction or "bidirectional",
        "notes": store.notes,
        "has_api_key": bool(store.api_key),
        "has_api_secret": bool(store.api_secret),
        "has_access_token": bool(store.access_token),
    }


@app.post("/stores", status_code=201)
def create_store(
    payload: schemas.StoreConnectionCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    store = models.StoreConnection(
        name=payload.name.strip(),
        platform=payload.platform,
        base_url=payload.base_url.rstrip("/"),
        api_key=encrypt(payload.api_key),
        api_secret=encrypt(payload.api_secret),
        access_token=encrypt(payload.access_token),
        custom_headers=payload.custom_headers,
        sync_direction=payload.sync_direction,
        notes=payload.notes,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        entity_count=0,
    )
    db.add(store)
    db.commit()
    db.refresh(store)

    return {
        "message": f"Store '{store.name}' created successfully",
        "id": store.id,
        "platform": store.platform,
    }


@app.put("/stores/{store_id}")
def update_store(
    store_id: int = Path(..., ge=1),
    payload: schemas.StoreConnectionUpdate = ...,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    store = db.query(models.StoreConnection).filter(models.StoreConnection.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"]:
        update_data["name"] = update_data["name"].strip()
    if "base_url" in update_data and update_data["base_url"]:
        update_data["base_url"] = update_data["base_url"].rstrip("/")

    # Encrypt credential fields before persisting
    for cred_field in ("api_key", "api_secret", "access_token"):
        if cred_field in update_data and update_data[cred_field] is not None:
            update_data[cred_field] = encrypt(update_data[cred_field])

    for field, value in update_data.items():
        setattr(store, field, value)

    db.commit()
    db.refresh(store)
    return {"message": f"Store '{store.name}' updated successfully", "id": store.id}


@app.delete("/stores/{store_id}")
def delete_store(store_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    store = db.query(models.StoreConnection).filter(models.StoreConnection.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")

    # Also delete associated mappings and logs
    db.query(models.StoreSyncMapping).filter(models.StoreSyncMapping.store_id == store_id).delete()
    db.query(models.SyncLog).filter(models.SyncLog.store_id == store_id).delete()
    db.delete(store)
    db.commit()
    return {"message": f"Store '{store.name}' and all associated data deleted", "id": store_id}


@app.post("/stores/{store_id}/toggle")
def toggle_store(store_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    store = db.query(models.StoreConnection).filter(models.StoreConnection.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store connection not found")
    store.is_active = not store.is_active
    db.commit()
    return {"message": f"Store '{store.name}' {'activated' if store.is_active else 'deactivated'}", "is_active": store.is_active}


@app.get("/stores/stats/summary")
def get_stores_summary(db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    total_stores = db.query(func.count(models.StoreConnection.id)).scalar() or 0
    active_stores = db.query(func.count(models.StoreConnection.id)).filter(
        models.StoreConnection.is_active == True
    ).scalar() or 0
    total_mappings = db.query(func.count(models.StoreSyncMapping.id)).scalar() or 0

    platform_counts = db.query(
        models.StoreConnection.platform,
        func.count(models.StoreConnection.id)
    ).group_by(models.StoreConnection.platform).all()

    return {
        "total_stores": total_stores,
        "active_stores": active_stores,
        "total_mappings": total_mappings,
        "platforms": {p[0]: p[1] for p in platform_counts},
    }


# ── Sync Engine Endpoints ───────────────────────────────────────────────

def _get_store_adapter(store: models.StoreConnection):
    """Build adapter from store connection model, decrypting credentials."""
    config = {
        "platform": store.platform,
        "base_url": store.base_url,
        "api_key": decrypt(store.api_key),
        "api_secret": decrypt(store.api_secret),
        "access_token": decrypt(store.access_token),
        "custom_headers": store.custom_headers,
    }
    return get_adapter(store.platform, config)


@app.post("/stores/{store_id}/test")
def test_store_connection(store_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    store = db.query(models.StoreConnection).filter(models.StoreConnection.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    try:
        adapter = _get_store_adapter(store)
        result = adapter.test_connection()
        return {
            "success": result.success,
            "message": result.message,
            "store_name": result.store_name,
            "entity_count": result.entity_count,
            "api_version": result.api_version,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/stores/{store_id}/pull")
def pull_entities_from_store(store_id: int = Path(..., ge=1), page: int = Query(default=1, ge=1), per_page: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    """Pull entities from remote store and create queue items for human review."""
    store = db.query(models.StoreConnection).filter(models.StoreConnection.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    if not store.is_active:
        raise HTTPException(status_code=400, detail="Store connection is inactive")

    try:
        adapter = _get_store_adapter(store)
        remote_entities = adapter.fetch_entities(page=page, per_page=per_page)
    except Exception as e:
        # Log the error
        db.add(models.SyncLog(
            store_id=store_id, action="pull", status="error",
            records_affected=0, details=str(e), executed_at=datetime.now(timezone.utc)
        ))
        db.commit()
        raise HTTPException(status_code=502, detail=f"Failed to fetch from store: {e}")

    new_mappings = 0
    new_queue_items = 0
    skipped = 0

    for rp in remote_entities:
        if not rp.canonical_url:
            skipped += 1
            continue

        # Check if mapping exists by canonical_url
        existing = db.query(models.StoreSyncMapping).filter(
            models.StoreSyncMapping.store_id == store_id,
            models.StoreSyncMapping.canonical_url == rp.canonical_url,
        ).first()

        if not existing:
            # Create new mapping
            mapping = models.StoreSyncMapping(
                store_id=store_id,
                local_entity_id=None,
                remote_entity_id=rp.remote_id,
                canonical_url=rp.canonical_url,
                remote_sku=rp.sku,
                remote_name=rp.name,
                remote_price=rp.price,
                remote_stock=rp.stock,
                remote_status=rp.status,
                remote_data_json=json.dumps(rp.raw_data, default=str, ensure_ascii=False) if rp.raw_data else None,
                sync_status="pending",
                created_at=datetime.now(timezone.utc),
            )
            db.add(mapping)
            db.flush()
            new_mappings += 1

            # Create queue item for human review
            db.add(models.SyncQueueItem(
                store_id=store_id,
                mapping_id=mapping.id,
                direction="pull",
                entity_name=rp.name,
                canonical_url=rp.canonical_url,
                field="new_entity",
                local_value=None,
                remote_value=rp.name,
                status="pending",
                created_at=datetime.now(timezone.utc),
            ))
            new_queue_items += 1
        else:
            # Check for changes in existing mapping
            changes = []
            if existing.remote_name != rp.name and rp.name:
                changes.append(("name", existing.remote_name, rp.name))
            if existing.remote_price != rp.price and rp.price:
                changes.append(("price", existing.remote_price, rp.price))
            if existing.remote_stock != rp.stock and rp.stock:
                changes.append(("stock", existing.remote_stock, rp.stock))
            if existing.remote_sku != rp.sku and rp.sku:
                changes.append(("sku", existing.remote_sku, rp.sku))
            if existing.remote_status != rp.status and rp.status:
                changes.append(("status", existing.remote_status, rp.status))

            for field, old_val, new_val in changes:
                # Only create queue item if not already pending for this field
                already_pending = db.query(models.SyncQueueItem).filter(
                    models.SyncQueueItem.mapping_id == existing.id,
                    models.SyncQueueItem.field == field,
                    models.SyncQueueItem.status == "pending",
                ).first()
                if not already_pending:
                    db.add(models.SyncQueueItem(
                        store_id=store_id,
                        mapping_id=existing.id,
                        direction="pull",
                        entity_name=rp.name,
                        canonical_url=rp.canonical_url,
                        field=field,
                        local_value=old_val,
                        remote_value=new_val,
                        status="pending",
                        created_at=datetime.now(timezone.utc),
                    ))
                    new_queue_items += 1

            # Update snapshot
            existing.remote_name = rp.name or existing.remote_name
            existing.remote_price = rp.price or existing.remote_price
            existing.remote_stock = rp.stock or existing.remote_stock
            existing.remote_sku = rp.sku or existing.remote_sku
            existing.remote_status = rp.status or existing.remote_status
            existing.remote_data_json = json.dumps(rp.raw_data, default=str, ensure_ascii=False) if rp.raw_data else existing.remote_data_json
            existing.last_synced_at = datetime.now(timezone.utc)

    # Log the sync
    store.last_sync_at = datetime.now(timezone.utc)
    db.add(models.SyncLog(
        store_id=store_id, action="pull", status="success",
        records_affected=new_mappings + new_queue_items,
        details=json.dumps({"new_mappings": new_mappings, "queue_items": new_queue_items, "skipped": skipped}),
        executed_at=datetime.now(timezone.utc)
    ))
    db.commit()

    return {
        "message": f"Pull completed: {len(remote_entities)} entities fetched",
        "new_mappings": new_mappings,
        "new_queue_items": new_queue_items,
        "skipped": skipped,
        "total_fetched": len(remote_entities),
    }


@app.get("/stores/{store_id}/mappings")
def get_store_mappings(store_id: int = Path(..., ge=1), skip: int = 0, limit: int = 50, db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    total = db.query(func.count(models.StoreSyncMapping.id)).filter(
        models.StoreSyncMapping.store_id == store_id
    ).scalar() or 0

    mappings = db.query(models.StoreSyncMapping).filter(
        models.StoreSyncMapping.store_id == store_id
    ).order_by(models.StoreSyncMapping.id.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "mappings": [{
            "id": m.id,
            "local_entity_id": m.local_entity_id,
            "remote_entity_id": m.remote_entity_id,
            "canonical_url": m.canonical_url,
            "remote_sku": m.remote_sku,
            "remote_name": m.remote_name,
            "remote_price": m.remote_price,
            "remote_stock": m.remote_stock,
            "remote_status": m.remote_status,
            "sync_status": m.sync_status,
            "last_synced_at": str(m.last_synced_at) if m.last_synced_at else None,
        } for m in mappings]
    }


@app.get("/stores/{store_id}/queue")
def get_store_queue(store_id: int = Path(..., ge=1), status: str = "pending", skip: int = 0, limit: int = 50, db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    query = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.store_id == store_id,
    )
    if status != "all":
        query = query.filter(models.SyncQueueItem.status == status)

    total = query.count()
    items = query.order_by(models.SyncQueueItem.id.desc()).offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [{
            "id": q.id,
            "mapping_id": q.mapping_id,
            "direction": q.direction,
            "entity_name": q.entity_name,
            "canonical_url": q.canonical_url,
            "field": q.field,
            "local_value": q.local_value,
            "remote_value": q.remote_value,
            "status": q.status,
            "created_at": str(q.created_at) if q.created_at else None,
            "resolved_at": str(q.resolved_at) if q.resolved_at else None,
        } for q in items]
    }


@app.post("/stores/queue/{item_id}/approve")
def approve_queue_item(item_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    # Optimistic update: only succeeds if the item is still pending (avoids TOCTOU)
    now = datetime.now(timezone.utc)
    rows = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.id == item_id,
        models.SyncQueueItem.status == "pending",
    ).update({"status": "approved", "resolved_at": now})
    if rows == 0:
        # Either not found or no longer pending — distinguish for a clear response
        item = db.query(models.SyncQueueItem).filter(models.SyncQueueItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found")
        raise HTTPException(status_code=409, detail=f"Item is already {item.status}")
    db.commit()
    return {"message": "Item approved", "id": item_id, "status": "approved"}


@app.post("/stores/queue/{item_id}/reject")
def reject_queue_item(item_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    # Optimistic update: only succeeds if the item is still pending (avoids TOCTOU)
    now = datetime.now(timezone.utc)
    rows = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.id == item_id,
        models.SyncQueueItem.status == "pending",
    ).update({"status": "rejected", "resolved_at": now})
    if rows == 0:
        item = db.query(models.SyncQueueItem).filter(models.SyncQueueItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Queue item not found")
        raise HTTPException(status_code=409, detail=f"Item is already {item.status}")
    db.commit()
    return {"message": "Item rejected", "id": item_id, "status": "rejected"}


@app.post("/stores/queue/bulk-approve")
def bulk_approve_queue(store_id: int = Query(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    """Approve all pending queue items for a store."""
    updated = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.store_id == store_id,
        models.SyncQueueItem.status == "pending",
    ).update({"status": "approved", "resolved_at": datetime.now(timezone.utc)})
    db.commit()
    return {"message": f"{updated} items approved", "count": updated}


@app.post("/stores/queue/bulk-reject")
def bulk_reject_queue(store_id: int = Query(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    """Reject all pending queue items for a store."""
    updated = db.query(models.SyncQueueItem).filter(
        models.SyncQueueItem.store_id == store_id,
        models.SyncQueueItem.status == "pending",
    ).update({"status": "rejected", "resolved_at": datetime.now(timezone.utc)})
    db.commit()
    return {"message": f"{updated} items rejected", "count": updated}


@app.get("/stores/{store_id}/logs")
def get_store_logs(store_id: int = Path(..., ge=1), skip: int = 0, limit: int = 20, db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    logs = db.query(models.SyncLog).filter(
        models.SyncLog.store_id == store_id
    ).order_by(models.SyncLog.id.desc()).offset(skip).limit(limit).all()

    return [{
        "id": l.id,
        "action": l.action,
        "status": l.status,
        "records_affected": l.records_affected,
        "details": l.details,
        "executed_at": str(l.executed_at) if l.executed_at else None,
    } for l in logs]


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Liveness + DB connectivity probe."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"
    status = "ok" if db_status == "ok" else "degraded"
    return {"status": status, "database": db_status}


# --- Phase 5: AI / RAG Integrations ---
class AIIntegrationPayload(schemas.BaseModel):
    provider_name: str = Field(min_length=1, max_length=100)
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None


class AIIntegrationUpdate(schemas.BaseModel):
    base_url: str | None = Field(default=None, max_length=500)
    api_key: str | None = None
    model_name: str | None = Field(default=None, max_length=100)

@app.get("/ai-integrations")
def get_ai_integrations(db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    integrations = db.query(models.AIIntegration).all()
    # Never expose raw api_key — return a masked indicator instead
    return [
        {
            "id": i.id,
            "provider_name": i.provider_name,
            "base_url": i.base_url,
            "model_name": i.model_name,
            "is_active": i.is_active,
            "created_at": str(i.created_at) if i.created_at else None,
            "has_api_key": bool(i.api_key),
        }
        for i in integrations
    ]

@app.post("/ai-integrations", status_code=201)
def create_ai_integration(
    payload: AIIntegrationPayload,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    existing = db.query(models.AIIntegration).filter(models.AIIntegration.provider_name == payload.provider_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Provider already configured.")
    new_ai = models.AIIntegration(
        provider_name=payload.provider_name,
        base_url=payload.base_url,
        api_key=encrypt(payload.api_key),
        model_name=payload.model_name,
        is_active=False,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_ai)
    db.commit()
    db.refresh(new_ai)
    return {"message": f"Provider '{new_ai.provider_name}' configured", "id": new_ai.id}

@app.put("/ai-integrations/{integration_id}")
def update_ai_integration(
    integration_id: int = Path(..., ge=1),
    payload: AIIntegrationUpdate = ...,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    integration = db.query(models.AIIntegration).filter(models.AIIntegration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "base_url" in update_data:
        integration.base_url = update_data["base_url"]
    if "api_key" in update_data and update_data["api_key"] is not None:
        integration.api_key = encrypt(update_data["api_key"])
    if "model_name" in update_data:
        integration.model_name = update_data["model_name"]

    db.commit()
    return {"message": "Updated successfully", "id": integration.id}

@app.post("/ai-integrations/{integration_id}/activate")
def activate_ai_integration(integration_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    # Deactivate all others
    db.query(models.AIIntegration).update({"is_active": False})

    # Activate target
    integration = db.query(models.AIIntegration).filter(models.AIIntegration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration.is_active = True
    db.commit()
    return {"message": f"{integration.provider_name} activated"}

@app.delete("/ai-integrations/{integration_id}")
def delete_ai_integration(integration_id: int = Path(..., ge=1), db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    integration = db.query(models.AIIntegration).filter(models.AIIntegration.id == integration_id).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    db.delete(integration)
    db.commit()
    return {"message": "Deleted"}


# --- Phase 5: RAG Endpoints ---

class RAGQueryPayload(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=5, ge=1, le=20)

def _get_active_integration(db: Session):
    """Return the active AI integration with its api_key decrypted for use.

    The object is expunged from the session before the api_key is overwritten so
    SQLAlchemy cannot flush the plaintext key back to the database.
    """
    integration = db.query(models.AIIntegration).filter(models.AIIntegration.is_active == True).first()
    if not integration:
        return None
    db.expunge(integration)  # detach — mutations below are not tracked
    if integration.api_key:
        integration.api_key = decrypt(integration.api_key)
    return integration

@app.post("/rag/index")
def rag_index_catalog(db: Session = Depends(get_db), _: models.User = Depends(require_role("super_admin", "admin"))):
    """
    Phase 5: Bulk index all enriched products into the ChromaDB Vector Store.
    Only products with enrichment_status='completed' are indexed.
    """
    integration = _get_active_integration(db)
    if not integration:
        raise HTTPException(status_code=400, detail="No active AI provider. Configure one in Integrations → AI Language Models.")

    entities = db.query(models.RawEntity).filter(
        models.RawEntity.enrichment_status == "completed"
    ).all()

    indexed = 0
    skipped = 0
    errors = 0

    for entity in entities:
        result = rag_engine.index_entity(entity, integration)
        if result["status"] == "indexed":
            indexed += 1
        elif result["status"] == "skipped":
            skipped += 1
        else:
            errors += 1

    return {
        "message": f"Indexing complete.",
        "indexed": indexed,
        "skipped": skipped,
        "errors": errors,
        "provider_used": integration.provider_name
    }

@app.post("/rag/query")
def rag_query(payload: RAGQueryPayload, db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    """
    Phase 5: Accepts a natural language question and returns a grounded, context-aware answer
    using the active LLM provider and the ChromaDB vector store.
    """
    integration = _get_active_integration(db)
    result = rag_engine.query_catalog(
        user_question=payload.question,
        integration_record=integration,
        top_k=payload.top_k
    )
    return result

@app.get("/rag/stats")
def rag_stats(_: models.User = Depends(get_current_user)):
    """Returns ChromaDB index statistics."""
    return VectorStoreService.get_stats()

@app.delete("/rag/index")
def rag_clear_index(_: models.User = Depends(require_role("super_admin", "admin"))):
    """Clears the entire vector index. Use with caution."""
    VectorStoreService.clear_all()
    return {"message": "Vector index cleared."}
