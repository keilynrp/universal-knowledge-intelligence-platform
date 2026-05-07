from __future__ import annotations

from backend.importers.scientific.base import ScientificImportAdapter, ScientificImportResult
from backend.importers.scientific.legacy_records import canonical_publication_from_legacy_record
from backend.parsers.bibtex_parser import parse_bibtex


class BibTeXImportAdapter(ScientificImportAdapter):
    provider = "bibtex"
    format = "bibtex"

    def can_parse(self, filename: str, content: str) -> bool:
        return filename.lower().endswith(".bib")

    def parse(self, filename: str, content: str) -> ScientificImportResult:
        raw_records = parse_bibtex(content)
        records = [
            canonical_publication_from_legacy_record(
                record,
                provider=self.provider,
                provider_record_id=record.get("_cite_key") or record.get("doi"),
            )
            for record in raw_records
        ]
        return ScientificImportResult(format=self.format, provider=self.provider, records=records)
