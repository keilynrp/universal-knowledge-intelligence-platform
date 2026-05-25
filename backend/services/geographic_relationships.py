"""Geographic Relationship Materialization — Task 3.4.

Materializes geographic relationships between entities and geographic
entities based on institution reconciliation, author affiliations,
and spatial coverage data.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class GeoRelationType(str, Enum):
    LOCATED_IN = "located_in"
    ASSOCIATED_WITH = "associated_with"
    COVERS_REGION = "covers_region"
    AFFILIATED_IN = "affiliated_in"
    HELD_AT = "held_at"
    CONTAINED_IN = "contained_in"


@dataclass
class GeoRelationship:
    """A materialized geographic relationship."""
    id: int | None = None
    source_entity_id: int | None = None
    source_entity_type: str = ""  # organization | publication | dataset | person
    target_country_code: str | None = None
    target_geo_entity_id: int | None = None
    relation_type: GeoRelationType = GeoRelationType.ASSOCIATED_WITH
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["relation_type"] = self.relation_type.value
        return d


class GeoRelationshipMaterializer:
    """Materializes geographic relationships from reconciliation data."""

    def __init__(self) -> None:
        self._relationships: list[GeoRelationship] = []
        self._next_id = 1

    @property
    def relationships(self) -> list[GeoRelationship]:
        return list(self._relationships)

    def materialize_institution_location(
        self,
        institution_name: str,
        country_code: str,
        entity_id: int | None = None,
        confidence: float = 0.95,
        ror_id: str | None = None,
    ) -> GeoRelationship:
        """Materialize 'organization located_in country' from ROR/reconciliation."""
        evidence = [f"institution_name:{institution_name}"]
        if ror_id:
            evidence.append(f"ror_id:{ror_id}")

        rel = GeoRelationship(
            id=self._next_id,
            source_entity_id=entity_id,
            source_entity_type="organization",
            target_country_code=country_code.upper(),
            relation_type=GeoRelationType.LOCATED_IN,
            confidence=confidence,
            evidence=evidence,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._relationships.append(rel)
        self._next_id += 1
        return rel

    def materialize_publication_association(
        self,
        entity_id: int,
        country_codes: list[str],
        confidence: float = 0.85,
    ) -> list[GeoRelationship]:
        """Materialize 'publication associated_with country' from author affiliations.

        Deduplicates country codes before materializing.
        """
        seen: set[str] = set()
        results: list[GeoRelationship] = []

        for code in country_codes:
            normalized = code.strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            rel = GeoRelationship(
                id=self._next_id,
                source_entity_id=entity_id,
                source_entity_type="publication",
                target_country_code=normalized,
                relation_type=GeoRelationType.ASSOCIATED_WITH,
                confidence=confidence,
                evidence=[f"author_affiliation_country:{normalized}"],
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._relationships.append(rel)
            self._next_id += 1
            results.append(rel)

        return results

    def materialize_dataset_coverage(
        self,
        entity_id: int,
        country_codes: list[str],
        confidence: float = 0.8,
    ) -> list[GeoRelationship]:
        """Materialize 'dataset covers_region country' from spatial coverage."""
        seen: set[str] = set()
        results: list[GeoRelationship] = []

        for code in country_codes:
            normalized = code.strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)

            rel = GeoRelationship(
                id=self._next_id,
                source_entity_id=entity_id,
                source_entity_type="dataset",
                target_country_code=normalized,
                relation_type=GeoRelationType.COVERS_REGION,
                confidence=confidence,
                evidence=[f"spatial_coverage:{normalized}"],
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self._relationships.append(rel)
            self._next_id += 1
            results.append(rel)

        return results

    def get_relationships_for_entity(self, entity_id: int) -> list[GeoRelationship]:
        return [r for r in self._relationships if r.source_entity_id == entity_id]

    def get_relationships_by_country(self, country_code: str) -> list[GeoRelationship]:
        return [r for r in self._relationships if r.target_country_code == country_code.upper()]
