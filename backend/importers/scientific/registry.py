from __future__ import annotations

from backend.importers.scientific.base import ScientificImportAdapter, ScientificImportResult
from backend.importers.scientific.bibtex_adapter import BibTeXImportAdapter
from backend.importers.scientific.openalex_adapter import OpenAlexJSONImportAdapter
from backend.importers.scientific.ris_adapter import RISImportAdapter
from backend.importers.scientific.scopus_adapter import ScopusJSONImportAdapter
from backend.importers.scientific.wos_adapter import WosPlaintextImportAdapter


_ADAPTERS: tuple[ScientificImportAdapter, ...] = (
    BibTeXImportAdapter(),
    RISImportAdapter(),
    WosPlaintextImportAdapter(),
    OpenAlexJSONImportAdapter(),
    ScopusJSONImportAdapter(),
)


def get_scientific_import_adapter(filename: str, content: str) -> ScientificImportAdapter | None:
    for adapter in _ADAPTERS:
        if adapter.can_parse(filename, content):
            return adapter
    return None


def detect_scientific_import(filename: str, content: str) -> ScientificImportResult | None:
    adapter = get_scientific_import_adapter(filename, content)
    if adapter is None:
        return None
    return adapter.parse(filename, content)
