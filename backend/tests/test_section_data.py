"""Format-neutral section payload types (unify-report-format-coverage, phase 1).

A section is authored once as a `SectionData` of format-neutral blocks; each
renderer turns those blocks into HTML / Excel / PPTX. These tests pin the
construction and validation contract of the payload before any renderer or
migration depends on it.
"""
import pytest

from backend.reporting.section_data import (
    Meter,
    Narrative,
    SectionData,
    StatGrid,
    StatItem,
    Table,
)


def test_statgrid_holds_labelled_items():
    grid = StatGrid(items=(
        StatItem(label="Total", value="1,240"),
        StatItem(label="Enriched", value="60%", sub="744 of 1,240"),
    ))
    assert grid.items[1].sub == "744 of 1,240"


def test_table_rows_must_match_column_count():
    Table(columns=("Journal", "NIF"), rows=(("Nature", "9.1"), ("Cell", "8.3")))
    with pytest.raises(ValueError):
        Table(columns=("Journal", "NIF"), rows=(("Nature",),))


def test_table_bar_column_must_be_in_range():
    Table(columns=("A", "B"), rows=(("1", "2"),), bar_column=1)
    with pytest.raises(ValueError):
        Table(columns=("A", "B"), rows=(("1", "2"),), bar_column=2)


def test_meter_pct_is_bounded():
    Meter(label="Coverage", pct=0)
    Meter(label="Coverage", pct=100)
    with pytest.raises(ValueError):
        Meter(label="Coverage", pct=101)
    with pytest.raises(ValueError):
        Meter(label="Coverage", pct=-1)


def test_narrative_requires_a_heading():
    Narrative(heading="Executive reading", paragraphs=("A.", "B."))
    with pytest.raises(ValueError):
        Narrative(heading="", paragraphs=("A.",))


def test_section_data_carries_key_title_and_blocks():
    section = SectionData(
        key="entity_stats",
        title="Entity Statistics",
        blocks=(
            StatGrid(items=(StatItem(label="Total", value="10"),)),
            Narrative(heading="Reading", paragraphs=("All good.",)),
        ),
    )
    assert section.key == "entity_stats"
    assert len(section.blocks) == 2


def test_section_data_rejects_empty_key():
    with pytest.raises(ValueError):
        SectionData(key="", title="X", blocks=())


def test_blocks_are_immutable():
    item = StatItem(label="Total", value="10")
    with pytest.raises(Exception):
        item.value = "20"  # frozen
