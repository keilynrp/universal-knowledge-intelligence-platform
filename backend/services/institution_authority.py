"""Institution Authority Records — Task 3.2.

Manages institution authority records created from reconciliation results.
Prevents duplicates by checking existing records by ROR/OpenAlex ID.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InstitutionAuthority:
    """Canonical institution authority record."""
    id: int | None = None
    canonical_name: str = ""
    ror_id: str | None = None
    openalex_id: str | None = None
    aliases: list[str] = field(default_factory=list)
    country_code: str | None = None
    institution_type: str | None = None
    confidence: float = 0.0
    status: str = "pending"  # pending | confirmed | rejected
    source_identifiers: list[str] = field(default_factory=list)
    created_at: str = ""
    confirmed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InstitutionAuthorityStore:
    """In-memory store for institution authority records.

    In production this would be backed by the AuthorityRecord DB table.
    This service layer handles deduplication and accept/reject logic.
    """

    def __init__(self) -> None:
        self._records: dict[int, InstitutionAuthority] = {}
        self._next_id = 1
        self._ror_index: dict[str, int] = {}
        self._openalex_index: dict[str, int] = {}

    def find_by_ror(self, ror_id: str) -> InstitutionAuthority | None:
        """Find existing authority by ROR ID."""
        rec_id = self._ror_index.get(ror_id.strip().lower())
        return self._records.get(rec_id) if rec_id else None

    def find_by_openalex(self, openalex_id: str) -> InstitutionAuthority | None:
        """Find existing authority by OpenAlex ID."""
        rec_id = self._openalex_index.get(openalex_id.strip().lower())
        return self._records.get(rec_id) if rec_id else None

    def create_or_reuse(
        self,
        canonical_name: str,
        ror_id: str | None = None,
        openalex_id: str | None = None,
        aliases: list[str] | None = None,
        country_code: str | None = None,
        institution_type: str | None = None,
        confidence: float = 0.0,
        source_identifiers: list[str] | None = None,
    ) -> tuple[InstitutionAuthority, bool]:
        """Create a new authority record or reuse existing one.

        Returns (record, is_new). If a record with the same ROR or OpenAlex
        already exists, returns the existing record with is_new=False.
        """
        # Check for existing by ROR
        if ror_id:
            existing = self.find_by_ror(ror_id)
            if existing:
                return existing, False

        # Check for existing by OpenAlex
        if openalex_id:
            existing = self.find_by_openalex(openalex_id)
            if existing:
                return existing, False

        record = InstitutionAuthority(
            id=self._next_id,
            canonical_name=canonical_name,
            ror_id=ror_id,
            openalex_id=openalex_id,
            aliases=aliases or [],
            country_code=country_code,
            institution_type=institution_type,
            confidence=confidence,
            status="pending",
            source_identifiers=source_identifiers or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._records[self._next_id] = record

        if ror_id:
            self._ror_index[ror_id.strip().lower()] = self._next_id
        if openalex_id:
            self._openalex_index[openalex_id.strip().lower()] = self._next_id

        self._next_id += 1
        return record, True

    def accept(self, record_id: int) -> InstitutionAuthority | None:
        """Accept/confirm an institution authority record."""
        record = self._records.get(record_id)
        if not record:
            return None
        record.status = "confirmed"
        record.confirmed_at = datetime.now(timezone.utc).isoformat()
        return record

    def reject(self, record_id: int) -> InstitutionAuthority | None:
        """Reject an institution authority record."""
        record = self._records.get(record_id)
        if not record:
            return None
        record.status = "rejected"
        return record

    def get(self, record_id: int) -> InstitutionAuthority | None:
        return self._records.get(record_id)

    def list_records(self, status: str | None = None) -> list[InstitutionAuthority]:
        records = list(self._records.values())
        if status:
            records = [r for r in records if r.status == status]
        return records
