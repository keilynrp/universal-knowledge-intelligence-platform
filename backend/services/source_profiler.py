"""Source Profiling Contract — Task 1.4.

Analyzes incoming data sources (CSV, REST, OpenAlex Works, Crossref Works)
to produce a SourceProfile: field profiles, semantic candidates, inferred
types, and sparsity maps.
"""
from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone as _tz

_UTC = _tz.utc
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SemanticRole(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    PLACE = "Place"
    CONCEPT = "Concept"
    PUBLICATION = "Publication"
    DATASET = "Dataset"
    IDENTIFIER = "Identifier"
    DATE = "Date"
    NUMERIC = "Numeric"
    UNKNOWN = "Unknown"


class InferredType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    JSON_OBJECT = "json_object"
    JSON_ARRAY = "json_array"
    URL = "url"
    EMAIL = "email"
    IDENTIFIER = "identifier"
    UNKNOWN = "unknown"


@dataclass
class FieldProfile:
    """Profile for a single field/column in the source data."""
    field_name: str
    inferred_type: InferredType = InferredType.UNKNOWN
    non_null_count: int = 0
    total_count: int = 0
    sparsity: float = 1.0  # fraction of nulls
    unique_count: int = 0
    sample_values: list[str] = field(default_factory=list)
    semantic_candidates: list[SemanticRole] = field(default_factory=list)
    candidate_identifiers: list[str] = field(default_factory=list)  # DOI, ORCID, ROR, etc.
    distribution: dict[str, int] = field(default_factory=dict)  # top-N value counts

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["inferred_type"] = self.inferred_type.value
        d["semantic_candidates"] = [c.value for c in self.semantic_candidates]
        return d


@dataclass
class SourceProfile:
    """Complete profile of a data source."""
    source_id: str
    total_rows: int = 0
    field_profiles: list[FieldProfile] = field(default_factory=list)
    semantic_candidates: dict[str, list[str]] = field(default_factory=dict)  # role → field names
    candidate_identifiers: dict[str, list[str]] = field(default_factory=dict)  # id_type → field names
    inferred_types: dict[str, str] = field(default_factory=dict)  # field → type
    sparsity_map: dict[str, float] = field(default_factory=dict)  # field → sparsity
    source_format: str = "unknown"  # csv | rest | openalex | crossref
    profiled_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "total_rows": self.total_rows,
            "field_profiles": [fp.to_dict() for fp in self.field_profiles],
            "semantic_candidates": self.semantic_candidates,
            "candidate_identifiers": self.candidate_identifiers,
            "inferred_types": self.inferred_types,
            "sparsity_map": self.sparsity_map,
            "source_format": self.source_format,
            "profiled_at": self.profiled_at,
        }


# ── Type inference ───────────────────────────────────────────────────────────

_DOI_RE = re.compile(r"^10\.\d{4,}/\S+$")
_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_ROR_RE = re.compile(r"^(https?://ror\.org/)?0[a-z0-9]{6}\d{2}$", re.IGNORECASE)
_ISSN_RE = re.compile(r"^\d{4}-\d{3}[\dX]$", re.IGNORECASE)
_ISBN_RE = re.compile(r"^(978|979)[\d-]{10,}$")
_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")


def _infer_type_single(value: str) -> InferredType:
    """Infer the type of a single string value."""
    v = value.strip()
    if not v:
        return InferredType.UNKNOWN

    # Identifiers first
    if _DOI_RE.match(v):
        return InferredType.IDENTIFIER
    if _ORCID_RE.match(v):
        return InferredType.IDENTIFIER
    if _ROR_RE.match(v):
        return InferredType.IDENTIFIER
    if _ISSN_RE.match(v):
        return InferredType.IDENTIFIER
    if v.lower().startswith("https://ror.org/") or v.lower().startswith("http://ror.org/"):
        return InferredType.IDENTIFIER
    if _URL_RE.match(v):
        return InferredType.URL
    if _EMAIL_RE.match(v):
        return InferredType.EMAIL

    # Date
    if _DATE_RE.match(v) or _ISO_DATE_RE.match(v):
        return InferredType.DATE

    # Boolean
    if v.lower() in {"true", "false", "yes", "no", "1", "0"}:
        return InferredType.BOOLEAN

    # Numeric
    try:
        int(v)
        return InferredType.INTEGER
    except ValueError:
        pass
    try:
        float(v)
        return InferredType.FLOAT
    except ValueError:
        pass

    # JSON
    if v.startswith("{"):
        try:
            json.loads(v)
            return InferredType.JSON_OBJECT
        except (ValueError, TypeError):
            pass
    if v.startswith("["):
        try:
            json.loads(v)
            return InferredType.JSON_ARRAY
        except (ValueError, TypeError):
            pass

    return InferredType.STRING


