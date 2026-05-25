"""Geographic Entity semantic layer — Task 1.2.

Provides the GeographicEntity dataclass, ID normalization helpers,
hierarchy traversal, and alias support.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class GeoEntityType(str, Enum):
    COUNTRY = "country"
    REGION = "region"
    CITY = "city"
    CAMPUS = "campus"
    ADDRESS = "address"
    SPATIAL_AREA = "spatial_area"
    UNKNOWN = "unknown"


# ── ISO 3166-1 alpha-2 codes ────────────────────────────────────────────────
# Subset for fast validation; full set loaded lazily.

_ISO_ALPHA2 = frozenset({
    "AF", "AL", "DZ", "AD", "AO", "AG", "AR", "AM", "AU", "AT", "AZ",
    "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BT", "BO", "BA",
    "BW", "BR", "BN", "BG", "BF", "BI", "CV", "KH", "CM", "CA", "CF",
    "TD", "CL", "CN", "CO", "KM", "CG", "CD", "CR", "CI", "HR", "CU",
    "CY", "CZ", "DK", "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER",
    "EE", "SZ", "ET", "FJ", "FI", "FR", "GA", "GM", "GE", "DE", "GH",
    "GR", "GD", "GT", "GN", "GW", "GY", "HT", "HN", "HU", "IS", "IN",
    "ID", "IR", "IQ", "IE", "IL", "IT", "JM", "JP", "JO", "KZ", "KE",
    "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY",
    "LI", "LT", "LU", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MR",
    "MU", "MX", "FM", "MD", "MC", "MN", "ME", "MA", "MZ", "MM", "NA",
    "NR", "NP", "NL", "NZ", "NI", "NE", "NG", "MK", "NO", "OM", "PK",
    "PW", "PA", "PG", "PY", "PE", "PH", "PL", "PT", "QA", "RO", "RU",
    "RW", "KN", "LC", "VC", "WS", "SM", "ST", "SA", "SN", "RS", "SC",
    "SL", "SG", "SK", "SI", "SB", "SO", "ZA", "SS", "ES", "LK", "SD",
    "SR", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TO",
    "TT", "TN", "TR", "TM", "TV", "UG", "UA", "AE", "GB", "US", "UY",
    "UZ", "VU", "VE", "VN", "YE", "ZM", "ZW",
    # Common territories
    "HK", "MO", "PR", "GU", "VI", "AS", "MP", "AW", "CW", "SX", "BM",
    "KY", "GI", "GL", "FO", "FK", "GG", "JE", "IM", "RE", "YT", "GP",
    "MQ", "GF", "PF", "NC", "WF", "BL", "MF", "PM", "AX", "CC", "CX",
    "NF", "TK", "NU", "CK", "IO", "SH", "AC", "TA", "MS", "TC", "VG",
    "AI", "BQ", "EH", "PS", "XK",
})


@dataclass
class GeographicEntity:
    """Domain model for a geographic entity."""

    id: int | None = None
    type: GeoEntityType = GeoEntityType.UNKNOWN
    name: str = ""
    parent_id: int | None = None
    coordinates: tuple[float, float] | None = None  # (lat, lon)
    country_code: str | None = None  # ISO 3166-1 alpha-2
    geonames_id: int | None = None
    wikidata_id: str | None = None  # e.g. Q30
    osm_id: int | None = None
    aliases: list[str] = field(default_factory=list)
    geometry: dict[str, Any] | None = None  # GeoJSON
    provenance: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d


# ── ID normalization ─────────────────────────────────────────────────────────

def validate_country_code(code: str | None) -> str | None:
    """Return uppercase ISO 3166-1 alpha-2 code if valid, else None."""
    if not code:
        return None
    normalized = code.strip().upper()
    return normalized if normalized in _ISO_ALPHA2 else None


def normalize_geonames_id(value: str | int | None) -> int | None:
    """Extract numeric GeoNames ID from various formats."""
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    # Handle URLs like https://www.geonames.org/3865483
    match = re.search(r"(\d{4,})", text)
    return int(match.group(1)) if match else None


def normalize_wikidata_qid(value: str | None) -> str | None:
    """Normalize Wikidata QID to Q-prefixed form (e.g. Q30)."""
    if not value:
        return None
    text = str(value).strip()
    # Handle full URLs
    text = text.replace("https://www.wikidata.org/wiki/", "")
    text = text.replace("http://www.wikidata.org/entity/", "")
    text = text.replace("https://www.wikidata.org/entity/", "")
    text = text.strip("/")
    match = re.match(r"^[Qq](\d+)$", text)
    if match:
        return f"Q{match.group(1)}"
    # Bare numeric
    if text.isdigit():
        return f"Q{text}"
    return None


def normalize_osm_id(value: str | int | None) -> int | None:
    """Extract numeric OSM ID."""
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value).strip()
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


# ── Hierarchy traversal ──────────────────────────────────────────────────────

def build_ancestor_chain(
    entity: GeographicEntity,
    lookup: dict[int, GeographicEntity],
    max_depth: int = 10,
) -> list[GeographicEntity]:
    """Walk parent_id chain upward, returning [entity, parent, grandparent, ...]."""
    chain: list[GeographicEntity] = [entity]
    current = entity
    seen: set[int] = {current.id} if current.id is not None else set()
    for _ in range(max_depth):
        if current.parent_id is None or current.parent_id not in lookup:
            break
        if current.parent_id in seen:
            break  # cycle guard
        parent = lookup[current.parent_id]
        chain.append(parent)
        if parent.id is not None:
            seen.add(parent.id)
        current = parent
    return chain


# ── Alias matching ───────────────────────────────────────────────────────────

def normalize_geo_name(name: str) -> str:
    """Normalize a geographic name for comparison."""
    import unicodedata
    text = unicodedata.normalize("NFD", name)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def matches_alias(entity: GeographicEntity, query: str) -> bool:
    """Check if a query string matches the entity name or any alias."""
    normalized_query = normalize_geo_name(query)
    if not normalized_query:
        return False
    if normalize_geo_name(entity.name) == normalized_query:
        return True
    return any(normalize_geo_name(alias) == normalized_query for alias in entity.aliases)


def create_geographic_entity_from_dict(raw: dict[str, Any]) -> GeographicEntity:
    """Build a GeographicEntity from a raw dict (e.g. API payload or DB row)."""
    geo_type = raw.get("type", "unknown")
    try:
        entity_type = GeoEntityType(geo_type)
    except ValueError:
        entity_type = GeoEntityType.UNKNOWN

    coords = raw.get("coordinates")
    if isinstance(coords, (list, tuple)) and len(coords) == 2:
        try:
            coordinates = (float(coords[0]), float(coords[1]))
        except (TypeError, ValueError):
            coordinates = None
    else:
        coordinates = None

    aliases = raw.get("aliases") or []
    if isinstance(aliases, str):
        try:
            aliases = json.loads(aliases)
        except (TypeError, ValueError):
            aliases = [aliases]

    geometry = raw.get("geometry")
    if isinstance(geometry, str):
        try:
            geometry = json.loads(geometry)
        except (TypeError, ValueError):
            geometry = None

    return GeographicEntity(
        id=raw.get("id"),
        type=entity_type,
        name=raw.get("name", ""),
        parent_id=raw.get("parent_id"),
        coordinates=coordinates,
        country_code=validate_country_code(raw.get("country_code")),
        geonames_id=normalize_geonames_id(raw.get("geonames_id")),
        wikidata_id=normalize_wikidata_qid(raw.get("wikidata_id")),
        osm_id=normalize_osm_id(raw.get("osm_id")),
        aliases=aliases if isinstance(aliases, list) else [],
        geometry=geometry if isinstance(geometry, dict) else None,
        provenance=raw.get("provenance", "unknown"),
    )
