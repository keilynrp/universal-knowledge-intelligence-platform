"""
Data ingestion and export endpoints.
  POST /upload
  POST /upload/preview
  POST /upload/suggest-mapping
  POST /analyze
  GET  /export
"""
import io
import json
import logging
import math
import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend import database, models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.routers.limiter import limiter
from backend.datasource_analyzer import DataSourceAnalyzer
from backend.importers.scientific import ScientificImportResult, detect_scientific_import
from backend.routers.column_maps import COLUMN_MAPPING, EXPORT_COLUMN_MAPPING
from backend.routers.deps import _audit, _dispatch_webhook, _get_active_integration
from backend.services.graph_materializer import materialize_scientific_import_graph
from backend.services import engine_bridge
from backend.services.text_normalization import normalize_import_value
from backend.tenant_access import persisted_org_id, resolve_request_org_id, scope_query_to_org

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
_MAX_ROWS = 100_000
_CHUNK_SIZE = 10_000

# Fields exposed for wizard field-mapping
MAPPABLE_MODEL_FIELDS = [
    "primary_label", "secondary_label", "canonical_id", "entity_type", "domain",
    "enrichment_doi", "enrichment_citation_count", "enrichment_concepts",
    "enrichment_source", "creation_date", "validation_status",
]

_VIRTUAL_MODEL_FIELDS = {"creation_date"}

_SCIENCE_AUTO_MAPPING = {
    "title":    "primary_label",
    "authors":  "secondary_label",
    "doi":      "enrichment_doi",
    "keywords": "enrichment_concepts",
    "year":     "creation_date",
    "journal":  "secondary_label",
}

# Human-readable descriptions for the LLM prompt
_FIELD_DESCRIPTIONS = {
    "primary_label":             "main name/title of the entity (product name, paper title, person name)",
    "secondary_label":           "secondary label (brand, author, publisher, organization)",
    "canonical_id":              "unique identifier (SKU, DOI, ISBN, GTIN, barcode, record ID)",
    "entity_type":               "type or category of the entity (product, paper, person, organization…)",
    "domain":                    "knowledge domain (science, healthcare, business, education…)",
    "enrichment_doi":            "Digital Object Identifier (DOI)",
    "enrichment_citation_count": "number of citations (integer)",
    "enrichment_concepts":       "keywords, topics, or concepts (comma-separated)",
    "enrichment_source":         "source or database that provided enrichment data",
    "creation_date":             "date the entity was created or published",
    "validation_status":         "validation or review status of the record",
}

_VALID_UKIP_FIELDS: set[str] = set(_FIELD_DESCRIPTIONS.keys())

_SUGGEST_SYSTEM_PROMPT = (
    "You are a data-field mapper for UKIP (Universal Knowledge Intelligence Platform).\n"
    "Given a list of column names from a user-uploaded file and up to 3 sample values per "
    "column, decide which UKIP model field each column best maps to.\n\n"
    "VALID UKIP FIELDS:\n"
    + "\n".join(f"  - {k}: {v}" for k, v in _FIELD_DESCRIPTIONS.items())
    + "\n\nRULES:\n"
    "1. Return ONLY a raw JSON object — no markdown, no explanation.\n"
    "2. Keys = original column names exactly as given.\n"
    "3. Values = one of the valid UKIP field names above, or null if no clear match.\n"
    "4. Avoid mapping two columns to the same field unless the first one is clearly wrong.\n"
    "5. When in doubt, use null rather than a wrong guess.\n"
)


