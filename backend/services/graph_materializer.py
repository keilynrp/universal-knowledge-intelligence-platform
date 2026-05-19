from __future__ import annotations

import json
import re
from itertools import combinations
from typing import Any

from sqlalchemy.orm import Session

from backend import models


_DERIVED_SOURCE = "graph_materializer"


def _safe_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _split_concepts(entity: models.RawEntity, attrs: dict[str, Any]) -> list[str]:
    concepts: list[str] = []
    raw_values: list[Any] = [
        attrs.get("concepts"),
        attrs.get("keywords"),
        entity.enrichment_concepts,
    ]
    raw_record = attrs.get("raw_record")
    if isinstance(raw_record, dict):
        raw_values.extend([
            raw_record.get("keywords"),
            raw_record.get("concepts"),
            raw_record.get("DE"),
            raw_record.get("ID"),
        ])

    for raw in raw_values:
        if isinstance(raw, list):
            candidates = raw
        elif isinstance(raw, str):
            candidates = re.split(r"[;,|]", raw)
        else:
            candidates = []
        for candidate in candidates:
            label = _clean_text(candidate)
            if label and label.lower() not in {c.lower() for c in concepts}:
                concepts.append(label)
    return concepts[:20]


def _authors_from_enrichment(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    raw_authors = attrs.get("canonical_authors")
    if isinstance(raw_authors, list) and raw_authors:
        return [author for author in raw_authors if isinstance(author, dict)]

    enriched_authors = attrs.get("enrichment_authors")
    if not isinstance(enriched_authors, list):
        return []

    orcids = attrs.get("enrichment_author_orcids")
    author_orcids = orcids if isinstance(orcids, list) else []
    authors: list[dict[str, Any]] = []
    for index, author in enumerate(enriched_authors):
        if isinstance(author, dict):
            name = _clean_text(author.get("name") or author.get("display_name") or author.get("author"))
            if not name:
                continue
            authors.append({**author, "name": name, "order": author.get("order") or index + 1})
            continue
        name = _clean_text(author)
        if not name:
            continue
        authors.append({
            "name": name,
            "order": index + 1,
            "orcid": author_orcids[index] if index < len(author_orcids) else None,
        })
    return authors


def _node_attrs(kind: str, import_batch_id: int, metadata: dict[str, Any]) -> str:
    payload = {
        "derived": True,
        "derived_kind": kind,
        "import_batch_id": import_batch_id,
        **metadata,
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def _get_or_create_node(
    db: Session,
    *,
    org_id: int | None,
    import_batch_id: int,
    domain: str,
    entity_type: str,
    canonical_id: str,
    primary_label: str,
    secondary_label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[models.RawEntity, bool]:
    node = (
        db.query(models.RawEntity)
        .filter(
            models.RawEntity.org_id == org_id,
            models.RawEntity.import_batch_id == import_batch_id,
            models.RawEntity.domain == domain,
            models.RawEntity.entity_type == entity_type,
            models.RawEntity.canonical_id == canonical_id,
        )
        .first()
    )
    if node:
        return node, False

    node = models.RawEntity(
        org_id=org_id,
        import_batch_id=import_batch_id,
        domain=domain,
        entity_type=entity_type,
        primary_label=primary_label,
        secondary_label=secondary_label,
        canonical_id=canonical_id,
        attributes_json=_node_attrs(entity_type, import_batch_id, metadata or {}),
        validation_status="derived",
        enrichment_status="derived",
        source=_DERIVED_SOURCE,
    )
    db.add(node)
    db.flush()
    return node, True


def _relationship_exists(
    db: Session,
    *,
    org_id: int | None,
    source_id: int,
    target_id: int,
    relation_type: str,
    import_batch_id: int,
) -> bool:
    marker = f'"import_batch_id": {import_batch_id}'
    return (
        db.query(models.EntityRelationship.id)
        .filter(
            models.EntityRelationship.org_id == org_id,
            models.EntityRelationship.source_id == source_id,
            models.EntityRelationship.target_id == target_id,
            models.EntityRelationship.relation_type == relation_type,
            models.EntityRelationship.notes.contains(marker),
        )
        .first()
        is not None
    )


def _create_relationship(
    db: Session,
    *,
    org_id: int | None,
    source_id: int,
    target_id: int,
    relation_type: str,
    import_batch_id: int,
    publication_id: int | None = None,
    weight: float = 1.0,
) -> bool:
    if source_id == target_id:
        return False
    if _relationship_exists(
        db,
        org_id=org_id,
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        import_batch_id=import_batch_id,
    ):
        return False

    notes = {
        "import_batch_id": import_batch_id,
        "publication_id": publication_id,
        "derived_by": _DERIVED_SOURCE,
    }
    db.add(models.EntityRelationship(
        org_id=org_id,
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        weight=weight,
        notes=json.dumps(notes, ensure_ascii=False),
    ))
    return True


def _canonical_id(prefix: str, *values: Any) -> str | None:
    parts = [_clean_text(value) for value in values]
    usable = [part for part in parts if part]
    if not usable:
        return None
    return f"{prefix}:{_slug(':'.join(usable))}"


def materialize_scientific_import_graph(
    db: Session,
    import_batch_id: int,
    *,
    org_id: int | None,
) -> dict[str, int]:
    """Create graph-ready derived entities and relationships for a scientific import batch."""
    publications = (
        db.query(models.RawEntity)
        .filter(
            models.RawEntity.org_id == org_id,
            models.RawEntity.import_batch_id == import_batch_id,
        )
        .filter(models.RawEntity.source != _DERIVED_SOURCE)
        .all()
    )

    nodes_created = 0
    relationships_created = 0
    author_nodes_by_publication: dict[int, list[models.RawEntity]] = {}

    for publication in publications:
        attrs = _safe_json(publication.attributes_json)
        provider = _clean_text(attrs.get("provider") or publication.enrichment_source)
        domain = publication.domain or "science"
        pub_id = publication.id

        authors = _authors_from_enrichment(attrs)
        author_pairs: list[tuple[dict[str, Any], models.RawEntity]] = []
        for author in authors:
            if not isinstance(author, dict):
                continue
            name = _clean_text(author.get("name"))
            if not name:
                continue
            canonical_id = (
                _canonical_id("orcid", author.get("orcid"))
                or _canonical_id("author", author.get("external_id"))
                or _canonical_id("author", name)
            )
            if not canonical_id:
                continue
            node, created = _get_or_create_node(
                db,
                org_id=org_id,
                import_batch_id=import_batch_id,
                domain=domain,
                entity_type="author",
                canonical_id=canonical_id,
                primary_label=name,
                secondary_label=provider,
                metadata={"provider": provider, "order": author.get("order")},
            )
            nodes_created += int(created)
            author_pairs.append((author, node))
            relationships_created += int(_create_relationship(
                db,
                org_id=org_id,
                source_id=publication.id,
                target_id=node.id,
                relation_type="authored-by",
                import_batch_id=import_batch_id,
                publication_id=pub_id,
            ))

        author_nodes_by_publication[publication.id] = [node for _, node in author_pairs]

        raw_affiliations = attrs.get("canonical_affiliations")
        affiliations = raw_affiliations if isinstance(raw_affiliations, list) else []
        affiliation_nodes: dict[str, models.RawEntity] = {}
        for affiliation in affiliations:
            if not isinstance(affiliation, dict):
                continue
            name = _clean_text(affiliation.get("name"))
            if not name:
                continue
            canonical_id = (
                _canonical_id("affiliation", affiliation.get("external_id"))
                or _canonical_id("affiliation", name)
            )
            if not canonical_id:
                continue
            node, created = _get_or_create_node(
                db,
                org_id=org_id,
                import_batch_id=import_batch_id,
                domain=domain,
                entity_type="affiliation",
                canonical_id=canonical_id,
                primary_label=name,
                secondary_label=_clean_text(affiliation.get("country")),
                metadata={"provider": provider, "country": affiliation.get("country")},
            )
            nodes_created += int(created)
            affiliation_nodes[name.lower()] = node

        for author, author_node in author_pairs:
            raw_author_affiliations = author.get("affiliations")
            author_affiliations = raw_author_affiliations if isinstance(raw_author_affiliations, list) else []
            for affiliation_name in author_affiliations:
                affiliation_node = affiliation_nodes.get(str(affiliation_name).strip().lower())
                if not affiliation_node:
                    continue
                relationships_created += int(_create_relationship(
                    db,
                    org_id=org_id,
                    source_id=author_node.id,
                    target_id=affiliation_node.id,
                    relation_type="belongs-to",
                    import_batch_id=import_batch_id,
                    publication_id=pub_id,
                ))

        source_title = _clean_text(attrs.get("journal") or attrs.get("source_title") or attrs.get("venue"))
        raw_record = attrs.get("raw_record")
        if not source_title and isinstance(raw_record, dict):
            source_title = _clean_text(raw_record.get("journal") or raw_record.get("source") or raw_record.get("SO"))
        if source_title:
            canonical_id = _canonical_id("journal", source_title)
            if canonical_id:
                journal, created = _get_or_create_node(
                    db,
                    org_id=org_id,
                    import_batch_id=import_batch_id,
                    domain=domain,
                    entity_type="journal",
                    canonical_id=canonical_id,
                    primary_label=source_title,
                    secondary_label=provider,
                    metadata={"provider": provider},
                )
                nodes_created += int(created)
                relationships_created += int(_create_relationship(
                    db,
                    org_id=org_id,
                    source_id=publication.id,
                    target_id=journal.id,
                    relation_type="published-in",
                    import_batch_id=import_batch_id,
                    publication_id=pub_id,
                ))

        for concept in _split_concepts(publication, attrs):
            canonical_id = _canonical_id("concept", concept)
            if not canonical_id:
                continue
            node, created = _get_or_create_node(
                db,
                org_id=org_id,
                import_batch_id=import_batch_id,
                domain=domain,
                entity_type="concept",
                canonical_id=canonical_id,
                primary_label=concept,
                secondary_label=provider,
                metadata={"provider": provider},
            )
            nodes_created += int(created)
            relationships_created += int(_create_relationship(
                db,
                org_id=org_id,
                source_id=publication.id,
                target_id=node.id,
                relation_type="has-concept",
                import_batch_id=import_batch_id,
                publication_id=pub_id,
                weight=0.7,
            ))

        raw_identifiers = attrs.get("canonical_identifiers")
        identifiers = raw_identifiers if isinstance(raw_identifiers, list) else []
        if publication.enrichment_doi:
            identifiers = [{"scheme": "doi", "value": publication.enrichment_doi}, *identifiers]
        seen_identifiers: set[str] = set()
        for identifier in identifiers:
            if not isinstance(identifier, dict):
                continue
            scheme = _clean_text(identifier.get("scheme"))
            value = _clean_text(identifier.get("value"))
            canonical_id = _canonical_id(scheme or "identifier", value)
            if not scheme or not value or not canonical_id or canonical_id in seen_identifiers:
                continue
            seen_identifiers.add(canonical_id)
            node, created = _get_or_create_node(
                db,
                org_id=org_id,
                import_batch_id=import_batch_id,
                domain=domain,
                entity_type="identifier",
                canonical_id=canonical_id,
                primary_label=value,
                secondary_label=scheme.upper(),
                metadata={"provider": provider, "scheme": scheme},
            )
            nodes_created += int(created)
            relationships_created += int(_create_relationship(
                db,
                org_id=org_id,
                source_id=publication.id,
                target_id=node.id,
                relation_type="identified-by",
                import_batch_id=import_batch_id,
                publication_id=pub_id,
                weight=0.5,
            ))

    for publication_id, author_nodes in author_nodes_by_publication.items():
        for left, right in combinations(author_nodes, 2):
            source_id, target_id = sorted((left.id, right.id))
            relationships_created += int(_create_relationship(
                db,
                org_id=org_id,
                source_id=source_id,
                target_id=target_id,
                relation_type="coauthor-with",
                import_batch_id=import_batch_id,
                publication_id=publication_id,
                weight=0.8,
            ))

    db.commit()
    return {
        "publications": len(publications),
        "nodes_created": nodes_created,
        "relationships_created": relationships_created,
    }
