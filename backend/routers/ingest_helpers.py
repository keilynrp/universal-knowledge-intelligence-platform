"""
Helper functions, constants, and Pydantic models for the ingest router.

Extracted from ingest.py to keep the endpoint file focused on route handlers.
"""
import io
import json
import logging
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend import models
from backend.importers.scientific import ScientificImportResult, detect_scientific_import
from backend.services.graph_materializer import materialize_scientific_import_graph
from backend.services import engine_bridge

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

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
    "primary_label":             "main name/title of the entity (publication title, dataset title, person name, organization name)",
    "secondary_label":           "secondary label (author, institution, publisher, venue, organization, source label)",
    "canonical_id":              "stable identifier (DOI, ORCID, ROR, ISBN, ISSN, accession number, local record ID)",
    "entity_type":               "type or category of the entity (publication, dataset, person, organization, concept, place…)",
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


# ── Pydantic model for suggest-mapping ────────────────────────────────────────

class SuggestMappingRequest(BaseModel):
    columns:     List[str]        = Field(min_length=1, max_length=50)
    sample_rows: List[dict]       = Field(default=[], max_length=10)


# ── Helper functions ─────────────────────────────────────────────────────────

def _dedup_before_insert(
    db: Session,
    objects: list[models.RawEntity],
    *,
    org_id: int | None,
) -> tuple[list[models.RawEntity], int]:
    """Remove entities whose ``(domain, entity_type, canonical_id)`` already
    exists in the DB or appears earlier in the same batch.

    Returns ``(deduplicated_list, skipped_count)``."""
    if not objects:
        return objects, 0

    existing_keys: set[tuple[str, str, str]] = set()
    candidate_cids = [
        obj.canonical_id for obj in objects
        if obj.canonical_id and obj.entity_type
    ]
    if candidate_cids:
        q = db.query(
            models.RawEntity.domain,
            models.RawEntity.entity_type,
            models.RawEntity.canonical_id,
        ).filter(
            models.RawEntity.canonical_id.in_(candidate_cids),
            models.RawEntity.entity_type.isnot(None),
        )
        if org_id is not None:
            q = q.filter(models.RawEntity.org_id == org_id)
        for row in q:
            existing_keys.add((row[0] or "", row[1], row[2]))

    seen_in_batch: set[tuple[str, str, str]] = set()
    kept: list[models.RawEntity] = []
    skipped = 0

    for obj in objects:
        cid = obj.canonical_id
        etype = obj.entity_type
        if cid and etype:
            key = (obj.domain or "", etype, cid)
            if key in existing_keys or key in seen_in_batch:
                skipped += 1
                continue
            seen_in_batch.add(key)
        kept.append(obj)

    if skipped:
        logger.info("Import dedup: skipped %d duplicate(s) out of %d", skipped, len(objects))

    return kept, skipped


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


def _parse_file_to_records(filename: str, contents: bytes) -> tuple[str, list[dict]]:
    """Parse file bytes -> (format_str, records list). Raises HTTPException on error."""
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
    - ENGINE_SHADOW_MODE=true  -> Python runs (correctness), engine fires async for comparison
    - ENGINE_SHADOW_MODE=false -> engine sync (if available), fallback to Python on failure
    - No engine configured    -> Python only (legacy behavior)
    """
    engine = getattr(request.app.state, "engine_client", None)

    # No engine -> Python fallback only
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
