from __future__ import annotations

from backend.importers.scientific.base import ScientificImportAdapter, ScientificImportResult
from backend.importers.scientific.legacy_records import canonical_publication_from_legacy_record
from backend.parsers.ris_parser import parse_ris


class RISImportAdapter(ScientificImportAdapter):
    provider = "ris"
    format = "ris"

    def can_parse(self, filename: str, content: str) -> bool:
        return filename.lower().endswith(".ris")

    def parse(self, filename: str, content: str) -> ScientificImportResult:
        raw_records = parse_ris(content)
        records = [
            canonical_publication_from_legacy_record(
                record,
                provider=self.provider,
                provider_record_id=record.get("doi") or record.get("url"),
            )
            for record in raw_records
        ]
        return ScientificImportResult(format=self.format, provider=self.provider, records=records)
