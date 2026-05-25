"""Geographic Reconciliation Service — Task 2.4.

Reconciles raw geographic strings (country names, codes, city names)
against known entities. Produces candidates with confidence scores.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.services.geographic_entities import (
    GeoEntityType,
    GeographicEntity,
    normalize_geo_name,
    validate_country_code,
)


@dataclass
class GeoCandidate:
    """A reconciliation candidate for a geographic value."""
    entity: GeographicEntity
    confidence: float  # 0.0 – 1.0
    evidence: list[str] = field(default_factory=list)
    source_value: str = ""
    source_field: str = ""
    extraction_method: str = "unknown"  # iso_exact | name_exact | name_alias | coordinate | ambiguous

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["entity"]["type"] = self.entity.type.value
        return d


# ── Common country name → ISO 3166-1 alpha-2 ────────────────────────────────

_COUNTRY_NAME_MAP: dict[str, str] = {
    "united states": "US", "united states of america": "US", "usa": "US", "u.s.a.": "US", "u.s.": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "england": "GB",
    "germany": "DE", "deutschland": "DE", "allemagne": "DE",
    "france": "FR", "francia": "FR",
    "spain": "ES", "espana": "ES", "españa": "ES",
    "italy": "IT", "italia": "IT",
    "japan": "JP", "japon": "JP",
    "china": "CN", "peoples republic of china": "CN", "p.r. china": "CN", "p.r.china": "CN",
    "south korea": "KR", "republic of korea": "KR", "korea": "KR",
    "north korea": "KP",
    "canada": "CA",
    "australia": "AU",
    "brazil": "BR", "brasil": "BR",
    "india": "IN",
    "russia": "RU", "russian federation": "RU",
    "mexico": "MX", "méxico": "MX",
    "argentina": "AR",
    "chile": "CL",
    "colombia": "CO",
    "peru": "PE", "perú": "PE",
    "netherlands": "NL", "holland": "NL",
    "belgium": "BE", "belgique": "BE", "belgie": "BE",
    "switzerland": "CH", "suisse": "CH", "schweiz": "CH",
    "austria": "AT", "österreich": "AT",
    "sweden": "SE", "sverige": "SE",
    "norway": "NO", "norge": "NO",
    "denmark": "DK", "danmark": "DK",
    "finland": "FI", "suomi": "FI",
    "portugal": "PT",
    "greece": "GR", "hellas": "GR",
    "turkey": "TR", "türkiye": "TR", "turkiye": "TR",
    "poland": "PL", "polska": "PL",
    "czech republic": "CZ", "czechia": "CZ",
    "ireland": "IE",
    "new zealand": "NZ",
    "south africa": "ZA",
    "israel": "IL",
    "saudi arabia": "SA",
    "united arab emirates": "AE", "uae": "AE",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "philippines": "PH",
    "vietnam": "VN", "viet nam": "VN",
    "egypt": "EG",
    "nigeria": "NG",
    "kenya": "KE",
    "pakistan": "PK",
    "bangladesh": "BD",
    "taiwan": "TW",
    "hong kong": "HK",
    "iran": "IR",
    "iraq": "IQ",
    "ukraine": "UA",
    "romania": "RO",
    "hungary": "HU", "magyarorszag": "HU",
    "slovakia": "SK",
    "croatia": "HR", "hrvatska": "HR",
    "serbia": "RS", "srbija": "RS",
    "bulgaria": "BG",
    "slovenia": "SI",
    "estonia": "EE", "eesti": "EE",
    "latvia": "LV", "latvija": "LV",
    "lithuania": "LT", "lietuva": "LT",
    "luxembourg": "LU",
    "iceland": "IS",
    "cyprus": "CY",
    "malta": "MT",
    "cuba": "CU",
    "venezuela": "VE",
    "ecuador": "EC",
    "uruguay": "UY",
    "paraguay": "PY",
    "bolivia": "BO",
    "costa rica": "CR",
    "panama": "PA",
    "guatemala": "GT",
    "honduras": "HN",
    "el salvador": "SV",
    "nicaragua": "NI",
    "dominican republic": "DO",
    "jamaica": "JM",
    "morocco": "MA", "maroc": "MA",
    "tunisia": "TN",
    "algeria": "DZ",
    "ethiopia": "ET",
    "ghana": "GH",
    "tanzania": "TZ",
    "uganda": "UG",
    "mozambique": "MZ",
    "nepal": "NP",
    "sri lanka": "LK",
    "cambodia": "KH",
    "myanmar": "MM", "burma": "MM",
    "laos": "LA",
    "mongolia": "MN",
    "kazakhstan": "KZ",
    "uzbekistan": "UZ",
    "georgia (country)": "GE",
    "armenia": "AM",
    "azerbaijan": "AZ",
    "qatar": "QA",
    "kuwait": "KW",
    "bahrain": "BH",
    "oman": "OM",
    "jordan": "JO",
    "lebanon": "LB",
}

# Ambiguous names that map to multiple entities
_AMBIGUOUS_NAMES: dict[str, list[str]] = {
    "georgia": ["GE", "US-GA"],  # country vs US state
}


class GeographicReconciliationService:
    """Reconcile raw geographic strings to normalized entities."""

    def reconcile(
        self,
        value: str,
        source_field: str = "unknown",
    ) -> list[GeoCandidate]:
        """Reconcile a single value. Returns candidates sorted by confidence."""
        if not value or not value.strip():
            return []

        candidates: list[GeoCandidate] = []
        clean = value.strip()

        # 1. Try exact ISO code
        iso = validate_country_code(clean)
        if iso:
            candidates.append(GeoCandidate(
                entity=GeographicEntity(
                    type=GeoEntityType.COUNTRY,
                    name=iso,
                    country_code=iso,
                ),
                confidence=1.0,
                evidence=["exact_iso_code"],
                source_value=clean,
                source_field=source_field,
                extraction_method="iso_exact",
            ))
            return candidates

        # 2. Normalize and try country name map
        normalized = _normalize_for_lookup(clean)

        # Check ambiguous first
        if normalized in _AMBIGUOUS_NAMES:
            codes = _AMBIGUOUS_NAMES[normalized]
            for code in codes:
                real_code = code.split("-")[0] if "-" in code else code
                validated = validate_country_code(real_code)
                candidates.append(GeoCandidate(
                    entity=GeographicEntity(
                        type=GeoEntityType.COUNTRY if "-" not in code else GeoEntityType.REGION,
                        name=clean,
                        country_code=validated,
                    ),
                    confidence=0.5,
                    evidence=["ambiguous_name", f"possible_{code}"],
                    source_value=clean,
                    source_field=source_field,
                    extraction_method="ambiguous",
                ))
            return sorted(candidates, key=lambda c: c.confidence, reverse=True)

        # Exact country name
        if normalized in _COUNTRY_NAME_MAP:
            iso = _COUNTRY_NAME_MAP[normalized]
            candidates.append(GeoCandidate(
                entity=GeographicEntity(
                    type=GeoEntityType.COUNTRY,
                    name=clean,
                    country_code=iso,
                ),
                confidence=0.95,
                evidence=["exact_country_name"],
                source_value=clean,
                source_field=source_field,
                extraction_method="name_exact",
            ))
            return candidates

        # 3. Alias / variant matching (diacritic-stripped)
        stripped = _strip_diacritics(normalized)
        for name, code in _COUNTRY_NAME_MAP.items():
            if _strip_diacritics(name) == stripped and name != normalized:
                candidates.append(GeoCandidate(
                    entity=GeographicEntity(
                        type=GeoEntityType.COUNTRY,
                        name=clean,
                        country_code=code,
                    ),
                    confidence=0.85,
                    evidence=["variant_alias_match"],
                    source_value=clean,
                    source_field=source_field,
                    extraction_method="name_alias",
                ))
                return candidates

        # 4. No match — return empty
        return candidates

    def reconcile_coordinates(
        self,
        lat: float,
        lon: float,
        source_field: str = "coordinates",
    ) -> list[GeoCandidate]:
        """Create a spatial entity from coordinates."""
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return []
        return [GeoCandidate(
            entity=GeographicEntity(
                type=GeoEntityType.SPATIAL_AREA,
                name=f"({lat:.4f}, {lon:.4f})",
                coordinates=(lat, lon),
            ),
            confidence=0.7,
            evidence=["coordinate_input"],
            source_value=f"{lat},{lon}",
            source_field=source_field,
            extraction_method="coordinate",
        )]

    def extract_from_affiliation(
        self,
        affiliation_text: str,
    ) -> list[GeoCandidate]:
        """Extract geographic candidates from an affiliation string.

        Splits on commas and tries the last 1-2 tokens as potential country/city.
        """
        if not affiliation_text:
            return []

        parts = [p.strip() for p in affiliation_text.split(",") if p.strip()]
        candidates: list[GeoCandidate] = []

        # Try last token as country
        for token in reversed(parts[-2:]):
            result = self.reconcile(token, source_field="affiliation")
            candidates.extend(result)

        # Deduplicate by country_code
        seen: set[str | None] = set()
        deduped: list[GeoCandidate] = []
        for c in candidates:
            key = c.entity.country_code
            if key not in seen:
                seen.add(key)
                deduped.append(c)

        return deduped

    def extract_from_record(
        self,
        record: dict[str, Any],
    ) -> list[GeoCandidate]:
        """Extract geographic candidates from a flat record dict."""
        candidates: list[GeoCandidate] = []

        # Direct country fields
        for field_name in ("country", "country_code", "country_name"):
            val = record.get(field_name)
            if val and isinstance(val, str):
                candidates.extend(self.reconcile(val, source_field=field_name))

        # Coordinate fields
        lat = record.get("latitude") or record.get("lat")
        lon = record.get("longitude") or record.get("lon") or record.get("lng")
        if lat is not None and lon is not None:
            try:
                candidates.extend(self.reconcile_coordinates(float(lat), float(lon)))
            except (TypeError, ValueError):
                pass

        # Affiliation field
        for field_name in ("affiliation", "affiliations", "institution"):
            val = record.get(field_name)
            if val and isinstance(val, str):
                candidates.extend(self.extract_from_affiliation(val))

        # Deduplicate
        seen: set[str] = set()
        deduped: list[GeoCandidate] = []
        for c in candidates:
            key = f"{c.entity.country_code}_{c.entity.type.value}_{c.extraction_method}"
            if key not in seen:
                seen.add(key)
                deduped.append(c)

        return sorted(deduped, key=lambda c: c.confidence, reverse=True)


def _normalize_for_lookup(text: str) -> str:
    """Normalize text for country name lookup."""
    result = text.casefold().strip()
    result = re.sub(r"[^\w\s.]", " ", result)
    return re.sub(r"\s+", " ", result).strip()


def _strip_diacritics(text: str) -> str:
    """Remove diacritical marks for fuzzy matching."""
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
