"""Section collectors — format-neutral data extraction
(unify-report-format-coverage, phase 3).

A collector pulls a section's data into a `SectionData` with no markup, so every
format renders the same payload. Pilot section: entity_stats.
"""
from backend import models, report_builder
from backend.reporting.section_data import (
    Meter,
    Narrative,
    SectionData,
    StatGrid,
    Table,
)


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


# ── impact_projection (task 3.7) ────────────────────────────────────────────

def _seed_snapshot(db) -> None:
    """Enriched entities with concepts + citations so the analytics snapshot
    produces real recommendations, patterns, a benchmark and an impact
    projection (mirrors the parity-guard seed, sized to guarantee non-empty
    analytics output)."""
    for i in range(6):
        db.add(models.RawEntity(
            primary_label=f"Signal {i}",
            domain="default",
            enrichment_status="completed",
            enrichment_concepts="knowledge graph; semantic intelligence; ontology",
            enrichment_citation_count=120 + i * 7,
            enrichment_source="openalex",
            secondary_label="Clinical Trial" if i % 2 else "Review",
            quality_score=0.8,
        ))
    db.commit()


def test_collect_impact_projection_returns_kpis_interpretation_and_drivers(db_session):
    _seed_snapshot(db_session)
    section = report_builder.collect_impact_projection(db_session, "default", None)

    assert isinstance(section, SectionData)
    assert section.key == "impact_projection"
    assert section.title == "Impact Projection"

    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    assert {i.label for i in grid.items} == {"Expected Impact", "Probable Range", "Confidence"}

    narrative = next(b for b in section.blocks if isinstance(b, Narrative))
    assert narrative.heading == "Executive interpretation"

    meters = [b for b in section.blocks if isinstance(b, Meter)]
    assert [m.label for m in meters] == ["Coverage", "Quality", "Citation signal", "Concentration"]
    for m in meters:
        assert 0 <= m.pct <= 100


def test_migrated_impact_projection_html_preserves_structure(db_session):
    """HTML builder delegates to the collector + renderer. The three KPI cards,
    the executive-interpretation callout, and the four driver bars survive; the
    decorative 'Projection drivers' wrapper card is dropped (the four Meters
    render as label + bar directly)."""
    _seed_snapshot(db_session)
    html = report_builder._section_impact_projection(db_session, "default", None)

    assert "<h2>Impact Projection</h2>" in html
    assert html.count('class="stat-card"') == 3        # the three KPI cards only
    assert 'class="callout"' in html and "Executive interpretation" in html
    for driver in ("Coverage", "Quality", "Citation signal", "Concentration"):
        assert driver in html
    assert 'class="bar"' in html


# ── decision_recommendations (task 3.9) ─────────────────────────────────────

def test_collect_decision_recommendations_returns_priority_table(db_session):
    _seed_snapshot(db_session)
    section = report_builder.collect_decision_recommendations(db_session, "default", None)

    assert isinstance(section, SectionData)
    assert section.key == "decision_recommendations"
    assert section.title == "Suggested Next Actions"

    table = next(b for b in section.blocks if isinstance(b, Table))
    assert table.columns == ("Priority", "Category", "Recommendation", "Detail", "Evidence")
    assert len(table.rows) >= 1               # the seed produces real recommendations
    # priority is title-cased plain text, no badge markup
    assert all("<span" not in cell for row in table.rows for cell in row)


def test_migrated_decision_recommendations_html_preserves_structure(db_session):
    _seed_snapshot(db_session)
    html = report_builder._section_decision_recommendations(db_session, "default", None)
    assert "<h2>Suggested Next Actions</h2>" in html
    for col in ("Priority", "Category", "Recommendation", "Detail", "Evidence"):
        assert col in html


# ── hidden_patterns (task 3.8) ──────────────────────────────────────────────

def test_collect_hidden_patterns_returns_reading_and_impact_table(db_session):
    _seed_snapshot(db_session)
    section = report_builder.collect_hidden_patterns(db_session, "default", None)

    assert section.key == "hidden_patterns"
    reading = next(b for b in section.blocks if isinstance(b, Narrative))
    assert reading.heading == "Executive reading"

    table = next(b for b in section.blocks if isinstance(b, Table))
    assert table.columns == ("Pattern", "Confidence", "Signal", "Evidence", "Action", "Impact")
    assert table.bar_column == 5
    assert len(table.rows) >= 1
    # the impact cell is a plain number the bar renderer reads
    assert table.rows[0][5].isdigit()


