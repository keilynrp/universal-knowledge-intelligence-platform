"""The render-boundary seam that lets report text be localised at all.

#268. Section titles were localised in #209 by keying off the section id — the
one slot where an id exists. Everything else (stat labels, table headers, method
notes, narrative prose) is built inside a collector, so there is no id to derive
a key from.

`localize_section` resolves catalog keys anywhere in a payload. A collector
migrates one field at a time, and until it does, the payload renders exactly as
before: a string that is not a key passes through untouched.
"""

from __future__ import annotations

import pytest

from backend.i18n import catalog as catalog_module
from backend.reporting.localize import localize_section, looks_like_key
from backend.reporting.section_data import (
    Materiality,
    Meter,
    Narrative,
    SectionData,
    StatGrid,
    StatItem,
    Table,
)

pytestmark = pytest.mark.reporting


def _section(**overrides) -> SectionData:
    base = dict(
        key="entity_stats",
        title="Entity Statistics",
        takeaway="30 of 40 entities pass validation.",
        method="Counts are scoped to this domain.",
        blocks=(),
        materiality=Materiality.ROUTINE,
    )
    base.update(overrides)
    return SectionData(**base)


class TestKeyDetection:
    @pytest.mark.parametrize(
        "value", ["report.section.entity_stats", "email.password_reset.subject"]
    )
    def test_a_surface_prefixed_string_is_a_key(self, value):
        assert looks_like_key(value)

    @pytest.mark.parametrize(
        "value",
        [
            "Entity Statistics",
            "30 of 40 entities pass validation.",
            "Reporting on the report.",  # contains the word, does not start with it
            None,
            42,
        ],
    )
    def test_ordinary_copy_is_not_a_key(self, value):
        assert not looks_like_key(value)


class TestPassthrough:
    """Until a collector migrates, nothing about its output may change."""

    def test_a_payload_with_no_keys_is_unchanged(self):
        section = _section(
            blocks=(
                StatGrid(items=(StatItem(label="Total Entities", value="40", sub="all"),)),
                Table(columns=("Concept", "Frequency"), rows=(("knowledge graph", "20"),)),
                Narrative(heading="Executive reading", paragraphs=("UKIP scanned…",)),
                Meter(label="Coverage", pct=65.0),
            )
        )

        assert localize_section(section, "es") == section

    def test_it_is_idempotent(self):
        section = _section()

        once = localize_section(section, "es")
        assert localize_section(once, "es") == once


class TestResolution:
    @pytest.fixture(autouse=True)
    def _catalog(self, monkeypatch):
        monkeypatch.setattr(
            catalog_module,
            "_load_catalog",
            lambda language: {
                "report.section.entity_stats": {
                    "en": "Entity Statistics",
                    "es": "Estadísticas de Entidades",
                }[language],
                "report.stat.total": {"en": "Total Entities", "es": "Entidades Totales"}[
                    language
                ],
                "report.col.concept": {"en": "Concept", "es": "Concepto"}[language],
                "report.status.passed": {"en": "Passed", "es": "Cumple"}[language],
                "report.narrative.exec": {"en": "Executive reading", "es": "Lectura ejecutiva"}[
                    language
                ],
                "report.stat.sub.awaiting": {"en": "awaiting validation", "es": "esperando validación"}[
                    language
                ],
                "report.narrative.scan": {"en": "UKIP scanned the portfolio.", "es": "UKIP revisó el portafolio."}[
                    language
                ],
            },
        )

    def test_the_title_resolves(self):
        out = localize_section(_section(title="report.section.entity_stats"), "es")

        assert out.title == "Estadísticas de Entidades"

    def test_stat_labels_resolve_but_values_do_not(self):
        section = _section(
            blocks=(StatGrid(items=(StatItem(label="report.stat.total", value="40"),)),)
        )

        out = localize_section(section, "es")

        assert out.blocks[0].items[0].label == "Entidades Totales"
        assert out.blocks[0].items[0].value == "40", (
            "a figure is data, not copy — translating it would change what the "
            "report states"
        )

    def test_table_cells_pass_through_unless_they_are_keys(self):
        """Cells were exempt from resolution on the grounds that they hold
        provider data. That is true of nearly every table and false of one: the
        benchmark rule table has a status column the system writes itself, and a
        key placed there rendered verbatim.

        So the rule is now the same one every other slot already uses — a string
        starting with a surface prefix is a key, anything else is data. Provider
        text is still untouched, and now it is untouched for a reason that does
        not depend on which field it landed in.
        """
        section = _section(
            blocks=(
                Table(
                    columns=("report.col.concept", "Frequency"),
                    rows=(("knowledge graph", "report.status.passed"),),
                ),
            )
        )

        out = localize_section(section, "es")

        assert out.blocks[0].columns == ("Concepto", "Frequency")
        cell_data, cell_key = out.blocks[0].rows[0]
        assert cell_data == "knowledge graph", (
            "a concept name is provider data and is not ours to translate"
        )
        assert cell_key == "Cumple", (
            "a system-authored cell holding a key must resolve, not render raw"
        )

    def test_stat_sub_labels_resolve(self):
        """`sub` is copy — "awaiting validation" — not a figure.

        Added after a mutation check: removing its localization left every test
        green, because no fixture had ever put a key there.
        """
        section = _section(
            blocks=(
                StatGrid(
                    items=(
                        StatItem(
                            label="report.stat.total",
                            value="40",
                            sub="report.stat.sub.awaiting",
                        ),
                    )
                ),
            )
        )

        out = localize_section(section, "es")

        assert out.blocks[0].items[0].sub == "esperando validación"

    def test_narrative_paragraphs_resolve(self):
        """Same gap as `sub`: no fixture had a key in a paragraph."""
        section = _section(
            blocks=(
                Narrative(
                    heading="report.narrative.exec",
                    paragraphs=("report.narrative.scan", "a literal stays put"),
                ),
            )
        )

        out = localize_section(section, "es")

        assert out.blocks[0].paragraphs == (
            "UKIP revisó el portafolio.",
            "a literal stays put",
        )

    def test_narrative_headings_resolve(self):
        section = _section(
            blocks=(Narrative(heading="report.narrative.exec", paragraphs=("plain",)),)
        )

        out = localize_section(section, "es")

        assert out.blocks[0].heading == "Lectura ejecutiva"
        assert out.blocks[0].paragraphs == ("plain",)

    def test_a_mixed_payload_resolves_only_the_keys(self):
        section = _section(
            title="report.section.entity_stats",
            takeaway="30 of 40 entities pass validation.",
        )

        out = localize_section(section, "es")

        assert out.title == "Estadísticas de Entidades"
        assert out.takeaway == "30 of 40 entities pass validation."
