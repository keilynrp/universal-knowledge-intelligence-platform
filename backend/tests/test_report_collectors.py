"""Section collectors — format-neutral data extraction
(unify-report-format-coverage, phase 3).

A collector pulls a section's data into a `SectionData` with no markup, so every
format renders the same payload. Pilot section: entity_stats.
"""
from backend import models, report_builder
from backend.reporting.section_data import SectionData, StatGrid, Table


def _seed(db) -> None:
    rows = [
        ("valid", "completed"),
        ("valid", "completed"),
        ("valid", "pending"),
        ("pending", "pending"),
        ("invalid", "failed"),
    ]
    for i, (status, enrich) in enumerate(rows):
        db.add(models.RawEntity(
            primary_label=f"E{i}",
            domain="default",
            validation_status=status,
            enrichment_status=enrich,
        ))
    db.commit()


def test_collect_entity_stats_returns_stat_grid_and_distribution(db_session):
    _seed(db_session)
    section = report_builder.collect_entity_stats(db_session, "default", None)

    assert isinstance(section, SectionData)
    assert section.key == "entity_stats"
    assert section.title == "Entity Statistics"

    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    labels = {item.label: item.value for item in grid.items}
    assert labels["Total Entities"] == "5"
    assert labels["Valid"] == "3"        # 3 rows with validation_status=valid
    assert labels["Pending"] == "1"      # 1 row with validation_status=pending
    assert labels["Enriched"] == "2"     # 2 rows with enrichment_status=completed

    table = next(b for b in section.blocks if isinstance(b, Table))
    assert table.columns == ("Validation Status", "Count", "Distribution")
    assert table.bar_column == 2
    # rows sorted by count desc; valid (3) leads
    assert table.rows[0][0] == "valid"
    assert table.rows[0][1] == "3"


def test_collect_entity_stats_empty_workspace(db_session):
    section = report_builder.collect_entity_stats(db_session, "default", None)
    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    labels = {item.label: item.value for item in grid.items}
    assert labels["Total Entities"] == "0"


def test_migrated_entity_stats_html_preserves_structure(db_session):
    """The HTML section builder now delegates to the collector + renderer; the
    output must still carry the same structure the hand-written builder did
    (task 3 gate: existing tests + a structural assertion)."""
    _seed(db_session)
    html = report_builder._section_entity_stats(db_session, "default", None)

    assert "<h2>Entity Statistics</h2>" in html
    assert html.count('class="stat-card"') == 4          # the four KPI cards
    for label in ("Total Entities", "Valid", "Pending", "Enriched"):
        assert label in html
    # the validation-distribution table with its bar column
    assert "Validation Status" in html and "Distribution" in html
    assert 'class="bar-wrap"' in html and 'class="bar"' in html
