"""
Demo Mode endpoints.
  GET    /demo/status  — check if demo data is loaded
  POST   /demo/seed    — load pre-generated demo entities (admin+)
  DELETE /demo/reset   — remove demo entities (admin+)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.auth import get_current_user, require_role
from backend.database import get_db
from backend.tenant_access import persisted_org_id, resolve_request_org_id

logger = logging.getLogger(__name__)

router = APIRouter()

# Relative to project root (where the process is started from)
_DEMO_FILE = Path("data/demo/demo_entities.xlsx")
_SNAPSHOT_FILE = Path("data/demo/openalex_snapshot.json")
_OPENALEX_CONCEPT_ID = "C41008148"  # "Knowledge Management"
_OPENALEX_DEMO_LIMIT = 1_000

_SEED_CHUNK = 500
_DEMO_BATCH_SOURCE_TYPE = "demo"
_DEMO_BATCH_SOURCE_LABEL = "UKIP Demo Dataset"
_DEMO_PORTAL_SLUG = "ukip-demo-catalog"
_DEMO_PORTAL_TITLE = "Portal demo UKIP"
_DEMO_PORTAL_DESCRIPTION = (
    "Portal de descubrimiento generado automáticamente desde la demo UKIP "
    "para explorar un corpus científico pregenerado."
)

_SHOWCASE_CLUSTERS = (
    {
        "slug": "ai-research-assessment",
        "label": "AI-assisted research assessment",
        "publisher": "Journal of Research Intelligence",
        "concepts": [
            "scientific intelligence",
            "research assessment",
            "responsible metrics",
            "machine learning",
            "decision support",
        ],
        "titles": [
            "Human-in-the-loop evidence synthesis for research portfolio decisions",
            "Responsible metric design for AI-assisted science policy",
            "Benchmarking institutional research signals with explainable indicators",
            "Decision support workflows for scientific intelligence platforms",
            "Trust calibration in automated research assessment systems",
            "Mapping uncertainty in machine-assisted evidence briefs",
        ],
    },
    {
        "slug": "open-science-quality",
        "label": "Open science and reproducibility quality",
        "publisher": "Open Science Analytics",
        "concepts": [
            "open science",
            "reproducibility",
            "data quality",
            "research integrity",
            "evidence governance",
        ],
        "titles": [
            "Reproducibility signals as operational quality controls",
            "Open science readiness across institutional research domains",
            "Data availability patterns in high-impact scientific corpora",
            "Governance models for reusable research evidence",
            "Quality gaps in cross-domain research knowledge bases",
            "Operational indicators for transparent scientific outputs",
        ],
    },
    {
        "slug": "bibliometric-networks",
        "label": "Bibliometric and knowledge graph networks",
        "publisher": "Scientometrics Systems Review",
        "concepts": [
            "bibliometrics",
            "knowledge graphs",
            "citation networks",
            "topic modeling",
            "research impact",
        ],
        "titles": [
            "Knowledge graph methods for emerging topic detection",
            "Citation network dynamics in interdisciplinary research portfolios",
            "Topic drift indicators for scientific intelligence dashboards",
            "Graph-based discovery of institutional research strengths",
            "Impact projection from citation and concept trajectories",
            "Signal fusion methods for bibliometric monitoring",
        ],
    },
    {
        "slug": "science-policy-translation",
        "label": "Science policy translation",
        "publisher": "Policy Evidence Quarterly",
        "concepts": [
            "science policy",
            "technology transfer",
            "research translation",
            "innovation systems",
            "stakeholder briefs",
        ],
        "titles": [
            "From research signals to executive science briefs",
            "Evidence packaging for policy and innovation stakeholders",
            "Translational readiness metrics in university research portfolios",
            "Institutional decision models for strategic scientific investments",
            "Aligning research intelligence with stakeholder action cycles",
            "Portfolio narratives for high-confidence science policy decisions",
        ],
    },
)

_CURRENT_FIELD_MAP = {
    "primary_label":             "primary_label",
    "secondary_label":           "secondary_label",
    "canonical_id":              "canonical_id",
    "entity_type":               "entity_type",
    "domain":                    "domain",
    "validation_status":         "validation_status",
    "enrichment_status":         "enrichment_status",
    "enrichment_citation_count": "enrichment_citation_count",
    "enrichment_concepts":       "enrichment_concepts",
    "enrichment_source":         "enrichment_source",
    "enrichment_doi":            "enrichment_doi",
}

_LEGACY_FALLBACKS = {
    "primary_label": "entity_name",
    "secondary_label": "brand_capitalized",
    "canonical_id": "sku",
}

_LEGACY_ATTRIBUTE_COLUMNS = ("brand_lower", "classification", "creation_date", "status")


def _demo_count(db: Session) -> int:
    return db.query(models.RawEntity).filter(models.RawEntity.source == "demo").count()


def _demo_file_name() -> str:
    name = getattr(_DEMO_FILE, "name", None)
    return name if isinstance(name, str) else "demo_entities.xlsx"


def _demo_portal(db: Session) -> models.CatalogPortal | None:
    return (
        db.query(models.CatalogPortal)
        .filter(models.CatalogPortal.source_label == _DEMO_BATCH_SOURCE_LABEL)
        .order_by(models.CatalogPortal.created_at.desc(), models.CatalogPortal.id.desc())
        .first()
    )


def _demo_status_payload(db: Session) -> dict:
    count = _demo_count(db)
    portal = _demo_portal(db)
    return {
        "demo_seeded": count > 0,
        "demo_entity_count": count,
        "catalog_portal": (
            {
                "title": portal.title,
                "slug": portal.slug,
                "url": f"/catalogs/{portal.slug}",
            }
            if portal
            else None
        ),
    }


def _is_present(value: object) -> bool:
    return value is not None and not pd.isna(value)


def _normalize_domain(raw_value: object) -> str:
    if not _is_present(raw_value):
        return "default"
    return str(raw_value).strip().lower() or "default"


def _row_to_raw_entity_kwargs(row: dict) -> dict:
    kwargs: dict = {"source": "demo"}

    for df_col, model_field in _CURRENT_FIELD_MAP.items():
        value = row.get(df_col)
        if _is_present(value):
            kwargs[model_field] = value

    for model_field, legacy_column in _LEGACY_FALLBACKS.items():
        if model_field not in kwargs:
            value = row.get(legacy_column)
            if _is_present(value):
                kwargs[model_field] = value

    if "domain" not in kwargs:
        kwargs["domain"] = _normalize_domain(row.get("entity_type"))

    legacy_attributes = {
        key: row.get(key)
        for key in _LEGACY_ATTRIBUTE_COLUMNS
        if _is_present(row.get(key))
    }
    if legacy_attributes:
        kwargs["attributes_json"] = json.dumps(legacy_attributes)

    # Any remaining columns that are not known model fields go into
    # normalized_json so the disambiguation engine can find them.
    _known = (
        set(_CURRENT_FIELD_MAP.keys())
        | set(_LEGACY_FALLBACKS.values())
        | set(_LEGACY_ATTRIBUTE_COLUMNS)
        | {"entity_name", "brand_capitalized", "sku"}  # legacy label columns
    )
    extra = {k: str(v) for k, v in row.items() if k not in _known and _is_present(v)}
    if extra:
        kwargs["normalized_json"] = json.dumps(extra, ensure_ascii=False)

    return kwargs


def _ensure_unique_demo_slug(db: Session) -> str:
    if not db.query(models.CatalogPortal).filter(models.CatalogPortal.slug == _DEMO_PORTAL_SLUG).first():
        return _DEMO_PORTAL_SLUG

    suffix = 2
    while True:
        candidate = f"{_DEMO_PORTAL_SLUG}-{suffix}"
        if not db.query(models.CatalogPortal).filter(models.CatalogPortal.slug == candidate).first():
            return candidate
        suffix += 1


def _create_demo_batch_and_portal(
    db: Session,
    *,
    current_user: models.User,
    total_rows: int,
) -> tuple[models.ImportBatch, models.CatalogPortal]:
    org_id = resolve_request_org_id(db, current_user)
    now = datetime.now(timezone.utc)
    batch = models.ImportBatch(
        org_id=persisted_org_id(org_id),
        domain_id="science",
        source_type=_DEMO_BATCH_SOURCE_TYPE,
        file_name=_demo_file_name(),
        file_format="xlsx",
        source_label=_DEMO_BATCH_SOURCE_LABEL,
        total_rows=total_rows,
        entity_type_hint=None,
        created_by=current_user.id,
        created_at=now,
    )
    db.add(batch)
    db.flush()

    portal = models.CatalogPortal(
        org_id=persisted_org_id(org_id),
        source_batch_id=batch.id,
        domain_id=batch.domain_id,
        title=_DEMO_PORTAL_TITLE,
        slug=_ensure_unique_demo_slug(db),
        description=_DEMO_PORTAL_DESCRIPTION,
        visibility="org",
        source_label=_DEMO_BATCH_SOURCE_LABEL,
        source_context_json=json.dumps(
            {
                "kind": "demo_seed",
                "file": _demo_file_name(),
                "rows": total_rows,
                "provider": "UKIP demo",
            }
        ),
        query_json=json.dumps(
            {
                "search": None,
                "min_quality": None,
                "ft_entity_type": None,
                "ft_validation_status": None,
                "ft_enrichment_status": None,
                "ft_source": None,
                "sort_by": "primary_label",
                "order": "asc",
            }
        ),
        featured_facets_json=json.dumps(["entity_type", "enrichment_status", "source"]),
        default_sort="primary_label",
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(portal)
    db.flush()
    return batch, portal


# ── GET /demo/status ──────────────────────────────────────────────────────────

@router.get("/demo/status", tags=["demo"])
def demo_status(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    return _demo_status_payload(db)


# ── POST /demo/seed ───────────────────────────────────────────────────────────

def _try_openalex_live():
    """Try fetching demo records from live OpenAlex API. Returns (records, source_label) or raises."""
    from backend.adapters.enrichment.openalex import OpenAlexAdapter
    adapter = OpenAlexAdapter()
    records = adapter.search_bulk(
        query="knowledge management",
        filters={"concept_id": _OPENALEX_CONCEPT_ID},
        limit=_OPENALEX_DEMO_LIMIT,
    )
    if not records:
        raise RuntimeError("OpenAlex returned zero results")
    return records, "openalex_live"


def _load_openalex_snapshot():
    """Load bundled snapshot JSON as EnrichedRecord objects."""
    from backend.schemas_enrichment import EnrichedRecord
    if not _SNAPSHOT_FILE.exists():
        raise FileNotFoundError(f"Snapshot not found: {_SNAPSHOT_FILE}")
    data = json.loads(_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    records = []
    for item in data:
        records.append(EnrichedRecord(
            id=item.get("id", "unknown"),
            doi=item.get("doi"),
            title=item.get("title", "Untitled"),
            authors=item.get("authors", []),
            citation_count=item.get("citation_count", 0),
            publication_year=item.get("year") or item.get("publication_year"),
            concepts=item.get("concepts", []),
            publisher=item.get("publisher"),
            is_open_access=item.get("is_open_access", False),
            source_api="OpenAlex",
        ))
    return records, "openalex_snapshot"


def _build_scientific_showcase_records():
    """Create a deterministic scientific intelligence demo corpus."""
    from backend.schemas_enrichment import EnrichedRecord

    records: list[EnrichedRecord] = []
    author_pool = (
        ("Ana Morales", "Nora Patel", "Mateo Chen"),
        ("Lucia Rivera", "Ethan Okafor", "Sofia Klein"),
        ("Ines Vidal", "Maya Singh", "Theo Martin"),
        ("Camila Torres", "Jonas Weber", "Priya Raman"),
    )
    for cluster_index, cluster in enumerate(_SHOWCASE_CLUSTERS):
        for title_index, title in enumerate(cluster["titles"]):
            sequence = cluster_index * 100 + title_index + 1
            year = 2020 + ((title_index + cluster_index) % 6)
            citation_count = 18 + (cluster_index * 17) + (title_index * 11)
            authors = list(author_pool[(cluster_index + title_index) % len(author_pool)])
            records.append(EnrichedRecord(
                id=f"ukip-showcase-{cluster['slug']}-{title_index + 1}",
                doi=f"10.5555/ukip.showcase.{sequence:04d}",
                title=title,
                authors=authors,
                citation_count=citation_count,
                publication_year=year,
                concepts=list(cluster["concepts"]),
                publisher=cluster["publisher"],
                affiliations=[
                    "UKIP Scientific Intelligence Lab",
                    "Latin American Research Observatory",
                ],
                is_open_access=title_index % 2 == 0,
                source_api="UKIP Showcase",
                raw_response={
                    "cluster": cluster["label"],
                    "demo_use": "scientific intelligence product walkthrough",
                },
            ))
    return records, "curated_scientific_showcase"


def _seed_from_enriched_records(
    db: Session,
    records,
    current_user: models.User,
    org_id,
) -> tuple[int, models.CatalogPortal]:
    """Ingest EnrichedRecord list as demo entities and return (count, portal)."""
    from backend.routers.api_import import _ingest_records
    batch, portal = _create_demo_batch_and_portal(
        db, current_user=current_user, total_rows=len(records),
    )
    inserted = _ingest_records(db, records, "science", "demo", org_id)
    # Tag all just-inserted demo entities with the batch id
    db.execute(
        models.RawEntity.__table__.update()
        .where(models.RawEntity.source == "demo")
        .where(models.RawEntity.import_batch_id == None)  # noqa: E711
        .values(import_batch_id=batch.id, org_id=batch.org_id)
    )
    db.commit()
    return inserted, portal


@router.post("/demo/seed", status_code=201, tags=["demo"])
def demo_seed(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """
    Seed demo data from live OpenAlex API (preferred) or bundled snapshot fallback.
    Clears any existing demo entities first for idempotency.
    Falls back to legacy Excel file if neither OpenAlex source is available.
    """
    # Idempotent: clear existing demo data before re-seeding
    existing_count = _demo_count(db)
    if existing_count > 0:
        db.query(models.RawEntity).filter(models.RawEntity.source == "demo").delete(synchronize_session=False)
        db.commit()
        logger.info("Demo seed: cleared %d existing demo entities", existing_count)

    org_id = resolve_request_org_id(db, current_user)

    # Strategy 1: Live OpenAlex query
    try:
        records, data_source = _try_openalex_live()
        seeded, portal = _seed_from_enriched_records(db, records, current_user, org_id)
        logger.info("Demo seed: %d entities from %s", seeded, data_source)
        return {
            "seeded": seeded,
            "source": data_source,
            "message": f"Demo dataset loaded: {seeded} entities from live OpenAlex.",
            "catalog_portal": {"title": portal.title, "slug": portal.slug, "url": f"/catalogs/{portal.slug}"},
        }
    except Exception as exc:
        logger.info("Live OpenAlex unavailable (%s), trying snapshot fallback", exc)

    # Strategy 2: Bundled snapshot JSON
    try:
        records, data_source = _load_openalex_snapshot()
        seeded, portal = _seed_from_enriched_records(db, records, current_user, org_id)
        logger.info("Demo seed: %d entities from %s", seeded, data_source)
        return {
            "seeded": seeded,
            "source": data_source,
            "message": f"Demo dataset loaded: {seeded} entities from bundled snapshot.",
            "catalog_portal": {"title": portal.title, "slug": portal.slug, "url": f"/catalogs/{portal.slug}"},
        }
    except Exception as exc:
        logger.info("Snapshot fallback unavailable (%s), trying legacy Excel", exc)

    # Strategy 3: Legacy Excel file (backwards compat)
    if not _DEMO_FILE.exists():
        records, data_source = _build_scientific_showcase_records()
        seeded, portal = _seed_from_enriched_records(db, records, current_user, org_id)
        logger.info("Demo seed: %d entities from %s", seeded, data_source)
        return {
            "seeded": seeded,
            "source": data_source,
            "message": f"Demo dataset loaded: {seeded} curated scientific intelligence entities.",
            "catalog_portal": {"title": portal.title, "slug": portal.slug, "url": f"/catalogs/{portal.slug}"},
        }

    try:
        df = pd.read_excel(_DEMO_FILE)
    except Exception as exc:
        logger.exception("Failed to read demo Excel file")
        raise HTTPException(status_code=500, detail=f"Failed to read demo file: {exc}") from exc

    rows = df.to_dict(orient="records")
    batch, portal = _create_demo_batch_and_portal(db, current_user=current_user, total_rows=len(rows))
    seeded = 0
    chunk: list[models.RawEntity] = []
    for row in rows:
        entity_kwargs = _row_to_raw_entity_kwargs(row)
        entity_kwargs["import_batch_id"] = batch.id
        entity_kwargs["org_id"] = batch.org_id
        chunk.append(models.RawEntity(**entity_kwargs))
        if len(chunk) >= _SEED_CHUNK:
            db.add_all(chunk)
            db.commit()
            seeded += len(chunk)
            chunk = []

    if chunk:
        db.add_all(chunk)
        db.commit()
        seeded += len(chunk)

    logger.info("Demo seed: %d entities from legacy Excel", seeded)
    return {
        "seeded": seeded,
        "source": "legacy_excel",
        "message": f"Demo dataset loaded: {seeded} entities ready.",
        "catalog_portal": {"title": portal.title, "slug": portal.slug, "url": f"/catalogs/{portal.slug}"},
    }


# ── DELETE /demo/reset ────────────────────────────────────────────────────────

@router.delete("/demo/reset", tags=["demo"])
def demo_reset(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_role("super_admin", "admin")),
):
    """Remove all demo entities without touching user-imported data."""
    demo_batch_ids = [
        row[0]
        for row in db.query(models.ImportBatch.id)
        .filter(models.ImportBatch.source_type == _DEMO_BATCH_SOURCE_TYPE)
        .all()
    ]
    if demo_batch_ids:
        (
            db.query(models.CatalogPortal)
            .filter(models.CatalogPortal.source_batch_id.in_(demo_batch_ids))
            .delete(synchronize_session=False)
        )
    (
        db.query(models.CatalogPortal)
        .filter(models.CatalogPortal.source_label == _DEMO_BATCH_SOURCE_LABEL)
        .delete(synchronize_session=False)
    )
    deleted = (
        db.query(models.RawEntity)
        .filter(models.RawEntity.source == "demo")
        .delete(synchronize_session=False)
    )
    if demo_batch_ids:
        (
            db.query(models.ImportBatch)
            .filter(models.ImportBatch.id.in_(demo_batch_ids))
            .delete(synchronize_session=False)
        )
    db.commit()
    logger.info("Demo reset: %d entities deleted", deleted)
    return {"deleted": deleted}
