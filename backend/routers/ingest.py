"""
Data ingestion and export endpoints.
  POST /upload
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
import xml.etree.ElementTree as ET

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend import database, models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.datasource_analyzer import DataSourceAnalyzer
from backend.parsers.bibtex_parser import parse_bibtex
from backend.parsers.ris_parser import parse_ris
from backend.parsers.science_mapper import science_record_to_entity
from backend.routers.column_maps import COLUMN_MAPPING, EXPORT_COLUMN_MAPPING
from backend.routers.deps import _audit, _dispatch_webhook

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

_SCIENCE_AUTO_MAPPING = {
    "title":    "primary_label",
    "authors":  "secondary_label",
    "doi":      "enrichment_doi",
    "keywords": "enrichment_concepts",
    "year":     "creation_date",
    "journal":  "secondary_label",
}


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

    # Science formats: BibTeX and RIS have fixed semantic mapping
    try:
        if filename.endswith(".bib"):
            records = parse_bibtex(contents.decode("utf-8", errors="replace"))
            return {
                "format": "bibtex",
                "row_count": len(records),
                "columns": list(_SCIENCE_AUTO_MAPPING.keys()),
                "sample_rows": [
                    {k: v for k, v in r.items() if k in _SCIENCE_AUTO_MAPPING}
                    for r in records[:5]
                ],
                "auto_mapping": _SCIENCE_AUTO_MAPPING,
                "is_science_format": True,
            }
        elif filename.endswith(".ris"):
            records = parse_ris(contents.decode("utf-8", errors="replace"))
            return {
                "format": "ris",
                "row_count": len(records),
                "columns": list(_SCIENCE_AUTO_MAPPING.keys()),
                "sample_rows": [
                    {k: v for k, v in r.items() if k in _SCIENCE_AUTO_MAPPING}
                    for r in records[:5]
                ],
                "auto_mapping": _SCIENCE_AUTO_MAPPING,
                "is_science_format": True,
            }
    except Exception as exc:
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


@router.post("/upload", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    domain: str = Form("default"),
    field_mapping: str = Form("{}"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    filename = file.filename.lower()
    allowed_extensions = (
        ".xlsx", ".csv", ".json", ".xml", ".parquet",
        ".jsonld", ".rdf", ".ttl", ".bib", ".ris",
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
    if filename.endswith(".bib") or filename.endswith(".ris"):
        # Science formats default to "science" domain when none is specified
        effective_domain = domain if domain and domain != "default" else "science"
        try:
            science_records = (
                parse_bibtex(contents.decode("utf-8", errors="replace"))
                if filename.endswith(".bib")
                else parse_ris(contents.decode("utf-8", errors="replace"))
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")

        objects = []
        for r in science_records:
            entity_data = science_record_to_entity(r)
            entity_data["domain"] = effective_domain
            objects.append(models.RawEntity(**entity_data))

        fmt = "bibtex" if filename.endswith(".bib") else "ris"
        for i in range(0, len(objects), _CHUNK_SIZE):
            db.bulk_save_objects(objects[i : i + _CHUNK_SIZE])
        _audit(db, "upload", user_id=current_user.id,
               details={"filename": file.filename, "rows": len(objects), "format": fmt})
        db.commit()
        _dispatch_webhook("upload", {"filename": file.filename, "rows": len(objects)},
                          database.SessionLocal)
        return {
            "message": f"Successfully imported {len(objects)} publications from {fmt.upper()}",
            "total_rows": len(objects),
            "format": fmt,
            "domain": effective_domain,
            "matched_columns": list(_SCIENCE_AUTO_MAPPING.keys()),
            "unmatched_columns": [],
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

    objects = []
    for row in records:
        if not isinstance(row, dict):
            continue

        row_data: dict = {"domain": domain}
        unmatched_data: dict = {}

        for k, val in row.items():
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
            elif mapped_field:
                row_data[mapped_field] = str(val) if val is not None else None
            elif sk in valid_model_keys:
                row_data[sk] = str(val) if val is not None else None
            else:
                unmatched_data[sk] = val

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
        details={"filename": file.filename, "rows": len(objects)},
    )
    db.commit()
    _dispatch_webhook(
        "upload",
        {"filename": file.filename, "rows": len(objects)},
        database.SessionLocal,
    )

    return {
        "message": f"Successfully imported {len(objects)} entities",
        "total_rows": len(objects),
        "domain": domain,
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
    _: models.User = Depends(require_role("super_admin", "admin", "editor")),
):
    query = db.query(models.RawEntity)

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
