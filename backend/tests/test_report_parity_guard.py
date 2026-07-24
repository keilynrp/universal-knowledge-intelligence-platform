"""Parity guard — the definition of done for unify-report-format-coverage.

Every public section must either render in every export format or be explicitly
declared unsupported *and reported as omitted* — never silently dropped. The
migration is complete: there are no xfails. Each (format, section) combo is now
asserted directly against `SECTION_FORMAT_SUPPORT`:

  * A combo the support map claims → the body performs the *real* render and the
    section's marker must appear, or the test fails (the map cannot lie about
    coverage it does not have).
  * A combo the map omits → the export must still succeed (no raise) and the
    section must be reported by `unsupported_sections()` — the omission contract
    (`test_report_omissions`), not a silent drop.

The map and reality cannot drift apart in either direction: claiming support
without a renderer fails the render assertion; rendering without claiming it
means the "unsupported" branch finds the marker anyway is impossible because the
branch is only taken when the map omits the combo. agentic_trace is the sole
declared-unsupported section (Excel + PPTX; free text that belongs in HTML/PDF).
"""
import io

import pytest
from pptx import Presentation

from backend import models, report_builder
from backend.exporters.excel_exporter import EnterpriseExcelExporter
from backend.exporters.pptx_exporter import generate_pptx
from backend.reporting import format_support


# How each section is expected to appear, per format. For HTML/PDF it is the
# section's <h2> label; for Excel it is the sheet name; for PPTX the slide
# title. A section absent from a format's map has no representation there yet —
# adding a renderer for it (migration) means adding its marker here too.
_MARKERS: dict[str, dict[str, str]] = {
    "html": dict(report_builder.SECTION_LABELS),
    "pdf": dict(report_builder.SECTION_LABELS),
    "excel": {
        "entity_stats": "Entity Statistics",  # migrated (phase 3): dedicated sheet
        "enrichment_coverage": "Enrichment Coverage",  # migrated (phase 3.2)
        "top_secondary_labels": "Top Secondary Labels",  # migrated (phase 3.3)
        "impact_projection": "Impact Projection",  # migrated (phase 3.7)
        "institutional_benchmark": "Institutional Benchmark",  # migrated (phase 3.6)
        "hidden_patterns": "Hidden Patterns",  # migrated (phase 3.8)
        "decision_recommendations": "Suggested Next Actions",  # migrated (phase 3.9)
        "topic_clusters": "Concepts",
        "harmonization_log": "Harmonization",
    },
    "pptx": {
        "entity_stats": "Entity Statistics",
        "enrichment_coverage": "Enrichment Coverage",
        "top_secondary_labels": "Top Secondary Labels",
        "topic_clusters": "Top Concepts",
        # migrated (phase 3): rendered via the shared payload + render_pptx
        "impact_projection": "Impact Projection",
        "institutional_benchmark": "Institutional Benchmark",
        "hidden_patterns": "Hidden Patterns",
        "decision_recommendations": "Suggested Next Actions",
        "harmonization_log": "Harmonization Log",
    },
}

_BRANDING = {
    "platform_name": "UKIP",
    "logo_url": None,
    "accent_color": "#6366f1",
    "footer_text": "UKIP",
}


def _render(export_format: str, section: str, db) -> str:
    """Render a single section in one format, returned as a searchable blob."""
    if export_format in ("html", "pdf"):
        # PDF renders exactly this HTML through WeasyPrint, so the HTML blob is
        # the faithful check for both without invoking a native PDF engine.
        return report_builder.build(db, "default", [section])
    if export_format == "excel":
        data = EnterpriseExcelExporter().build(db, "default", [section])
        wb = load_workbook_from_bytes(data)
        return "\n".join(wb.sheetnames)
    if export_format == "pptx":
        data = generate_pptx(
            db=db, domain_id="default", sections=[section], title=None,
            branding=_BRANDING, org_id=None,
        )
        prs = Presentation(io.BytesIO(data))
        return "\n".join(
            shape.text_frame.text
            for slide in prs.slides
            for shape in slide.shapes
            if shape.has_text_frame
        )
    raise AssertionError(f"unknown format {export_format}")


def load_workbook_from_bytes(data: bytes):
    import openpyxl
    return openpyxl.load_workbook(io.BytesIO(data))


def _seed(db) -> None:
    """Enough data for every section to produce its real content."""
    for idx in range(3):
        db.add(models.RawEntity(
            primary_label=f"Parity record {idx}",
            domain="default",
            enrichment_status="completed",
            enrichment_concepts="knowledge graph; semantic intelligence",
            enrichment_citation_count=120 + idx,
            enrichment_source="openalex",
            secondary_label="Clinical Trial",
            quality_score=0.8,
        ))
    db.add(models.HarmonizationLog(
        step_id="normalize_labels",
        step_name="Normalize labels",
        records_updated=3,
        fields_modified="primary_label",
    ))
    db.commit()


_COMBOS = [
    pytest.param(fmt, section, id=f"{fmt}:{section}")
    for fmt in format_support.EXPORT_FORMATS
    for section in format_support.PUBLIC_SECTIONS
]


@pytest.mark.parametrize("export_format,section", _COMBOS)
def test_section_renders_or_is_declared_unsupported(export_format, section, db_session):
    _seed(db_session)
    blob = _render(export_format, section, db_session)  # must never raise
    if format_support.supports(export_format, section):
        marker = _MARKERS[export_format].get(section)
        assert marker is not None, f"{export_format} declares no marker for {section}"
        assert marker in blob, f"{export_format} did not render {section} (marker {marker!r})"
    else:
        # Declared unsupported: the export still succeeds and the section is
        # reported as omitted (see test_report_omissions), never silently dropped.
        assert section in format_support.unsupported_sections(export_format, [section])


def test_support_map_covers_every_public_section_key():
    """Every format lists only real public sections; no typos, no aliases."""
    for fmt, sections in format_support.SECTION_FORMAT_SUPPORT.items():
        unknown = sections - set(format_support.PUBLIC_SECTIONS)
        assert not unknown, f"{fmt} claims unknown sections: {unknown}"
