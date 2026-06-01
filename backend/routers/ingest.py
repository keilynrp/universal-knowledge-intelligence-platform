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
import shutil
import tempfile
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend import database, models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.routers.limiter import limiter
from backend.datasource_analyzer import DataSourceAnalyzer
from backend.routers.column_maps import COLUMN_MAPPING, EXPORT_COLUMN_MAPPING
from backend.routers.deps import _audit, _dispatch_webhook, _get_active_integration
from backend.services.field_correspondence import (
    infer_source_schema,
    resolve_field_correspondence,
    resolve_field_mapping,
)
from backend.services.mapping_suggestions import MappingSuggestionService
from backend.services.source_profiler import FieldProfile, SourceProfile
from backend.services.text_normalization import normalize_import_value
from backend.tenant_access import persisted_org_id, resolve_request_org_id, scope_query_to_org

from backend.routers.ingest_helpers import (
    _MAX_UPLOAD_BYTES,
    _MAX_ROWS,
    _CHUNK_SIZE,
    MAPPABLE_MODEL_FIELDS,
    _VIRTUAL_MODEL_FIELDS,
    _SCIENCE_AUTO_MAPPING,
    _FIELD_DESCRIPTIONS,
    _VALID_UKIP_FIELDS,
    _SUGGEST_SYSTEM_PROMPT,
    SuggestMappingRequest,
    _dedup_before_insert,
    _parse_llm_mapping,
    _parse_file_to_records,
    _parse_science_import,
    _try_parse_science_import,
    _parse_science_records,
    _record_virtual_field,
    _infer_entity_type_hint,
    _create_import_batch,
    _materialize_graph,
    _shadow_engine_call,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])


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

    valid_model_keys = set(COLUMN_MAPPING.values())

    source_schema = infer_source_schema(filename, all_cols)
    auto_mapping = {}
    for col in all_cols:
        sk = col.strip()
        resolved = resolve_field_mapping(
            sk,
            domain="science" if filename.endswith((".bib", ".ris", ".txt")) else None,
            source_schema=source_schema,
        )
        if resolved:
            auto_mapping[col] = resolved
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
        "source_schema": source_schema,
        "row_count": len(tabular_records),
        "columns": sorted(all_cols),
        "sample_rows": sample,
        "auto_mapping": auto_mapping,
        "is_science_format": False,
    }


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

        objects, dedup_skipped = _dedup_before_insert(db, objects, org_id=stored_org_id)

        for i in range(0, len(objects), _CHUNK_SIZE):
            db.bulk_save_objects(objects[i : i + _CHUNK_SIZE])
        audit_details = {
            "filename": file.filename,
            "rows": len(objects),
            "duplicates_skipped": dedup_skipped,
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
            "message": f"Successfully imported {len(objects)} publications from {science_import.provider.upper()}"
                       + (f" ({dedup_skipped} duplicates skipped)" if dedup_skipped else ""),
            "total_rows": len(objects),
            "duplicates_skipped": dedup_skipped,
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
    valid_model_keys = set(COLUMN_MAPPING.values()) | set(MAPPABLE_MODEL_FIELDS)

    effective_mapping = {
        str(k).strip(): v
        for k, v in custom_mapping.items()
    }

    all_keys: set = set()
    for row in records[:100]:
        if isinstance(row, dict):
            all_keys.update(row.keys())
    source_schema = infer_source_schema(file.filename, {str(key) for key in all_keys})
    mapping_service = MappingSuggestionService(db=db, org_id=stored_org_id)

    matched_columns: set = set()
    unmatched_columns: set = set()
    for col in all_keys:
        col_str = str(col).strip()
        mapped = effective_mapping.get(col_str)
        if mapped is None:
            mapped, _metadata = mapping_service.resolve_field_target(
                col_str,
                source_schema=source_schema,
                org_id=stored_org_id,
            )
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
    field_samples: dict[str, list[str]] = {str(key): [] for key in all_keys}
    for sample_row in records[:20]:
        if not isinstance(sample_row, dict):
            continue
        for key, value in sample_row.items():
            sample_key = str(key).strip()
            if sample_key in field_samples and len(field_samples[sample_key]) < 3:
                normalized_sample = normalize_import_value(value)
                if normalized_sample not in (None, ""):
                    field_samples[sample_key].append(str(normalized_sample))
    mapping_service.generate_suggestions(
        SourceProfile(
            source_id=f"import_batch:{import_batch.id}",
            source_format=file.filename,
            total_rows=len(records),
            field_profiles=[
                FieldProfile(field_name=field, sample_values=samples)
                for field, samples in sorted(field_samples.items())
            ],
        ),
        org_id=stored_org_id,
        import_batch_id=import_batch.id,
    )

    objects = []
    for row in records:
        if not isinstance(row, dict):
            continue

        row_data: dict = {"domain": domain, "org_id": stored_org_id, "import_batch_id": import_batch.id}
        unmatched_data: dict = {}
        virtual_field_data: dict = {}
        field_correspondence_data: dict = {}

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
            metadata: dict = {}
            if mapped_field is None:
                mapped_field, metadata = mapping_service.resolve_field_target(
                    sk,
                    source_schema=source_schema,
                    org_id=stored_org_id,
                )
                correspondence = resolve_field_correspondence(sk, domain=domain, source_schema=source_schema)
            else:
                correspondence = resolve_field_correspondence(sk, domain=domain, source_schema=source_schema)
                if correspondence and correspondence.canonical_target != mapped_field:
                    correspondence = None
            if mapped_field and metadata and "approved_field_correspondence_rule" in metadata.get("evidence", []):
                field_correspondence_data[sk] = {
                    "target": mapped_field,
                    "concept": metadata.get("semantic_concept"),
                    "scheme": metadata.get("identifier_scheme"),
                    "confidence": metadata.get("confidence"),
                    "evidence": metadata.get("evidence", []),
                    "requires_review": metadata.get("requires_review", False),
                }
            elif correspondence:
                field_correspondence_data[sk] = correspondence.to_provenance()
            elif mapped_field and metadata:
                field_correspondence_data[sk] = {
                    "target": mapped_field,
                    "concept": metadata.get("semantic_concept"),
                    "scheme": metadata.get("identifier_scheme"),
                    "confidence": metadata.get("confidence"),
                    "evidence": metadata.get("evidence", []),
                    "requires_review": metadata.get("requires_review", False),
                }
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

        if field_correspondence_data:
            virtual_field_data["_field_correspondence"] = field_correspondence_data

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

    objects, dedup_skipped = _dedup_before_insert(db, objects, org_id=stored_org_id)

    for i in range(0, len(objects), _CHUNK_SIZE):
        db.bulk_save_objects(objects[i : i + _CHUNK_SIZE])
    _audit(
        db, "upload",
        user_id=current_user.id,
        details={"filename": file.filename, "rows": len(objects), "duplicates_skipped": dedup_skipped, "import_batch_id": import_batch.id},
    )
    db.commit()
    _dispatch_webhook(
        "upload",
        {"filename": file.filename, "rows": len(objects), "import_batch_id": import_batch.id},
        database.SessionLocal,
    )

    return {
        "message": f"Successfully imported {len(objects)} entities"
                   + (f" ({dedup_skipped} duplicates skipped)" if dedup_skipped else ""),
        "total_rows": len(objects),
        "duplicates_skipped": dedup_skipped,
        "domain": domain,
        "format": _fmt,
        "source_schema": source_schema,
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
