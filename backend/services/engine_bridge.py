"""
Converts between UKIP domain objects and ukip-engine proto messages.

Used by the ingest pipeline to route graph materialization to the Rust engine.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend import models

logger = logging.getLogger(__name__)


def _parse_attrs(entity: "models.RawEntity") -> dict:
    if not entity.attributes_json:
        return {}
    try:
        return json.loads(entity.attributes_json)
    except Exception:
        return {}


def entity_to_publication(entity: "models.RawEntity"):
    """
    Convert a saved RawEntity (science publication) to a proto Publication message.

    Reads nested author/affiliation/identifier data from attributes_json, which is
    populated by CanonicalPublication.to_entity_kwargs() during ingest.
    """
    from backend.proto.ukip.engine.v1 import engine_pb2

    attrs = _parse_attrs(entity)

    pub = engine_pb2.Publication(
        entity_id=entity.id,
        title=entity.primary_label or "",
    )

    # Scalar optional fields
    if entity.enrichment_doi:
        pub.doi = entity.enrichment_doi
        pub.enrichment_doi = entity.enrichment_doi
    if entity.enrichment_source:
        pub.enrichment_source = entity.enrichment_source
    if entity.attributes_json:
        pub.attributes_json = entity.attributes_json

    for attr_key, proto_setter in (
        ("journal", "source_title"),
        ("source_title", "source_title"),
        ("publisher", "publisher"),
    ):
        val = attrs.get(attr_key)
        if val and not getattr(pub, proto_setter, None):
            setattr(pub, proto_setter, str(val))

    pub_type = attrs.get("publication_type") or attrs.get("entity_type") or entity.entity_type
    if pub_type:
        pub.publication_type = str(pub_type)

    try:
        year_raw = attrs.get("year")
        if year_raw is not None:
            pub.year = int(year_raw)
    except (ValueError, TypeError):
        pass

    for count_key, proto_key in (
        ("citation_count", "citation_count"),
        ("enrichment_citation_count", "citation_count"),
        ("reference_count", "reference_count"),
    ):
        raw = attrs.get(count_key)
        if raw is not None and not getattr(pub, proto_key, 0):
            try:
                setattr(pub, proto_key, int(raw))
            except (ValueError, TypeError):
                pass

    # Authors
    for author_dict in (attrs.get("canonical_authors") or []):
        if not isinstance(author_dict, dict):
            continue
        name = (author_dict.get("name") or "").strip()
        if not name:
            continue
        author = engine_pb2.Author(name=name)
        try:
            if author_dict.get("order") is not None:
                author.order = int(author_dict["order"])
        except (ValueError, TypeError):
            pass
        if author_dict.get("orcid"):
            author.orcid = str(author_dict["orcid"])
        if author_dict.get("external_id"):
            author.external_id = str(author_dict["external_id"])
        for aff_name in (author_dict.get("affiliations") or []):
            if aff_name:
                author.affiliations.append(str(aff_name))
        pub.authors.append(author)

    # Affiliations
    for aff_dict in (attrs.get("canonical_affiliations") or []):
        if not isinstance(aff_dict, dict):
            continue
        name = (aff_dict.get("name") or "").strip()
        if not name:
            continue
        aff = engine_pb2.Affiliation(name=name)
        if aff_dict.get("country"):
            aff.country = str(aff_dict["country"])
        if aff_dict.get("external_id"):
            aff.external_id = str(aff_dict["external_id"])
        pub.affiliations.append(aff)

    # Identifiers
    for id_dict in (attrs.get("canonical_identifiers") or []):
        if not isinstance(id_dict, dict):
            continue
        scheme = (id_dict.get("scheme") or "").strip()
        value = (id_dict.get("value") or "").strip()
        if scheme and value:
            pub.identifiers.append(engine_pb2.Identifier(scheme=scheme, value=value))

    # Concepts
    raw_concepts = attrs.get("concepts") or attrs.get("keywords") or entity.enrichment_concepts or ""
    if isinstance(raw_concepts, list):
        for c in raw_concepts:
            if c:
                pub.concepts.append(str(c))
    elif isinstance(raw_concepts, str) and raw_concepts.strip():
        for c in re.split(r"[;,|]", raw_concepts):
            c = c.strip()
            if c:
                pub.concepts.append(c)

    return pub


def should_use_engine(engine_client) -> bool:
    """Return True if the engine is configured (client is not None)."""
    return engine_client is not None


def shadow_mode_enabled() -> bool:
    return os.environ.get("ENGINE_SHADOW_MODE", "false").lower() == "true"


def fallback_enabled() -> bool:
    return os.environ.get("ENGINE_FALLBACK_PYTHON", "true").lower() != "false"


def sync_threshold() -> int:
    try:
        return int(os.environ.get("ENGINE_SYNC_THRESHOLD", "500"))
    except (ValueError, TypeError):
        return 500