def _parse_llm_mapping(raw: str, valid_fields: set[str]) -> dict[str, Optional[str]]:
    """
    Robustly extract a {column: field_or_null} dict from an LLM text response.
    Tries direct JSON parse first, then regex extraction of the first {...} block.
    Values not in valid_fields are coerced to None.
    """
    text = raw.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    text = text.strip()

    parsed: dict = {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to find the first {...} block in the response
        m = re.search(r"\{[\s\S]+\}", text)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except json.JSONDecodeError:
                pass

    if not isinstance(parsed, dict):
        return {}

    result = {}
    for k, v in parsed.items():
        if not isinstance(k, str):
            continue
        if v is None or (isinstance(v, str) and v.strip() == ""):
            result[k] = None
        elif isinstance(v, str) and v.strip() in valid_fields:
            result[k] = v.strip()
        else:
            result[k] = None  # LLM hallucinated an unknown field name

    return result


# ── Pydantic model for suggest-mapping ────────────────────────────────────────

class SuggestMappingRequest(BaseModel):
    columns:     List[str]        = Field(min_length=1, max_length=50)
    sample_rows: List[dict]       = Field(default=[], max_length=10)


def _parse_file_to_records(filename: str, contents: bytes) -> tuple[str, list[dict]]:
    """Parse file bytes → (format_str, records list). Raises HTTPException on error."""
    if filename.endswith(".xlsx"):
        df = pd.read_excel(io.BytesIO(contents))
        return "excel", df.to_dict("records")
    elif filename.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(contents), encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(contents), encoding="latin-1")
        return "csv", df.to_dict("records")
    elif filename.endswith(".parquet"):
        df = pd.read_parquet(io.BytesIO(contents))
        return "parquet", df.to_dict("records")
    elif filename.endswith(".json") or filename.endswith(".jsonld"):
        data = json.loads(contents.decode("utf-8"))
        if isinstance(data, dict):
            records = next((v for v in data.values() if isinstance(v, list)), [data])
        else:
            records = data if isinstance(data, list) else []
        return "json", records
    elif filename.endswith(".xml"):
        root = ET.fromstring(contents.decode("utf-8"))
        records = []
        for child in root:
            record = {sub.tag: sub.text for sub in child}
            if record:
                records.append(record)
        return "xml", records
    elif filename.endswith(".rdf") or filename.endswith(".ttl"):
        import rdflib
        g = rdflib.Graph()
        fmt = "ttl" if filename.endswith(".ttl") else "xml"
        g.parse(data=contents.decode("utf-8"), format=fmt)
        entities: dict = {}
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
        return "rdf", list(entities.values())
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format for tabular parsing.")


def _parse_science_import(filename: str, contents: bytes) -> ScientificImportResult:
    text = contents.decode("utf-8", errors="replace")
    result = detect_scientific_import(filename, text)
    if result is not None:
        return result
    raise HTTPException(status_code=400, detail="Unsupported science import format.")


def _try_parse_science_import(filename: str, contents: bytes) -> ScientificImportResult | None:
    text = contents.decode("utf-8", errors="replace")
    return detect_scientific_import(filename, text)


def _parse_science_records(filename: str, contents: bytes) -> tuple[str, list[dict]]:
    result = _parse_science_import(filename, contents)
    return result.format, result.to_legacy_records()


def _record_virtual_field(target: dict, field_name: str, value) -> None:
    """Persist wizard-only virtual fields into attributes_json-compatible data."""
    if value is None:
        return

    text_value = str(value)
    target[field_name] = text_value

    if field_name == "creation_date":
        match = re.search(r"\b(19\d{2}|20\d{2})\b", text_value)
        if match and "year" not in target:
            target["year"] = int(match.group(1))


def _infer_entity_type_hint(records: list[dict]) -> Optional[str]:
    counts: dict[str, int] = {}
    for row in records:
        if not isinstance(row, dict):
            continue
        raw = row.get("entity_type")
        if raw is None:
            continue
        value = str(raw).strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: item[1])[0]


