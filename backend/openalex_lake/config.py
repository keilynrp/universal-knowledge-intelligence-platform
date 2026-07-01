"""LakeScope — declarative description of *what* OpenAlex slice to ingest.

The same LakeScope drives both the API puller (targeted subset) and, later, the
snapshot loader (full corpus): widening the scope is a config change, not a
rewrite. Sizes are governed here, not in the ingest loop.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Optional

# Default targeted subset: the journals we already score (NIF/Bayes) over a
# reasonable historical window. Small enough for the API path, useful day one.
DEFAULT_YEAR_FROM = 2010
DEFAULT_YEAR_TO = 2025

# OpenAlex entity types the lake understands. Works is the fact source; the rest
# are dimensions (loaded full from the snapshot, or derived from works).
WORK_ENTITY = "works"
DIMENSION_ENTITIES = ("sources", "institutions", "topics", "publishers", "funders")


@dataclass(frozen=True)
class LakeScope:
    """Immutable ingestion scope. Compose filters to bound the subset.

    An empty/None filter means "no constraint on this dimension". At least one
    of issn_l / field_ids should be set for the API path, otherwise the pull is
    effectively the whole corpus (only sensible against the snapshot).
    """
    issn_l: tuple[str, ...] = ()          # host source ISSN-L allowlist
    field_ids: tuple[int, ...] = ()        # OpenAlex topic field ids (e.g. 27 = Medicine)
    institution_ror: tuple[str, ...] = ()  # ROR ids
    country_codes: tuple[str, ...] = ()    # ISO-2 country codes
    year_from: Optional[int] = DEFAULT_YEAR_FROM
    year_to: Optional[int] = DEFAULT_YEAR_TO

    # Heaviest table (~30-40 refs/work). Off by default to respect storage.
    include_citations: bool = False

    # Source of works: "api" for the targeted subset, "snapshot" once storage
    # allows the full corpus. Transform/schema are identical either way.
    works_source: str = "api"

    def with_issns(self, issns: list[str]) -> "LakeScope":
        return replace(self, issn_l=tuple(dict.fromkeys(i for i in issns if i)))

    def is_bounded(self) -> bool:
        """True if the scope constrains works enough for the API path."""
        return bool(self.issn_l or self.field_ids or self.institution_ror)


@dataclass(frozen=True)
class LakeSettings:
    """Runtime/ops settings, kept separate from the analytical scope."""
    db_path: str = field(
        default_factory=lambda: os.environ.get(
            "OPENALEX_LAKE_DB", "data/openalex_lake.duckdb"
        )
    )
    # OpenAlex "polite pool" wants a contact; a premium key lifts rate limits.
    mailto: Optional[str] = field(default_factory=lambda: os.environ.get("OPENALEX_MAILTO"))
    api_key: Optional[str] = field(default_factory=lambda: os.environ.get("OPENALEX_API_KEY"))
    # S3 snapshot bucket (public, --no-sign-request).
    snapshot_s3_uri: str = field(
        default_factory=lambda: os.environ.get("OPENALEX_SNAPSHOT_S3", "s3://openalex")
    )


def default_scope() -> LakeScope:
    """The agreed starting point: 270 journals × 2010-2025, no citations."""
    return LakeScope(year_from=DEFAULT_YEAR_FROM, year_to=DEFAULT_YEAR_TO)


def load_scored_issn_l(db) -> list[str]:
    """Fetch the ISSN-L list we already have journal metrics for.

    Kept as a thin helper (I/O) so LakeScope itself stays pure. `db` is a
    SQLAlchemy Session.
    """
    from backend import models

    rows = (
        db.query(models.JournalMetric.issn_l)
        .filter(models.JournalMetric.issn_l.isnot(None))
        .distinct()
        .all()
    )
    return [r[0] for r in rows if r[0]]