def _infer_type_majority(values: list[str]) -> InferredType:
    """Infer type from majority vote over non-empty values."""
    if not values:
        return InferredType.UNKNOWN
    non_empty = [v for v in values if v and v.strip()]
    if not non_empty:
        return InferredType.UNKNOWN
    types = Counter(_infer_type_single(v) for v in non_empty[:200])
    return types.most_common(1)[0][0]


# ── Semantic role detection ──────────────────────────────────────────────────

_PERSON_FIELDS = frozenset({
    "author", "authors", "creator", "contributor", "investigator",
    "researcher", "person", "name", "first_name", "last_name",
    "given_name", "family_name", "corresponding_author",
})

_ORG_FIELDS = frozenset({
    "institution", "institutions", "organization", "affiliation",
    "affiliations", "publisher", "funder", "university", "company",
})

_PLACE_FIELDS = frozenset({
    "country", "country_code", "city", "region", "state", "address",
    "location", "latitude", "longitude", "lat", "lon", "lng",
    "country_name", "geo", "geography",
})

_CONCEPT_FIELDS = frozenset({
    "concept", "concepts", "keyword", "keywords", "topic", "topics",
    "subject", "subjects", "category", "categories", "tag", "tags",
    "mesh", "mesh_terms", "field_of_study",
})

_PUB_FIELDS = frozenset({
    "title", "doi", "publication", "journal", "venue", "issn",
    "volume", "issue", "pages", "abstract", "citation_count",
    "cited_by_count", "publication_date", "published_date",
    "publication_year", "year",
})

_DATASET_FIELDS = frozenset({
    "dataset", "data_source", "source_url", "download_url",
    "file_name", "file_format", "data_format",
})

_ID_FIELDS = frozenset({
    "doi", "orcid", "ror", "ror_id", "isbn", "issn", "pmid",
    "openalex_id", "wikidata_id", "geonames_id", "osm_id",
    "identifier", "id", "external_id",
})


def _detect_semantic_roles(field_name: str, values: list[str]) -> list[SemanticRole]:
    """Detect possible semantic roles for a field."""
    roles: list[SemanticRole] = []
    fn = field_name.lower().replace("-", "_").replace(" ", "_")

    if fn in _PERSON_FIELDS:
        roles.append(SemanticRole.PERSON)
    if fn in _ORG_FIELDS:
        roles.append(SemanticRole.ORGANIZATION)
    if fn in _PLACE_FIELDS:
        roles.append(SemanticRole.PLACE)
    if fn in _CONCEPT_FIELDS:
        roles.append(SemanticRole.CONCEPT)
    if fn in _PUB_FIELDS:
        roles.append(SemanticRole.PUBLICATION)
    if fn in _DATASET_FIELDS:
        roles.append(SemanticRole.DATASET)
    if fn in _ID_FIELDS:
        roles.append(SemanticRole.IDENTIFIER)

    # Value-based detection for identifiers
    non_empty = [v for v in values if v and v.strip()][:50]
    if non_empty:
        doi_count = sum(1 for v in non_empty if _DOI_RE.match(v.strip()))
        if doi_count > len(non_empty) * 0.3:
            if SemanticRole.IDENTIFIER not in roles:
                roles.append(SemanticRole.IDENTIFIER)
            if SemanticRole.PUBLICATION not in roles:
                roles.append(SemanticRole.PUBLICATION)

        orcid_count = sum(1 for v in non_empty if _ORCID_RE.match(v.strip()))
        if orcid_count > len(non_empty) * 0.3:
            if SemanticRole.IDENTIFIER not in roles:
                roles.append(SemanticRole.IDENTIFIER)
            if SemanticRole.PERSON not in roles:
                roles.append(SemanticRole.PERSON)

        ror_count = sum(1 for v in non_empty if _ROR_RE.match(v.strip()))
        if ror_count > len(non_empty) * 0.3:
            if SemanticRole.IDENTIFIER not in roles:
                roles.append(SemanticRole.IDENTIFIER)
            if SemanticRole.ORGANIZATION not in roles:
                roles.append(SemanticRole.ORGANIZATION)

    if not roles:
        # Date heuristic
        if any(kw in fn for kw in ("date", "year", "time", "created", "updated")):
            roles.append(SemanticRole.DATE)

    return roles