def _create_import_batch(
    db: Session,
    *,
    org_id: int | None,
    domain_id: str,
    source_type: str,
    file_name: str,
    file_format: str,
    total_rows: int,
    entity_type_hint: Optional[str],
    created_by: int | None,
    source_label: Optional[str] = None,
) -> models.ImportBatch:
    batch = models.ImportBatch(
        org_id=org_id,
        domain_id=domain_id,
        source_type=source_type,
        file_name=file_name,
        file_format=file_format,
        source_label=source_label,
        total_rows=total_rows,
        entity_type_hint=entity_type_hint,
        created_by=created_by,
        created_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.flush()
    return batch


# ── LLM-assisted mapping suggestion (Sprint 74) ───────────────────────────────

@router.post("/upload/suggest-mapping")
def suggest_column_mapping(
    payload: SuggestMappingRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Sprint 74 — LLM-Assisted Column Mapping.
    Accepts column names + sample rows, asks the active LLM to suggest the best
    UKIP model field for each column, and returns:
      {
        "mapping":   {"ColName": "ukip_field" | null, ...},
        "provider":  "openai" | "anthropic" | ... | null,
        "available": true | false,
      }

    If no AI integration is active, returns available=false with an empty mapping
    (200 OK — the frontend degrades gracefully).
    """
    integration = _get_active_integration(db)
    if not integration:
        return {"mapping": {col: None for col in payload.columns}, "provider": None, "available": False}

    # Build adapter (same factory used by the RAG engine)
    from backend.analytics.rag_engine import _build_adapter
    adapter = _build_adapter(integration)
    if not adapter:
        return {"mapping": {col: None for col in payload.columns}, "provider": None, "available": False}

    # Collect up to 3 sample values per column
    samples: dict[str, list] = {col: [] for col in payload.columns}
    for row in payload.sample_rows[:10]:
        for col in payload.columns:
            raw_val = row.get(col)
            if raw_val is not None and str(raw_val).strip() and len(samples[col]) < 3:
                samples[col].append(str(raw_val).strip()[:80])

    # Format user prompt
    lines = ["Map the following columns to UKIP fields:\n"]
    for col in payload.columns:
        sv = samples[col]
        sample_str = ", ".join(f'"{v}"' for v in sv) if sv else "(no samples)"
        lines.append(f'  "{col}": samples → {sample_str}')
    user_prompt = "\n".join(lines)

    try:
        raw_response = adapter.chat(
            system_prompt=_SUGGEST_SYSTEM_PROMPT,
            user_query=user_prompt,
            context_chunks=[],
        )
    except Exception as exc:
        logger.warning("LLM suggest-mapping error: %s", exc)
        return {"mapping": {col: None for col in payload.columns}, "provider": adapter.provider_name, "available": True}

    mapping = _parse_llm_mapping(raw_response, _VALID_UKIP_FIELDS)

    # Fill any missing columns (LLM may have omitted some)
    for col in payload.columns:
        if col not in mapping:
            mapping[col] = None

    return {
        "mapping":   mapping,
        "provider":  adapter.provider_name,
        "available": True,
    }


# ── Preview endpoint (Sprint 71) ───────────────────────────────────────────────

@router.post("/upload/preview")
async def preview_upload(
    file: UploadFile = File(...),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Sprint 71 — Bulk Import Wizard step 2.
    Parse the file without importing and return:
      format, row_count, columns, sample_rows (first 5), auto_mapping, is_science_format
    """
    filename = file.filename.lower()
    contents = await file.read()

    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum 20 MB.")

    # Science formats have fixed semantic mapping
    try:
        science_import = _try_parse_science_import(filename, contents)
        if science_import is not None:
            records = science_import.to_legacy_records()
            return {
                "format": science_import.format,
                "provider": science_import.provider,
                "row_count": len(records),
                "columns": list(_SCIENCE_AUTO_MAPPING.keys()),
                "sample_rows": [
                    {k: v for k, v in r.items() if k in _SCIENCE_AUTO_MAPPING}
                    for r in records[:5]
                ],
                "auto_mapping": _SCIENCE_AUTO_MAPPING,
                "is_science_format": True,
            }
        if filename.endswith(".bib") or filename.endswith(".ris"):
            raise HTTPException(status_code=400, detail="Unsupported science import format.")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")

    try:
        _fmt, tabular_records = _parse_file_to_records(filename, contents)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")

    if not tabular_records:
        return {
            "format": _fmt,
            "row_count": 0,
            "columns": [],
            "sample_rows": [],
            "auto_mapping": {},
            "is_science_format": False,
        }

    # Detect all columns from first 100 rows
    all_cols: set = set()
    for row in tabular_records[:100]:
        if isinstance(row, dict):
            all_cols.update(str(k) for k in row.keys())

    stripped_mapping = {k.strip(): v for k, v in COLUMN_MAPPING.items()}
    valid_model_keys = set(COLUMN_MAPPING.values())

    auto_mapping = {}
    for col in all_cols:
        sk = col.strip()
        if sk in stripped_mapping:
            auto_mapping[col] = stripped_mapping[sk]
        elif sk in valid_model_keys:
            auto_mapping[col] = sk
        else:
            auto_mapping[col] = None  # unmatched — user must decide

    # Sanitize sample rows (replace NaN with None)
    def _clean(v):
        try:
            import math
            if isinstance(v, float) and math.isnan(v):
                return None
        except Exception:
            pass
        return v

    sample = [
        {str(k): _clean(v) for k, v in row.items()}
        for row in tabular_records[:5]
        if isinstance(row, dict)
    ]

    return {
        "format": _fmt,
        "row_count": len(tabular_records),
        "columns": sorted(all_cols),
        "sample_rows": sample,
        "auto_mapping": auto_mapping,
        "is_science_format": False,
    }


async def _materialize_graph(
    *,
    request: Request,
    db,
    import_batch_id: int,
    org_id: int | None,
    domain: str,
) -> dict:
    """
    Route graph materialization to the Rust engine or the Python fallback.

    Modes (controlled by env vars):
    - ENGINE_SHADOW_MODE=true  → Python runs (correctness), engine fires async for comparison
    - ENGINE_SHADOW_MODE=false → engine sync (if available), fallback to Python on failure
    - No engine configured    → Python only (legacy behavior)
    """
    engine = getattr(request.app.state, "engine_client", None)

    # No engine → Python fallback only
    if not engine_bridge.should_use_engine(engine):
        return materialize_scientific_import_graph(db, import_batch_id, org_id=org_id)

    # Query saved entities to build proto Publications (need DB ids)
    from backend import models as _models
    entities = (
        db.query(_models.RawEntity)
        .filter(
            _models.RawEntity.import_batch_id == import_batch_id,
            _models.RawEntity.org_id == org_id,
            _models.RawEntity.source != "graph_materializer",
        )
        .all()
    )

    publications = [engine_bridge.entity_to_publication(e) for e in entities]

    if engine_bridge.shadow_mode_enabled():
        # Shadow mode: Python is primary, engine fires async for telemetry
        python_result = materialize_scientific_import_graph(db, import_batch_id, org_id=org_id)
        import asyncio as _asyncio
        _asyncio.ensure_future(_shadow_engine_call(
            engine=engine,
            import_batch_id=import_batch_id,
            org_id=org_id,
            domain=domain,
            publications=publications,
            python_result=python_result,
        ))
        return {**python_result, "engine_mode": "shadow"}

    # Primary mode: try engine first, fall back to Python
    import uuid as _uuid
    job_id = f"ingest-{import_batch_id}-{_uuid.uuid4().hex[:8]}"
    threshold = engine_bridge.sync_threshold()
    try:
        if len(publications) <= threshold:
            resp = await engine.process_sync(
                pipeline="graph_materialization",
                job_id=job_id,
                import_batch_id=import_batch_id,
                domain=domain,
                publications=publications,
                org_id=org_id,
            )
        else:
            resp = await engine.process_async(
                pipeline="graph_materialization",
                job_id=job_id,
                import_batch_id=import_batch_id,
                domain=domain,
                publications=publications,
                org_id=org_id,
            )
        if resp is not None:
            result = resp.result if hasattr(resp, "result") and resp.result else None
            return {
                "publications": len(publications),
                "nodes_created": result.nodes_created if result else 0,
                "relationships_created": result.relationships_created if result else 0,
                "engine_mode": "primary",
                "engine_job_id": job_id,
            }
    except Exception as exc:
        logger.warning("Engine graph materialization failed, falling back to Python: %s", exc)

    if engine_bridge.fallback_enabled():
        logger.info("Falling back to Python graph_materializer for batch %s", import_batch_id)
        return {**materialize_scientific_import_graph(db, import_batch_id, org_id=org_id), "engine_mode": "fallback"}

    return {"publications": len(publications), "nodes_created": 0, "relationships_created": 0, "engine_mode": "skipped"}


async def _shadow_engine_call(
    *,
    engine,
    import_batch_id: int,
    org_id: int | None,
    domain: str,
    publications: list,
    python_result: dict,
) -> None:
    """Fire-and-forget shadow call to the engine for telemetry comparison."""
    import uuid as _uuid
    job_id = f"shadow-{import_batch_id}-{_uuid.uuid4().hex[:8]}"
    try:
        resp = await engine.process_sync(
            pipeline="graph_materialization",
            job_id=job_id,
            import_batch_id=import_batch_id,
            domain=domain,
            publications=publications,
            org_id=org_id,
        )
        if resp and resp.result:
            r = resp.result
            logger.info(
                "Shadow engine result for batch %s: nodes=%s rels=%s | Python: nodes=%s rels=%s",
                import_batch_id,
                r.nodes_created,
                r.relationships_created,
                python_result.get("nodes_created", "?"),
                python_result.get("relationships_created", "?"),
            )
    except Exception as exc:
        logger.debug("Shadow engine call failed (non-critical): %s", exc)


@router.post("/upload", status_code=201)
@limiter.limit("60/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    domain: str = Form("default"),
    field_mapping: str = Form("{}"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    stored_org_id = persisted_org_id(org_id)
    filename = file.filename.lower()
    allowed_extensions = (
        ".xlsx", ".csv", ".json", ".xml", ".parquet",
        ".jsonld", ".rdf", ".ttl", ".bib", ".ris", ".txt",
    )
    if not any(filename.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format. Allowed: {', '.join(allowed_extensions)}",
        )

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is 20 MB "
                   f"(received {len(contents) // (1024*1024)} MB).",
        )

    # Parse custom field mapping from wizard (JSON string)
    try:
        custom_mapping: dict = json.loads(field_mapping) if field_mapping else {}
    except json.JSONDecodeError:
        custom_mapping = {}

    # ── Science formats: fixed mapping ────────────────────────────────────────
    science_import = _try_parse_science_import(filename, contents)
    if science_import is None and (filename.endswith(".bib") or filename.endswith(".ris")):
        raise HTTPException(status_code=400, detail="Unsupported science import format.")
    if science_import is not None:
        # Science formats default to "science" domain when none is specified
        effective_domain = domain if domain and domain != "default" else "science"

        import_batch = _create_import_batch(
            db,
            org_id=stored_org_id,
            domain_id=effective_domain,
            source_type=f"science_upload:{science_import.provider}",
            file_name=file.filename,
            file_format=science_import.format,
            total_rows=science_import.total_rows,
            entity_type_hint="publication",
            created_by=current_user.id,
            source_label=f"{file.filename} · {science_import.provider.upper()} · {science_import.format.upper()}",
        )
        objects = []
        for publication in science_import.records:
            entity_data = publication.to_entity_kwargs(domain=effective_domain)
            entity_data["domain"] = effective_domain
            entity_data["org_id"] = stored_org_id
            entity_data["import_batch_id"] = import_batch.id
            objects.append(models.RawEntity(**entity_data))

        for i in range(0, len(objects), _CHUNK_SIZE):
            db.bulk_save_objects(objects[i : i + _CHUNK_SIZE])
        audit_details = {
            "filename": file.filename,
            "rows": len(objects),
            "format": science_import.format,
            "provider": science_import.provider,
            "import_batch_id": import_batch.id,
        }
        _audit(db, "upload", user_id=current_user.id, details=audit_details)
        db.commit()

        graph_result = await _materialize_graph(
            request=request,
            db=db,
            import_batch_id=import_batch.id,
            org_id=stored_org_id,
            domain=effective_domain,
        )

        _dispatch_webhook("upload", {"filename": file.filename, "rows": len(objects), "import_batch_id": import_batch.id},
                          database.SessionLocal)
        return {
            "message": f"Successfully imported {len(objects)} publications from {science_import.provider.upper()}",
            "total_rows": len(objects),
            "format": science_import.format,
            "provider": science_import.provider,
            "domain": effective_domain,
            "import_batch_id": import_batch.id,
            "source_label": import_batch.source_label,
            "matched_columns": list(_SCIENCE_AUTO_MAPPING.keys()),
            "unmatched_columns": [],
            "graph": graph_result,
        }

    # ── Tabular formats ────────────────────────────────────────────────────────
    try:
        _fmt, records = _parse_file_to_records(filename, contents)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to process file: {str(exc)}")

    if not records:
        return {
            "message": "No valid data found or file is empty",
            "total_rows": 0,
            "matched_columns": [],
            "unmatched_columns": [],
        }

    if len(records) > _MAX_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"File contains too many rows ({len(records):,}). "
                   f"Maximum allowed is {_MAX_ROWS:,} rows per upload.",
        )

    # Build effective mapping: custom_mapping takes priority over COLUMN_MAPPING
    stripped_mapping = {k.strip(): v for k, v in COLUMN_MAPPING.items()}
    valid_model_keys = set(COLUMN_MAPPING.values()) | set(MAPPABLE_MODEL_FIELDS)

    effective_mapping = {**stripped_mapping, **{k.strip(): v for k, v in custom_mapping.items()}}

    all_keys: set = set()
    for row in records[:100]:
        if isinstance(row, dict):
            all_keys.update(row.keys())

    matched_columns: set = set()
    unmatched_columns: set = set()
    for col in all_keys:
        col_str = str(col).strip()
        mapped = effective_mapping.get(col_str)
        if mapped and mapped in valid_model_keys:
            matched_columns.add(col_str)
        elif col_str in valid_model_keys:
            matched_columns.add(col_str)
        else:
            unmatched_columns.add(col_str)

    import_batch = _create_import_batch(
        db,
        org_id=stored_org_id,
        domain_id=domain,
        source_type="tabular_upload",
        file_name=file.filename,
        file_format=_fmt,
        total_rows=len(records),
        entity_type_hint=_infer_entity_type_hint(records),
        created_by=current_user.id,
        source_label=f"{file.filename} · {_fmt.upper()}",
    )

    objects = []
    for row in records:
        if not isinstance(row, dict):
            continue

        row_data: dict = {"domain": domain, "org_id": stored_org_id, "import_batch_id": import_batch.id}
        unmatched_data: dict = {}
        virtual_field_data: dict = {}

        for k, val in row.items():
            val = normalize_import_value(val)
            is_nan = False
            if type(val) is float and math.isnan(val):
                is_nan = True
            elif pd.isna(val) if hasattr(pd, "isna") else False:
                try:
                    if pd.isna(val):
                        is_nan = True
                except (TypeError, ValueError):
                    pass
            if is_nan:
                val = None

            sk = str(k).strip()
            # "" means skip this column (wizard user chose "ignore")
            mapped_field = effective_mapping.get(sk)
            if mapped_field == "" or mapped_field is None and sk not in valid_model_keys:
                if mapped_field != "":  # only store if not explicitly skipped
                    unmatched_data[sk] = val
            elif mapped_field == "domain":
                # The wizard's selected domain is authoritative for the batch.
                # Source "domain" columns are retained as metadata so a blank or
                # inconsistent cell cannot fragment dashboard metrics.
                unmatched_data[sk] = val
            elif mapped_field in _VIRTUAL_MODEL_FIELDS:
                _record_virtual_field(virtual_field_data, mapped_field, val)
            elif mapped_field:
                row_data[mapped_field] = str(normalize_import_value(val)) if val is not None else None
            elif sk in _VIRTUAL_MODEL_FIELDS:
                _record_virtual_field(virtual_field_data, sk, val)
            elif sk in valid_model_keys:
                row_data[sk] = str(normalize_import_value(val)) if val is not None else None
            else:
                unmatched_data[sk] = val

        if virtual_field_data:
            row_data["attributes_json"] = json.dumps(
                virtual_field_data,
                default=str,
                ensure_ascii=False,
            )

        if unmatched_data:
            row_data["normalized_json"] = json.dumps(
                unmatched_data, default=str, ensure_ascii=False
            )

        objects.append(models.RawEntity(**row_data))

    for i in range(0, len(objects), _CHUNK_SIZE):
        db.bulk_save_objects(objects[i : i + _CHUNK_SIZE])
    _audit(
        db, "upload",
        user_id=current_user.id,
        details={"filename": file.filename, "rows": len(objects), "import_batch_id": import_batch.id},
    )
    db.commit()
    _dispatch_webhook(
        "upload",
        {"filename": file.filename, "rows": len(objects), "import_batch_id": import_batch.id},
        database.SessionLocal,
    )

    return {
        "message": f"Successfully imported {len(objects)} entities",
        "total_rows": len(objects),
        "domain": domain,
        "format": _fmt,
        "import_batch_id": import_batch.id,
        "source_label": import_batch.source_label,
        "matched_columns": list(matched_columns),
        "unmatched_columns": list(unmatched_columns),
    }


@router.post("/analyze")
async def analyze_datasource(
    file: UploadFile = File(...),
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    """
    Analyzes the structure (columns, keys, tags, predicates) of a given file.
    Supports CSV, Excel, JSON, XML, Parquet, RDF, Logs, etc.
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if not ext:
        raise HTTPException(
            status_code=400, detail="File must have an extension to be analyzed"
        )

    fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        structure = DataSourceAnalyzer.analyze(temp_path)
        return {
            "filename": file.filename,
            "format": ext.strip("."),
            "structure": structure,
            "count": len(structure),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Error analyzing file '%s'", file.filename)
        raise HTTPException(
            status_code=500, detail="Error analyzing file. Check server logs for details."
        )
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/export")
def export_entities(
    search: str = None,
    limit: int = Query(default=5000, ge=1, le=50000),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    org_id = resolve_request_org_id(db, current_user)
    query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                models.RawEntity.primary_label.ilike(search_filter),
                models.RawEntity.canonical_id.ilike(search_filter),
                models.RawEntity.secondary_label.ilike(search_filter),
                models.RawEntity.entity_type.ilike(search_filter),
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
        headers={"Content-Disposition": "attachment; filename=entities_export.xlsx"},
    )
