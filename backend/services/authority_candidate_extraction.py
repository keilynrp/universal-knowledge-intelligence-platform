"""Authority Candidate Extraction — Task 3.5.

Extracts authority resolution candidates from entity data across
6 families: person, institution, identifier, place, venue, concept.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

_ORCID_RE = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
_DOI_RE = re.compile(r"10\.\d{4,}/\S+")
_ROR_RE = re.compile(r"(https?://ror\.org/)?0[a-z0-9]{6}\d{2}", re.IGNORECASE)
_ISSN_RE = re.compile(r"\d{4}-\d{3}[\dX]", re.IGNORECASE)


class CandidateFamily(str, Enum):
    PERSON = "person"
    INSTITUTION = "institution"
    IDENTIFIER = "identifier"
    PLACE = "place"
    VENUE = "venue"
    CONCEPT = "concept"


class CandidateOrigin(str, Enum):
    SOURCE = "source"
    ENRICHMENT = "enrichment"
    PRIOR_AUTHORITY = "prior_authority"


@dataclass
class AuthorityCandidate:
    """A candidate for authority resolution."""
    family: CandidateFamily
    label: str
    origin: CandidateOrigin = CandidateOrigin.SOURCE
    confidence: float = 0.0
    identifiers: dict[str, str] = field(default_factory=dict)  # e.g. {"orcid": "0000-...", "ror": "..."}
    context: dict[str, Any] = field(default_factory=dict)  # extra metadata
    entity_id: int | None = None
    dedup_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["family"] = self.family.value
        d["origin"] = self.origin.value
        return d


class AuthorityCandidateExtractor:
    """Extracts authority candidates from entity data."""

    def extract(
        self,
        entity: dict[str, Any],
        entity_id: int | None = None,
    ) -> list[AuthorityCandidate]:
        """Extract all candidate families from a single entity dict."""
        candidates: list[AuthorityCandidate] = []
        attrs = self._get_attrs(entity)
        has_enrichment = entity.get("enrichment_status") == "done"

        candidates.extend(self._extract_persons(entity, attrs, entity_id, has_enrichment))
        candidates.extend(self._extract_institutions(attrs, entity_id, has_enrichment))
        candidates.extend(self._extract_identifiers(entity, attrs, entity_id))
        candidates.extend(self._extract_places(attrs, entity_id))
        candidates.extend(self._extract_venues(entity, attrs, entity_id, has_enrichment))
        candidates.extend(self._extract_concepts(entity, attrs, entity_id, has_enrichment))

        return self._deduplicate(candidates)

    def _get_attrs(self, entity: dict[str, Any]) -> dict[str, Any]:
        raw = entity.get("attributes_json", "{}")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                return {}
        return raw if isinstance(raw, dict) else {}

    # ── Person candidates ────────────────────────────────────────────────

    def _extract_persons(
        self, entity: dict[str, Any], attrs: dict[str, Any],
        entity_id: int | None, enriched: bool,
    ) -> list[AuthorityCandidate]:
        candidates: list[AuthorityCandidate] = []
        origin = CandidateOrigin.ENRICHMENT if enriched else CandidateOrigin.SOURCE
        confidence = 0.7 if enriched else 0.4

        # From author_affiliations (structured)
        for aa in attrs.get("author_affiliations") or []:
            if not isinstance(aa, dict):
                continue
            name = aa.get("author_name") or aa.get("name") or ""
            if not name:
                continue
            ids: dict[str, str] = {}
            orcid = aa.get("orcid") or ""
            if orcid:
                ids["orcid"] = orcid
                confidence = 0.85
            candidates.append(AuthorityCandidate(
                family=CandidateFamily.PERSON,
                label=name,
                origin=origin,
                confidence=confidence,
                identifiers=ids,
                context={"affiliation": aa.get("institutions", [])},
                entity_id=entity_id,
                dedup_key=f"person:{orcid or name.lower()}",
            ))

        # From secondary_label (authors text)
        secondary = entity.get("secondary_label") or ""
        if secondary and not candidates:
            for author in secondary.split(","):
                name = author.strip()
                if name and len(name) > 2:
                    candidates.append(AuthorityCandidate(
                        family=CandidateFamily.PERSON,
                        label=name,
                        origin=CandidateOrigin.SOURCE,
                        confidence=0.3,
                        entity_id=entity_id,
                        dedup_key=f"person:{name.lower()}",
                    ))

        return candidates

    # ── Institution candidates ───────────────────────────────────────────

    def _extract_institutions(
        self, attrs: dict[str, Any], entity_id: int | None, enriched: bool,
    ) -> list[AuthorityCandidate]:
        candidates: list[AuthorityCandidate] = []
        origin = CandidateOrigin.ENRICHMENT if enriched else CandidateOrigin.SOURCE

        for inst in attrs.get("canonical_affiliations") or []:
            if not isinstance(inst, dict):
                continue
            name = inst.get("name") or inst.get("display_name") or ""
            if not name:
                continue
            ids: dict[str, str] = {}
            ror = inst.get("ror") or ""
            if ror:
                ids["ror"] = ror
            oaid = inst.get("openalex_id") or ""
            if oaid:
                ids["openalex"] = oaid
            confidence = 0.9 if ror else 0.6 if oaid else 0.4
            candidates.append(AuthorityCandidate(
                family=CandidateFamily.INSTITUTION,
                label=name,
                origin=origin,
                confidence=confidence,
                identifiers=ids,
                context={"country_code": inst.get("country_code")},
                entity_id=entity_id,
                dedup_key=f"institution:{ror or oaid or name.lower()}",
            ))

        return candidates

    # ── Identifier candidates ────────────────────────────────────────────

    def _extract_identifiers(
        self, entity: dict[str, Any], attrs: dict[str, Any], entity_id: int | None,
    ) -> list[AuthorityCandidate]:
        candidates: list[AuthorityCandidate] = []

        doi = entity.get("enrichment_doi") or ""
        if doi and _DOI_RE.search(doi):
            candidates.append(AuthorityCandidate(
                family=CandidateFamily.IDENTIFIER,
                label=doi,
                origin=CandidateOrigin.ENRICHMENT,
                confidence=0.95,
                identifiers={"doi": doi},
                entity_id=entity_id,
                dedup_key=f"identifier:doi:{doi.lower()}",
            ))

        # ORCIDs from author affiliations
        for aa in attrs.get("author_affiliations") or []:
            if isinstance(aa, dict):
                orcid = aa.get("orcid") or ""
                if orcid and _ORCID_RE.match(orcid):
                    candidates.append(AuthorityCandidate(
                        family=CandidateFamily.IDENTIFIER,
                        label=orcid,
                        origin=CandidateOrigin.ENRICHMENT,
                        confidence=0.95,
                        identifiers={"orcid": orcid},
                        entity_id=entity_id,
                        dedup_key=f"identifier:orcid:{orcid}",
                    ))

        # RORs from canonical affiliations
        for inst in attrs.get("canonical_affiliations") or []:
            if isinstance(inst, dict):
                ror = inst.get("ror") or ""
                if ror and _ROR_RE.match(ror):
                    candidates.append(AuthorityCandidate(
                        family=CandidateFamily.IDENTIFIER,
                        label=ror,
                        origin=CandidateOrigin.ENRICHMENT,
                        confidence=0.95,
                        identifiers={"ror": ror},
                        entity_id=entity_id,
                        dedup_key=f"identifier:ror:{ror.lower()}",
                    ))

        return candidates

    # ── Place candidates ─────────────────────────────────────────────────

    def _extract_places(
        self, attrs: dict[str, Any], entity_id: int | None,
    ) -> list[AuthorityCandidate]:
        candidates: list[AuthorityCandidate] = []
        seen_countries: set[str] = set()

        for inst in attrs.get("canonical_affiliations") or []:
            if isinstance(inst, dict):
                cc = inst.get("country_code") or ""
                if cc and cc.upper() not in seen_countries:
                    seen_countries.add(cc.upper())
                    candidates.append(AuthorityCandidate(
                        family=CandidateFamily.PLACE,
                        label=cc.upper(),
                        origin=CandidateOrigin.ENRICHMENT,
                        confidence=0.8,
                        identifiers={"iso_country": cc.upper()},
                        entity_id=entity_id,
                        dedup_key=f"place:country:{cc.upper()}",
                    ))

        return candidates

    # ── Venue candidates ─────────────────────────────────────────────────

    def _extract_venues(
        self, entity: dict[str, Any], attrs: dict[str, Any],
        entity_id: int | None, enriched: bool,
    ) -> list[AuthorityCandidate]:
        candidates: list[AuthorityCandidate] = []
        venue = attrs.get("venue") or attrs.get("journal") or ""
        if venue:
            ids: dict[str, str] = {}
            issn = attrs.get("issn") or ""
            if issn:
                ids["issn"] = issn
            candidates.append(AuthorityCandidate(
                family=CandidateFamily.VENUE,
                label=venue,
                origin=CandidateOrigin.ENRICHMENT if enriched else CandidateOrigin.SOURCE,
                confidence=0.7 if issn else 0.5,
                identifiers=ids,
                entity_id=entity_id,
                dedup_key=f"venue:{issn or venue.lower()}",
            ))
        return candidates

    # ── Concept candidates ───────────────────────────────────────────────

    def _extract_concepts(
        self, entity: dict[str, Any], attrs: dict[str, Any],
        entity_id: int | None, enriched: bool,
    ) -> list[AuthorityCandidate]:
        candidates: list[AuthorityCandidate] = []
        concepts_raw = entity.get("enrichment_concepts") or ""
        if concepts_raw:
            for concept in concepts_raw.split(","):
                concept = concept.strip()
                if concept and len(concept) > 2:
                    candidates.append(AuthorityCandidate(
                        family=CandidateFamily.CONCEPT,
                        label=concept,
                        origin=CandidateOrigin.ENRICHMENT if enriched else CandidateOrigin.SOURCE,
                        confidence=0.6,
                        entity_id=entity_id,
                        dedup_key=f"concept:{concept.lower()}",
                    ))
        return candidates

    # ── Deduplication ────────────────────────────────────────────────────

    def _deduplicate(self, candidates: list[AuthorityCandidate]) -> list[AuthorityCandidate]:
        """Deduplicate candidates by dedup_key, keeping highest confidence."""
        best: dict[str, AuthorityCandidate] = {}
        for c in candidates:
            if not c.dedup_key:
                best[f"_no_key_{id(c)}"] = c
                continue
            existing = best.get(c.dedup_key)
            if existing is None or c.confidence > existing.confidence:
                best[c.dedup_key] = c
        return list(best.values())
