"""Linked-Data Output Governance — Task 4.7.

Exports entities as JSON-LD with alignment to standard vocabularies:
BIBFRAME (publications), EDM (cultural heritage), schema.org (generic),
DCAT (datasets).
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Vocabulary namespace prefixes
_CONTEXT = {
    "@vocab": "https://schema.org/",
    "bf": "http://id.loc.gov/ontologies/bibframe/",
    "edm": "http://www.europeana.eu/schemas/edm/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "dcterms": "http://purl.org/dc/terms/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}

# Entity type → vocabulary alignment
_TYPE_ALIGNMENTS: dict[str, dict[str, str]] = {
    "publication": {
        "schema_org": "ScholarlyArticle",
        "bibframe": "bf:Work",
        "edm": "edm:ProvidedCHO",
    },
    "dataset": {
        "schema_org": "Dataset",
        "dcat": "dcat:Dataset",
    },
    "person": {
        "schema_org": "Person",
        "foaf": "foaf:Person",
        "bibframe": "bf:Agent",
    },
    "organization": {
        "schema_org": "Organization",
        "foaf": "foaf:Organization",
        "bibframe": "bf:Agent",
    },
    "place": {
        "schema_org": "Place",
        "edm": "edm:Place",
        "dcat": "dcterms:Location",
        "bibframe": "bf:Place",
    },
    "concept": {
        "schema_org": "DefinedTerm",
        "skos": "skos:Concept",
    },
    "venue": {
        "schema_org": "Periodical",
        "bibframe": "bf:Serial",
    },
}


@dataclass
class LinkedDataExport:
    """Result of a linked-data export."""
    entity_id: int | None = None
    entity_type: str = ""
    format: str = "jsonld"  # jsonld | ntriples
    vocabulary: str = "schema_org"  # schema_org | bibframe | edm | dcat
    document: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(self.document, indent=2, ensure_ascii=False)


class JSONLDExporter:
    """Exports entities as JSON-LD aligned to standard vocabularies."""

    def export_entity(
        self,
        entity: dict[str, Any],
        vocabulary: str = "schema_org",
        include_provenance: bool = True,
    ) -> LinkedDataExport:
        """Export a single entity as JSON-LD."""
        entity_type = (entity.get("entity_type") or "").lower()
        entity_id = entity.get("id")
        warnings: list[str] = []

        # Resolve @type
        alignments = _TYPE_ALIGNMENTS.get(entity_type, {})
        ld_type = alignments.get(vocabulary)
        if not ld_type:
            ld_type = alignments.get("schema_org", "Thing")
            if vocabulary != "schema_org":
                warnings.append(
                    f"No {vocabulary} alignment for entity_type '{entity_type}'; "
                    f"falling back to schema.org '{ld_type}'"
                )

        doc: dict[str, Any] = {
            "@context": _CONTEXT,
            "@type": ld_type,
        }

        # Identifier
        if entity.get("canonical_id"):
            doc["@id"] = entity["canonical_id"]
        elif entity.get("enrichment_doi"):
            doc["@id"] = f"https://doi.org/{entity['enrichment_doi']}"

        # Core fields
        if entity.get("primary_label"):
            doc["name"] = entity["primary_label"]
        if entity.get("secondary_label"):
            doc["description"] = entity["secondary_label"]

        # Enrichment fields
        if entity.get("enrichment_doi"):
            doc["identifier"] = {
                "@type": "PropertyValue",
                "propertyID": "DOI",
                "value": entity["enrichment_doi"],
            }
        if entity.get("enrichment_citation_count"):
            doc["citationCount"] = entity["enrichment_citation_count"]
        if entity.get("enrichment_concepts"):
            concepts = entity["enrichment_concepts"]
            if isinstance(concepts, str):
                concepts = [c.strip() for c in concepts.split(",") if c.strip()]
            doc["about"] = [
                {"@type": "DefinedTerm", "name": c} for c in concepts
            ]

        # Authority fields
        if entity.get("authority_source"):
            doc["sameAs"] = self._build_same_as(entity)

        # Provenance
        if include_provenance:
            doc["sdPublisher"] = {"@type": "Organization", "name": "UKIP"}
            if entity.get("source"):
                doc["sdDatePublished"] = entity.get("created_at", "")
                doc["isBasedOn"] = entity["source"]

        # Geographic (place-specific)
        if entity_type == "place":
            doc = self._enrich_place(doc, entity, vocabulary)

        # Attributes expansion
        attrs = self._get_attrs(entity)
        if attrs.get("canonical_affiliations"):
            doc["affiliation"] = [
                self._export_affiliation(a) for a in attrs["canonical_affiliations"]
                if isinstance(a, dict)
            ]

        return LinkedDataExport(
            entity_id=entity_id,
            entity_type=entity_type,
            vocabulary=vocabulary,
            document=doc,
            warnings=warnings,
        )

    def export_geographic(
        self,
        geo_entity: dict[str, Any],
        vocabulary: str = "schema_org",
    ) -> LinkedDataExport:
        """Export a geographic entity as JSON-LD Place."""
        doc: dict[str, Any] = {
            "@context": _CONTEXT,
            "@type": self._geo_type(vocabulary),
            "name": geo_entity.get("name", ""),
        }

        if geo_entity.get("country_code"):
            doc["addressCountry"] = geo_entity["country_code"]
        if geo_entity.get("latitude") and geo_entity.get("longitude"):
            doc["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": geo_entity["latitude"],
                "longitude": geo_entity["longitude"],
            }
        if geo_entity.get("wikidata_id"):
            doc["sameAs"] = f"https://www.wikidata.org/entity/{geo_entity['wikidata_id']}"
        if geo_entity.get("geonames_id"):
            doc["identifier"] = {
                "@type": "PropertyValue",
                "propertyID": "GeoNames",
                "value": str(geo_entity["geonames_id"]),
            }

        return LinkedDataExport(
            entity_id=geo_entity.get("id"),
            entity_type="place",
            vocabulary=vocabulary,
            document=doc,
        )

    def _build_same_as(self, entity: dict[str, Any]) -> list[str]:
        """Build sameAs URIs from authority data."""
        same_as: list[str] = []
        authority_id = entity.get("authority_id", "")
        authority_source = entity.get("authority_source", "")

        if authority_source == "wikidata" and authority_id:
            same_as.append(f"https://www.wikidata.org/entity/{authority_id}")
        elif authority_source == "viaf" and authority_id:
            same_as.append(f"https://viaf.org/viaf/{authority_id}")
        elif authority_source == "orcid" and authority_id:
            same_as.append(f"https://orcid.org/{authority_id}")
        elif authority_id:
            same_as.append(authority_id)

        return same_as

    def _enrich_place(
        self, doc: dict[str, Any], entity: dict[str, Any], vocabulary: str,
    ) -> dict[str, Any]:
        attrs = self._get_attrs(entity)
        if attrs.get("latitude") and attrs.get("longitude"):
            doc["geo"] = {
                "@type": "GeoCoordinates",
                "latitude": attrs["latitude"],
                "longitude": attrs["longitude"],
            }
        if attrs.get("country_code"):
            doc["addressCountry"] = attrs["country_code"]
        return doc

    def _geo_type(self, vocabulary: str) -> str:
        mapping = _TYPE_ALIGNMENTS.get("place", {})
        return mapping.get(vocabulary, "Place")

    def _export_affiliation(self, aff: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "@type": "Organization",
            "name": aff.get("name") or aff.get("display_name", ""),
        }
        ror = aff.get("ror")
        if ror:
            result["identifier"] = {
                "@type": "PropertyValue",
                "propertyID": "ROR",
                "value": ror,
            }
            result["sameAs"] = f"https://ror.org/{ror}"
        cc = aff.get("country_code")
        if cc:
            result["addressCountry"] = cc
        return result

    def _get_attrs(self, entity: dict[str, Any]) -> dict[str, Any]:
        raw = entity.get("attributes_json", "{}")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                return {}
        return raw if isinstance(raw, dict) else {}