def _detect_identifiers(field_name: str, values: list[str]) -> list[str]:
    """Detect identifier types present in values."""
    ids: list[str] = []
    fn = field_name.lower()
    non_empty = [v.strip() for v in values if v and v.strip()][:50]

    if "doi" in fn or any(_DOI_RE.match(v) for v in non_empty[:20]):
        ids.append("DOI")
    if "orcid" in fn or any(_ORCID_RE.match(v) for v in non_empty[:20]):
        ids.append("ORCID")
    if "ror" in fn or any(_ROR_RE.match(v) for v in non_empty[:20]):
        ids.append("ROR")
    if "issn" in fn or any(_ISSN_RE.match(v) for v in non_empty[:20]):
        ids.append("ISSN")
    if "isbn" in fn or any(_ISBN_RE.match(v) for v in non_empty[:20]):
        ids.append("ISBN")
    if "pmid" in fn:
        ids.append("PMID")
    if "openalex" in fn:
        ids.append("OpenAlex")

    return ids


# ── Profiler ─────────────────────────────────────────────────────────────────

_MAX_SAMPLE = 5
_MAX_DISTRIBUTION = 10


class SourceProfiler:
    """Analyze a tabular data source and produce a SourceProfile."""

    def profile_records(
        self,
        records: list[dict[str, Any]],
        source_id: str = "upload",
        source_format: str = "csv",
    ) -> SourceProfile:
        """Profile a list of flat dicts (rows)."""
        if not records:
            return SourceProfile(
                source_id=source_id,
                source_format=source_format,
                profiled_at=datetime.now(tz=_UTC).isoformat(),
            )

        total = len(records)
        all_fields: set[str] = set()
        for row in records:
            all_fields.update(row.keys())

        field_profiles: list[FieldProfile] = []
        semantic_map: dict[str, list[str]] = {}
        id_map: dict[str, list[str]] = {}
        type_map: dict[str, str] = {}
        sparsity_map: dict[str, float] = {}

        for fname in sorted(all_fields):
            values = [str(row.get(fname, "")) if row.get(fname) is not None else "" for row in records]
            non_null = [v for v in values if v.strip()]
            non_null_count = len(non_null)
            sparsity = 1.0 - (non_null_count / total) if total > 0 else 1.0
            unique = len(set(non_null))

            inferred = _infer_type_majority(non_null)
            roles = _detect_semantic_roles(fname, non_null)
            identifiers = _detect_identifiers(fname, non_null)

            # Sample values
            sample = list(dict.fromkeys(non_null[:_MAX_SAMPLE * 3]))[:_MAX_SAMPLE]

            # Distribution (top-N)
            dist_counter = Counter(non_null)
            distribution = dict(dist_counter.most_common(_MAX_DISTRIBUTION))

            fp = FieldProfile(
                field_name=fname,
                inferred_type=inferred,
                non_null_count=non_null_count,
                total_count=total,
                sparsity=round(sparsity, 4),
                unique_count=unique,
                sample_values=sample,
                semantic_candidates=roles,
                candidate_identifiers=identifiers,
                distribution=distribution,
            )
            field_profiles.append(fp)

            # Aggregation maps
            for role in roles:
                semantic_map.setdefault(role.value, []).append(fname)
            for id_type in identifiers:
                id_map.setdefault(id_type, []).append(fname)
            type_map[fname] = inferred.value
            sparsity_map[fname] = round(sparsity, 4)

        return SourceProfile(
            source_id=source_id,
            total_rows=total,
            field_profiles=field_profiles,
            semantic_candidates=semantic_map,
            candidate_identifiers=id_map,
            inferred_types=type_map,
            sparsity_map=sparsity_map,
            source_format=source_format,
            profiled_at=datetime.now(tz=_UTC).isoformat(),
        )

    def profile_openalex_works(
        self,
        works: list[dict[str, Any]],
        source_id: str = "openalex",
    ) -> SourceProfile:
        """Profile OpenAlex Works API response records."""
        flat_records = []
        for work in works:
            flat: dict[str, Any] = {
                "id": work.get("id", ""),
                "doi": work.get("doi", ""),
                "title": work.get("title", ""),
                "publication_date": work.get("publication_date", ""),
                "publication_year": str(work.get("publication_year", "")),
                "cited_by_count": str(work.get("cited_by_count", "")),
                "type": work.get("type", ""),
            }
            # Flatten authorships
            authorships = work.get("authorships") or []
            author_names = []
            institutions = []
            orcids = []
            rors = []
            for auth in authorships:
                author = auth.get("author") or {}
                name = author.get("display_name", "")
                if name:
                    author_names.append(name)
                orcid = author.get("orcid", "")
                if orcid:
                    orcids.append(orcid)
                for inst in auth.get("institutions") or []:
                    inst_name = inst.get("display_name", "")
                    if inst_name:
                        institutions.append(inst_name)
                    ror = inst.get("ror", "")
                    if ror:
                        rors.append(ror)

            flat["authors"] = "; ".join(author_names)
            flat["institutions"] = "; ".join(institutions)
            flat["orcids"] = "; ".join(orcids)
            flat["rors"] = "; ".join(rors)

            # Concepts
            concepts = work.get("concepts") or work.get("topics") or []
            flat["concepts"] = "; ".join(
                c.get("display_name", "") for c in concepts if isinstance(c, dict)
            )

            # Primary location
            loc = work.get("primary_location") or {}
            source = loc.get("source") or {}
            flat["journal"] = source.get("display_name", "")
            flat["issn"] = "; ".join(source.get("issn") or [])

            flat_records.append(flat)

        return self.profile_records(flat_records, source_id=source_id, source_format="openalex")

    def profile_crossref_works(
        self,
        works: list[dict[str, Any]],
        source_id: str = "crossref",
    ) -> SourceProfile:
        """Profile Crossref Works API response records."""
        flat_records = []
        for work in works:
            flat: dict[str, Any] = {
                "doi": work.get("DOI", ""),
                "title": "; ".join(work.get("title") or []),
                "type": work.get("type", ""),
                "publisher": work.get("publisher", ""),
                "container_title": "; ".join(work.get("container-title") or []),
                "issn": "; ".join(work.get("ISSN") or []),
                "isbn": "; ".join(work.get("ISBN") or []),
            }
            # Authors
            authors = work.get("author") or []
            flat["authors"] = "; ".join(
                f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                for a in authors if isinstance(a, dict)
            )
            orcids = [
                a.get("ORCID", "").replace("http://orcid.org/", "").replace("https://orcid.org/", "")
                for a in authors if a.get("ORCID")
            ]
            flat["orcids"] = "; ".join(orcids)

            # Affiliations
            affs = []
            for a in authors:
                for aff in (a.get("affiliation") or []):
                    name = aff.get("name", "")
                    if name:
                        affs.append(name)
            flat["affiliations"] = "; ".join(affs)

            # Date
            issued = work.get("issued") or {}
            parts = (issued.get("date-parts") or [[]])[0]
            flat["publication_year"] = str(parts[0]) if parts else ""

            flat["cited_by_count"] = str(work.get("is-referenced-by-count", ""))

            flat_records.append(flat)

        return self.profile_records(flat_records, source_id=source_id, source_format="crossref")

    # ── API facade methods ────────────────────────────────────────────────────

    # In-memory profile store (production would persist to DB)
    _profile_store: dict[str, "SourceProfile"] = {}

    def analyze(
        self,
        source_id: str,
        field_names: list[str],
        sample_values: dict[str, list],
        payload_type: str = "csv",
    ) -> SourceProfile:
        """API-level analyze: build records from field_names + sample_values, profile, and store."""
        if not field_names and sample_values:
            field_names = list(sample_values.keys())

        # Build synthetic records from sample_values
        max_rows = max((len(v) for v in sample_values.values()), default=0)
        records: list[dict[str, Any]] = []
        for i in range(max_rows):
            row = {}
            for fname in field_names:
                vals = sample_values.get(fname, [])
                row[fname] = vals[i] if i < len(vals) else None
            records.append(row)

        profile = self.profile_records(records, source_id=source_id, source_format=payload_type)
        SourceProfiler._profile_store[source_id] = profile
        return profile

    def get_profile(self, source_id: str) -> SourceProfile | None:
        """Retrieve a previously stored profile."""
        return SourceProfiler._profile_store.get(source_id)
