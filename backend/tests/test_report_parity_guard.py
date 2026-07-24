"""Parity guard — the definition of done for unify-report-format-coverage.

Every public section must render in every export format, or be explicitly
declared unsupported. This test is the ratchet: the migration flips one
(section, format) at a time until nothing is xfailed.

Design — the ratchet enforces itself, in both directions:

  * The xfail marks are derived from `SECTION_FORMAT_SUPPORT` at collection
    time, and the test body performs the *real* render and checks the section's
    marker actually appears.
  * A combo the support map claims → no xfail → the body must genuinely render
    it, or the test fails (the map cannot lie about coverage it does not have).
  * A combo the map omits → strict xfail → the body's render fails, as expected.
  * When migration makes a section render but forgets to update the map, the
    strict xfail xpasses and fails, forcing the map update. When the map is
    updated but the renderer does not actually render, the body fails, forcing
    the implementation. The map and reality cannot drift apart.

Task 7.1 is done when this test reports zero xfails.
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
        "topic_clusters": "Concepts",
        "harmonization_log": "Harmonization",
    },
    "pptx": {
        "entity_stats": "Entity Statistics",
        "enrichment_coverage": "Enrichment Coverage",
        "top_secondary_labels": "Top Secondary Labels",
        "topic_clusters": "Top Concepts",
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


def _param(export_format: str, section: str):
    marks = ()
    if not format_support.supports(export_format, section):
        marks = pytest.mark.xfail(
            strict=True,
            reason=f"{export_format} does not render {section} yet — migration flips this",
        )
    return pytest.param(export_format, section, marks=marks, id=f"{export_format}:{section}")


_COMBOS = [
    _param(fmt, section)
    for fmt in format_support.EXPORT_FORMATS
    for section in format_support.PUBLIC_SECTIONS
]


@pytest.mark.parametrize("export_format,section", _COMBOS)
def test_section_renders_in_every_format(export_format, section, db_session):
    _seed(db_session)
    marker = _MARKERS[export_format].get(section)
    blob = _render(export_format, section, db_session)
    assert marker is not None, f"{export_format} declares no marker for {section}"
    assert marker in blob, f"{export_format} did not render {section} (marker {marker!r})"


def test_support_map_covers_every_public_section_key():
    """Every format lists only real public sections; no typos, no aliases."""
    for fmt, sections in format_support.SECTION_FORMAT_SUPPORT.items():
        unknown = sections - set(format_support.PUBLIC_SECTIONS)
        assert not unknown, f"{fmt} claims unknown sections: {unknown}"
