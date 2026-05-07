from __future__ import annotations

from backend.importers.scientific.base import ScientificImportAdapter, ScientificImportResult
from backend.importers.scientific.legacy_records import canonical_publication_from_legacy_record
from backend.parsers.wos_plaintext_parser import looks_like_wos_plaintext, parse_wos_plaintext


class WosPlaintextImportAdapter(ScientificImportAdapter):
    provider = "wos"
    format = "wos_plaintext"

    def can_parse(self, filename: str, content: str) -> bool:
        return filename.lower().endswith(".txt") and looks_like_wos_plaintext(content)

    def parse(self, filename: str, content: str) -> ScientificImportResult:
        raw_records = parse_wos_plaintext(content)
        records = [
            canonical_publication_from_legacy_record(
                record,
                provider=record.get("_source_name") or self.provider,
                provider_record_id=record.get("raw_ut") or record.get("doi"),
            )
            for record in raw_records
        ]
        return ScientificImportResult(format=self.format, provider=self.provider, records=records)