def test_migrated_hidden_patterns_html_preserves_structure(db_session):
    _seed_snapshot(db_session)
    html = report_builder._section_hidden_patterns(db_session, "default", None)
    assert "<h2>Hidden Patterns</h2>" in html
    assert 'class="callout"' in html and "Executive reading" in html
    assert 'class="bar-wrap"' in html and 'class="bar"' in html


# ── institutional_benchmark (task 3.6) ──────────────────────────────────────

def test_collect_institutional_benchmark_returns_kpis_reading_and_tables(db_session):
    _seed_snapshot(db_session)
    section = report_builder.collect_institutional_benchmark(db_session, "default", None)

    assert section.key == "institutional_benchmark"
    grid = next(b for b in section.blocks if isinstance(b, StatGrid))
    assert {i.label for i in grid.items} == {"Benchmark Profile", "Readiness", "Status"}

    assert any(isinstance(b, Narrative) for b in section.blocks)

    tables = [b for b in section.blocks if isinstance(b, Table)]
    assert len(tables) == 2
    assert tables[0].columns == ("Gap", "Priority", "Evidence")
    assert tables[1].columns == ("Rule", "Observed", "Threshold", "Status", "Interpretation")


def test_migrated_institutional_benchmark_html_preserves_structure(db_session):
    _seed_snapshot(db_session)
    html = report_builder._section_institutional_benchmark(db_session, "default", None)
    assert "<h2>Institutional Benchmark</h2>" in html
    assert html.count('class="stat-card"') == 3
    assert 'class="callout"' in html and "Executive reading" in html
    for col in ("Gap", "Priority", "Evidence", "Rule", "Observed", "Threshold", "Interpretation"):
        assert col in html


# ── harmonization_log (task 3.5, HTML + PPTX; Excel keeps its bespoke sheet) ─

def _seed_harmonization(db) -> None:
    db.add(models.HarmonizationLog(
        step_id="normalize_labels", step_name="Normalize labels",
        records_updated=3, fields_modified="primary_label",
    ))
    db.add(models.HarmonizationLog(
        step_id="dedupe", step_name="Deduplicate",
        records_updated=5, reverted=True,
    ))
    db.commit()


def test_collect_harmonization_log_returns_status_table(db_session):
    _seed_harmonization(db_session)
    section = report_builder.collect_harmonization_log(db_session, "default", None)

    assert section.key == "harmonization_log"
    assert section.title == "Harmonization Log"
    table = next(b for b in section.blocks if isinstance(b, Table))
    assert table.columns == ("Step", "Records Updated", "Status", "Executed")
    statuses = {row[2] for row in table.rows}
    assert statuses <= {"Applied", "Reverted"}
    assert "Reverted" in statuses          # the deduped row was reverted


def test_collect_harmonization_log_empty(db_session):
    section = report_builder.collect_harmonization_log(db_session, "default", None)
    table = next(b for b in section.blocks if isinstance(b, Table))
    assert table.rows == ()


def test_migrated_harmonization_log_html_preserves_structure(db_session):
    _seed_harmonization(db_session)
    html = report_builder._section_harmonization_log(db_session, "default", None)
    assert "<h2>Harmonization Log</h2>" in html
    for col in ("Step", "Records Updated", "Status", "Executed"):
        assert col in html
    assert "Normalize labels" in html


# ── stakeholder_reading (task 3.11 — always-on section, not in the registry) ─

def test_collect_stakeholder_reading_returns_narrative(db_session):
    _seed_snapshot(db_session)
    section = report_builder.collect_stakeholder_reading(db_session, "default", None)

    assert isinstance(section, SectionData)
    assert section.key == "stakeholder_reading"
    assert section.title == "Stakeholder Reading"

    reading = next(b for b in section.blocks if isinstance(b, Narrative))
    assert reading.heading                      # the stakeholder lens label
    joined = " ".join(reading.paragraphs)
    assert "benchmark readiness" in joined
    assert "Recommended emphasis:" in joined
    assert "Narrative goal:" in joined


def test_migrated_stakeholder_reading_html_preserves_structure(db_session):
    """HTML builder delegates to the collector + renderer. The section still
    renders as a callout under the Stakeholder Reading heading; the attention-
    point bullets flatten to paragraphs (the shared Narrative primitive)."""
    _seed_snapshot(db_session)
    html = report_builder._section_stakeholder_reading(db_session, "default", None)

    assert "<h2>Stakeholder Reading</h2>" in html
    assert 'class="callout"' in html
    assert "benchmark readiness" in html
