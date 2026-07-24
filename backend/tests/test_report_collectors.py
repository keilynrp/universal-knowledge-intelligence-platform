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


# ── enrichment_coverage (task 3.2) ──────────────────────────────────────────

def _seed_enriched(db) -> None:
    """Entities with citation counts and sources so the top-enriched table has
    real content; one non-completed row that must be excluded from coverage."""
    rows = [
        ("Alpha", "completed", 300, "openalex"),
        ("Beta", "completed", 150, "crossref"),
        ("Gamma", "pending", 0, None),
    ]
    for label, status, cites, source in rows:
        db.add(models.RawEntity(
            primary_label=label,
            domain="default",
            enrichment_status=status,
            enrichment_citation_count=cites,
            enrichment_source=source,
        ))
    db.commit()


def test_collect_enrichment_coverage_returns_coverage_kpis_and_top_table(db_session):
    _seed_enriched(db_session)
    section = report_builder.collect_enrichment_coverage(db_session, "default", None)

    assert isinstance(section, SectionData)
    assert section.key == "enrichment_coverage"
    assert section.title == "Enrichment Coverage"

    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    labels = {item.label: item.value for item in grid.items}
    assert labels["Coverage"] == "67%"       # 2 of 3 completed → round(66.6) = 67
    assert labels["Avg Citations"] == "225"  # (300 + 150) / 2 over completed only

    table = next(b for b in section.blocks if isinstance(b, Table))
    assert table.columns == ("Entity", "Citations", "Source")
    # only completed entities, sorted by citation count desc
    assert table.rows[0] == ("Alpha", "300", "openalex")
    assert all(r[0] != "Gamma" for r in table.rows)  # the pending row is excluded


def test_collect_enrichment_coverage_empty_workspace(db_session):
    section = report_builder.collect_enrichment_coverage(db_session, "default", None)
    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    labels = {item.label: item.value for item in grid.items}
    assert labels["Coverage"] == "0%"
    table = next(b for b in section.blocks if isinstance(b, Table))
    assert table.rows == ()


def test_migrated_enrichment_coverage_html_preserves_structure(db_session):
    """HTML builder now delegates to the collector + renderer; structure holds.
    The decorative source badge is intentionally dropped (the shared Table
    primitive renders plain cells)."""
    _seed_enriched(db_session)
    html = report_builder._section_enrichment_coverage(db_session, "default", None)

    assert "<h2>Enrichment Coverage</h2>" in html
    assert html.count('class="stat-card"') == 2      # Coverage + Avg Citations
    for label in ("Coverage", "Avg Citations"):
        assert label in html
    for col in ("Entity", "Citations", "Source"):
        assert col in html
    assert "Alpha" in html


# ── top_secondary_labels (task 3.3) ─────────────────────────────────────────

def _seed_labels(db) -> None:
    """Entities grouped by secondary_label so the share table has a clear order."""
    counts = [("Clinical Trial", 5), ("Review", 3), ("Dataset", 1)]
    for label, n in counts:
        for i in range(n):
            db.add(models.RawEntity(
                primary_label=f"{label}-{i}",
                domain="default",
                secondary_label=label,
            ))
    db.commit()


def test_collect_top_secondary_labels_returns_share_table(db_session):
    _seed_labels(db_session)
    section = report_builder.collect_top_secondary_labels(db_session, "default", None)

    assert isinstance(section, SectionData)
    assert section.key == "top_secondary_labels"
    assert section.title == "Top Secondary Labels / Classifications"

    table = next(b for b in section.blocks if isinstance(b, Table))
    assert table.columns == ("Label", "Entities", "Share")
    assert table.bar_column == 2
    # sorted by count desc; the top label draws a full-width bar
    assert table.rows[0] == ("Clinical Trial", "5", "100%")
    review = next(r for r in table.rows if r[0] == "Review")
    assert review == ("Review", "3", "60%")   # round(3 / 5 * 100)


def test_collect_top_secondary_labels_empty(db_session):
    section = report_builder.collect_top_secondary_labels(db_session, "default", None)
    table = next(b for b in section.blocks if isinstance(b, Table))
    assert table.rows == ()


def test_migrated_top_secondary_labels_html_preserves_structure(db_session):
    """HTML builder delegates to the collector + renderer; the share-bar table
    structure holds. The shared Table also prints the share value next to the
    bar (the hand-written builder drew the bar alone); the bar width is
    unchanged."""
    _seed_labels(db_session)
    html = report_builder._section_top_brands(db_session, "default", None)

    assert "<h2>Top Secondary Labels / Classifications</h2>" in html
    for col in ("Label", "Entities", "Share"):
        assert col in html
    assert 'class="bar-wrap"' in html and 'class="bar"' in html
    assert "Clinical Trial" in html
