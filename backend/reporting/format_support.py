"""Per-format section coverage — the single source of truth for parity.

The section picker offers one vocabulary and four export formats, but the
formats do not render the same set. This module declares, per format, which
sections it actually renders today. It is:

  * read by the parity guard test as the ratchet target — every section must
    eventually be supported by every format, or explicitly declared
    unsupported;
  * (from phase 4) surfaced through `GET /reports/sections` so a caller can see
    availability before exporting instead of discovering a silent drop after.

The strangler migration edits `SECTION_FORMAT_SUPPORT` one section at a time as
each gains a real renderer. HTML and PDF share the one HTML pipeline, so their
coverage is identical by construction.
"""
from __future__ import annotations

from backend import report_builder

# Ordered, alias-free public section ids — the vocabulary GET /reports/sections
# returns. Derived from the builder registry so this list cannot drift from it.
PUBLIC_SECTIONS: tuple[str, ...] = tuple(
    section
    for section in report_builder.SECTION_BUILDERS
    if section not in report_builder.SECTION_ALIASES
)

EXPORT_FORMATS: tuple[str, ...] = ("html", "pdf", "excel", "pptx")

# Sections each format renders TODAY. HTML/PDF render the full set through
# report_builder.build(); Excel and PPTX each implemented a subset. Migration
# grows the Excel and PPTX sets until every format equals PUBLIC_SECTIONS.
SECTION_FORMAT_SUPPORT: dict[str, frozenset[str]] = {
    "html": frozenset(PUBLIC_SECTIONS),
    "pdf": frozenset(PUBLIC_SECTIONS),
    "excel": frozenset({"entity_stats", "topic_clusters", "harmonization_log"}),
    "pptx": frozenset({
        "entity_stats",
        "enrichment_coverage",
        "top_secondary_labels",
        "topic_clusters",
    }),
}


def supports(export_format: str, section: str) -> bool:
    """Whether `export_format` renders `section` today."""
    return section in SECTION_FORMAT_SUPPORT.get(export_format, frozenset())


def unsupported_sections(export_format: str, sections: list[str]) -> list[str]:
    """Requested sections that `export_format` cannot render, order preserved."""
    supported = SECTION_FORMAT_SUPPORT.get(export_format, frozenset())
    canonical = report_builder.canonical_sections(sections)
    return [s for s in canonical if s not in supported]
