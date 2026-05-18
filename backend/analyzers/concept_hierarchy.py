"""
Concept hierarchy analyzer — materializes OpenAlex concept trees per domain.

Fetches ancestor chains for concepts found in enriched entities,
builds a local concept subgraph stored in concept_nodes table.
"""
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(os.environ.get("CONCEPT_CACHE_DIR", "concept_cache"))
_CACHE_TTL_DAYS = 7
_MAX_CONCURRENT = 5
_INTER_BATCH_DELAY = 0.1  # 100ms polite pool
_MAX_CONCEPTS_PER_RUN = 2000
_OPENALEX_CONCEPTS_URL = "https://api.openalex.org/concepts"
_POLITE_EMAIL = "research@ukip.dev"


# ── File-based cache ─────────────────────────────────────────────────────────

def _cache_path(concept_id: str) -> Path:
    """Return cache file path for a given OpenAlex concept ID."""
    safe_id = concept_id.replace("/", "_").replace(":", "_")
    return _CACHE_DIR / f"{safe_id}.json"


def _read_cache(concept_id: str) -> Optional[dict]:
    """Read cached concept data if fresh enough."""
    path = _cache_path(concept_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
        if datetime.now(timezone.utc) - cached_at > timedelta(days=_CACHE_TTL_DAYS):
            return None
        return data
    except (json.JSONDecodeError, ValueError, OSError):
        return None


def _write_cache(concept_id: str, data: dict) -> None:
    """Write concept data to cache."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data["_cached_at"] = datetime.now(timezone.utc).isoformat()
    try:
        _cache_path(concept_id).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as e:
        logger.warning("Failed to write concept cache for %s: %s", concept_id, e)


# ── OpenAlex API fetching ────────────────────────────────────────────────────

async def _fetch_concept(client: httpx.AsyncClient, concept_id: str) -> Optional[dict]:
    """Fetch a single concept from OpenAlex, with cache."""
    cached = _read_cache(concept_id)
    if cached:
        return cached

    url = f"{_OPENALEX_CONCEPTS_URL}/{concept_id}"
    try:
        resp = await client.get(url, params={"mailto": _POLITE_EMAIL})
        if resp.status_code == 200:
            data = resp.json()
            _write_cache(concept_id, data)
            return data
        logger.warning("OpenAlex concept %s returned %d", concept_id, resp.status_code)
    except Exception as e:
        logger.warning("Error fetching concept %s: %s", concept_id, e)
    return None


async def _fetch_concepts_batch(concept_ids: list[str]) -> dict[str, dict]:
    """Fetch multiple concepts with polite concurrency."""
    results: dict[str, dict] = {}
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def _fetch_one(cid: str):
            async with semaphore:
                data = await _fetch_concept(client, cid)
                if data:
                    results[cid] = data
                await asyncio.sleep(_INTER_BATCH_DELAY)

        await asyncio.gather(*[_fetch_one(cid) for cid in concept_ids])

    return results


async def resolve_concept_id_by_name(name: str) -> Optional[str]:
    """Search OpenAlex for a concept by display name (for legacy entities)."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                _OPENALEX_CONCEPTS_URL,
                params={
                    "search": name,
                    "per-page": 1,
                    "mailto": _POLITE_EMAIL,
                },
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    return results[0].get("id")
        except Exception as e:
            logger.warning("Error resolving concept name '%s': %s", name, e)
    return None


def _collect_ancestor_ids(concept_data: dict) -> list[str]:
    """Extract ancestor concept IDs from an OpenAlex concept response."""
    ancestors = concept_data.get("ancestors", [])
    return [a["id"] for a in ancestors if a.get("id")]


# ── Materialization ──────────────────────────────────────────────────────────

def _gather_corpus_concepts(db: Session, domain_id: str) -> dict[str, int]:
    """
    Collect unique concept names from enriched entities with frequency counts.
    Returns {concept_name: entity_count}.
    """
    entities = (
        db.query(models.RawEntity.enrichment_concepts, models.RawEntity.attributes_json)
        .filter(
            models.RawEntity.domain == domain_id,
            models.RawEntity.enrichment_status == "completed",
            models.RawEntity.enrichment_concepts.isnot(None),
        )
        .all()
    )

    concept_freq: dict[str, int] = {}
    for concepts_str, attrs_json in entities:
        if not concepts_str:
            continue
        for c in concepts_str.split(","):
            name = c.strip()
            if name:
                concept_freq[name] = concept_freq.get(name, 0) + 1

    return concept_freq


def _gather_concept_ids_from_attrs(db: Session, domain_id: str) -> dict[str, str]:
    """
    Collect concept_name -> openalex_id mappings from entities that have
    enrichment_concept_ids in their attributes_json.
    """
    entities = (
        db.query(models.RawEntity.enrichment_concepts, models.RawEntity.attributes_json)
        .filter(
            models.RawEntity.domain == domain_id,
            models.RawEntity.enrichment_status == "completed",
            models.RawEntity.attributes_json.like("%enrichment_concept_ids%"),
        )
        .all()
    )

    name_to_id: dict[str, str] = {}
    for concepts_str, attrs_json in entities:
        if not concepts_str or not attrs_json:
            continue
        try:
            attrs = json.loads(attrs_json)
        except (json.JSONDecodeError, TypeError):
            continue
        concept_ids = attrs.get("enrichment_concept_ids", [])
        names = [c.strip() for c in concepts_str.split(",") if c.strip()]
        for i, name in enumerate(names):
            if i < len(concept_ids) and concept_ids[i]:
                name_to_id[name] = concept_ids[i]

    return name_to_id


async def _resolve_all_concept_ids(
    concept_names: list[str],
    known_ids: dict[str, str],
) -> dict[str, str]:
    """Resolve OpenAlex IDs for all concept names, using known IDs and API fallback."""
    name_to_id = dict(known_ids)
    missing = [n for n in concept_names if n not in name_to_id]

    for name in missing:
        oa_id = await resolve_concept_id_by_name(name)
        if oa_id:
            name_to_id[name] = oa_id
        await asyncio.sleep(_INTER_BATCH_DELAY)

    return name_to_id


def _upsert_concept_node(
    db: Session,
    *,
    openalex_id: str,
    display_name: str,
    level: int,
    parent_openalex_id: Optional[str],
    entity_count: int,
    domain: str,
    id_cache: dict[str, int],
) -> int:
    """Upsert a concept node, return its DB id. Uses id_cache for parent lookups."""
    existing = (
        db.query(models.ConceptNode)
        .filter(
            models.ConceptNode.openalex_id == openalex_id,
            models.ConceptNode.domain == domain,
        )
        .first()
    )

    parent_db_id = id_cache.get(parent_openalex_id) if parent_openalex_id else None

    if existing:
        existing.display_name = display_name
        existing.level = level
        existing.parent_id = parent_db_id
        existing.entity_count = entity_count
        existing.last_fetched_at = datetime.now(timezone.utc)
        db.flush()
        id_cache[openalex_id] = existing.id
        return existing.id
    else:
        node = models.ConceptNode(
            openalex_id=openalex_id,
            display_name=display_name,
            level=level,
            parent_id=parent_db_id,
            entity_count=entity_count,
            domain=domain,
            last_fetched_at=datetime.now(timezone.utc),
        )
        db.add(node)
        db.flush()
        id_cache[openalex_id] = node.id
        return node.id


async def materialize_domain_concepts(db: Session, domain_id: str) -> dict:
    """
    Main materialization entry point.
    1. Gather corpus concepts with frequency counts
    2. Resolve OpenAlex IDs
    3. Fetch ancestor chains
    4. Upsert concept tree into concept_nodes
    """
    concept_freq = _gather_corpus_concepts(db, domain_id)
    if not concept_freq:
        return {"nodes_created": 0, "nodes_updated": 0, "warning": None}

    # Cap at most frequent concepts
    warning = None
    if len(concept_freq) > _MAX_CONCEPTS_PER_RUN:
        warning = f"Corpus has {len(concept_freq)} unique concepts; capped at {_MAX_CONCEPTS_PER_RUN} most frequent."
        sorted_concepts = sorted(concept_freq.items(), key=lambda x: -x[1])
        concept_freq = dict(sorted_concepts[:_MAX_CONCEPTS_PER_RUN])

    # Resolve OpenAlex IDs
    known_ids = _gather_concept_ids_from_attrs(db, domain_id)
    name_to_id = await _resolve_all_concept_ids(list(concept_freq.keys()), known_ids)

    # Fetch all leaf concept data + ancestors
    leaf_ids = list(set(name_to_id.values()))
    all_concept_data = await _fetch_concepts_batch(leaf_ids)

    # Collect all ancestor IDs we need to fetch
    ancestor_ids_needed: set[str] = set()
    for cdata in all_concept_data.values():
        for aid in _collect_ancestor_ids(cdata):
            if aid not in all_concept_data:
                ancestor_ids_needed.add(aid)

    # Fetch ancestors
    if ancestor_ids_needed:
        ancestor_data = await _fetch_concepts_batch(list(ancestor_ids_needed))
        all_concept_data.update(ancestor_data)

    # Build entity count map: openalex_id -> count
    oa_id_entity_count: dict[str, int] = {}
    for name, freq in concept_freq.items():
        oa_id = name_to_id.get(name)
        if oa_id:
            oa_id_entity_count[oa_id] = oa_id_entity_count.get(oa_id, 0) + freq

    # Sort by level (roots first) so parents exist before children
    sorted_concepts = sorted(
        all_concept_data.values(),
        key=lambda c: c.get("level", 0),
    )

    id_cache: dict[str, int] = {}  # openalex_id -> db_id
    nodes_created = 0
    nodes_updated = 0

    # Count existing nodes before upsert
    existing_count = (
        db.query(func.count(models.ConceptNode.id))
        .filter(models.ConceptNode.domain == domain_id)
        .scalar() or 0
    )

    for cdata in sorted_concepts:
        oa_id = cdata.get("id")
        if not oa_id:
            continue

        # Find the immediate parent (ancestor with highest level < this level)
        this_level = cdata.get("level", 0)
        ancestors = cdata.get("ancestors", [])
        parent_oa_id = None
        if ancestors:
            # Pick the ancestor with the highest level that's still < this_level
            valid_parents = [a for a in ancestors if a.get("level", 0) < this_level]
            if valid_parents:
                valid_parents.sort(key=lambda a: a.get("level", 0), reverse=True)
                parent_oa_id = valid_parents[0].get("id")

        _upsert_concept_node(
            db,
            openalex_id=oa_id,
            display_name=cdata.get("display_name", "Unknown"),
            level=this_level,
            parent_openalex_id=parent_oa_id,
            entity_count=oa_id_entity_count.get(oa_id, 0),
            domain=domain_id,
            id_cache=id_cache,
        )

    db.commit()

    new_count = (
        db.query(func.count(models.ConceptNode.id))
        .filter(models.ConceptNode.domain == domain_id)
        .scalar() or 0
    )

    nodes_created = max(0, new_count - existing_count)
    nodes_updated = len(sorted_concepts) - nodes_created

    return {
        "nodes_created": nodes_created,
        "nodes_updated": nodes_updated,
        "warning": warning,
    }


# ── Tree building ────────────────────────────────────────────────────────────

def build_concept_tree(db: Session, domain_id: str, root_level: Optional[int] = None) -> dict:
    """Build nested JSON tree from materialized concept_nodes."""
    nodes = (
        db.query(models.ConceptNode)
        .filter(models.ConceptNode.domain == domain_id)
        .order_by(models.ConceptNode.level, models.ConceptNode.display_name)
        .all()
    )

    if not nodes:
        return {"nodes": [], "materialized_at": None}

    last_fetched = max((n.last_fetched_at for n in nodes if n.last_fetched_at), default=None)

    # Build id -> node dict
    node_map: dict[int, dict] = {}
    for n in nodes:
        node_map[n.id] = {
            "id": n.id,
            "name": n.display_name,
            "level": n.level,
            "entity_count": n.entity_count,
            "openalex_id": n.openalex_id,
            "children": [],
        }

    # Attach children to parents
    roots: list[dict] = []
    for n in nodes:
        node_dict = node_map[n.id]
        if n.parent_id and n.parent_id in node_map:
            node_map[n.parent_id]["children"].append(node_dict)
        else:
            roots.append(node_dict)

    # Filter by root_level if specified
    if root_level is not None:
        roots = [r for r in roots if r["level"] >= root_level]
        # Also collect nodes at root_level that were children
        for ndict in node_map.values():
            if ndict["level"] == root_level and ndict not in roots:
                roots.append(ndict)

    return {
        "nodes": roots,
        "materialized_at": last_fetched.isoformat() if last_fetched else None,
    }
