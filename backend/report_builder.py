"""
Report Builder — generates self-contained HTML reports per domain.
No external template dependencies; uses f-strings with inline CSS.
"""
from __future__ import annotations

import json
from html import escape
from datetime import datetime, timezone
from typing import List, TypedDict

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend import models
from backend.analyzers.topic_modeling import TopicAnalyzer
from backend.schema_registry import registry
from backend.services.analytics_service import AnalyticsService
from backend.services.pattern_discovery import PatternDiscoveryService
from backend.tenant_access import scope_query_to_org

_STAKEHOLDER_PROFILES = {
    "leadership": {
        "label": "Leadership / Strategy",
        "focus": "decision readiness, strategic risk, and institutional positioning",
        "brief_hint": "Use this lens when the audience needs a concise readout of readiness, confidence, and next executive moves.",
        "attention_points": [
            "benchmark readiness and whether the current portfolio supports a defendable executive conversation",
            "main confidence risks that could weaken institutional positioning if shared too early",
            "one concrete next move that improves decision readiness quickly",
        ],
        "narrative_goal": "Keep the story concise, directional, and anchored in readiness, confidence, and near-term institutional action.",
    },
    "research_office": {
        "label": "Research Office",
        "focus": "portfolio quality, benchmark progress, and operational follow-through",
        "brief_hint": "Use this lens when the audience needs to understand what to improve in the dataset and which actions strengthen research reporting.",
        "attention_points": [
            "coverage and quality gaps that most directly hold back reporting confidence",
            "which benchmark rules already pass and which still need operational attention",
            "the most practical next actions for strengthening the portfolio baseline",
        ],
        "narrative_goal": "Frame the brief as an operational readout: what is already usable, what still needs work, and where the office should focus next.",
    },
    "library": {
        "label": "Library / Metadata",
        "focus": "metadata quality, authority control, and catalog reliability",
        "brief_hint": "Use this lens when the audience cares most about normalization quality, authority review, and trust in the underlying records.",
        "attention_points": [
            "record quality and authority issues that still affect trust in the dataset",
            "whether metadata consistency is strong enough for downstream analytics and reporting",
            "where curation effort will most improve catalog reliability",
        ],
        "narrative_goal": "Tell the story through trust in the record layer: what is stable, what remains ambiguous, and what curation work matters most.",
    },
    "innovation": {
        "label": "Innovation / Transfer",
        "focus": "high-impact entities, signals worth following, and portfolio narratives that support opportunity scanning",
        "brief_hint": "Use this lens when the audience wants a faster read on standout outputs, concentration areas, and next exploratory opportunities.",
        "attention_points": [
            "high-impact outputs that can anchor opportunity scanning or partner conversations",
            "concept clusters that point to concentration areas worth exploring further",
            "the next exploratory move that could turn signal into action",
        ],
        "narrative_goal": "Keep the brief opportunity-oriented: highlight standout outputs, concentration areas, and the most promising next exploratory path.",
    },
}


class ManualReportSection(TypedDict, total=False):
    title: str
    content: str


def _stakeholder_profile(profile_id: str | None) -> dict[str, str]:
    return _STAKEHOLDER_PROFILES.get(profile_id or "leadership", _STAKEHOLDER_PROFILES["leadership"])


def _section_manual_note(title: str, content: str) -> str:
    safe_title = escape(title.strip() or "Analyst Note")
    paragraphs = [
        f"<p>{escape(part.strip())}</p>"
        for part in content.split("\n\n")
        if part.strip()
    ]
    if not paragraphs:
        return ""
    return f"""<section>
    <h2>{safe_title}</h2>
    <div class="analyst-note">
        {"".join(paragraphs)}
    </div>
</section>"""


def _section_stakeholder_reading(
    db: Session,
    domain_id: str,
    org_id: int | None,
    benchmark_profile_id: str | None = None,
    benchmark_org: models.Organization | None = None,
    stakeholder_profile: str | None = None,
) -> str:
    snapshot = AnalyticsService.get_domain_snapshot(
        db,
        TopicAnalyzer(),
        domain_id,
        org_id=org_id,
        benchmark_org=benchmark_org,
        benchmark_profile_id=benchmark_profile_id,
        top_n_concepts=5,
        top_n_entities=3,
    )
    stakeholder = _stakeholder_profile(stakeholder_profile)
    benchmark = snapshot.get("institutional_benchmark") or {}
    quality = snapshot.get("quality") or {}
    kpis = snapshot.get("kpis") or {}
    actions = snapshot.get("recommended_actions") or []
    top_entity = (snapshot.get("top_entities") or [None])[0]
    impact_projection = snapshot.get("impact_projection") or {}

    benchmark_status = benchmark.get("status", "watch")
    readiness_pct = round(float(benchmark.get("readiness_pct") or 0))
    quality_avg = round(float(quality.get("average") or 0))
    coverage_pct = round(float(kpis.get("enrichment_pct") or 0))
    impact_score = round(float(impact_projection.get("score") or 0))
    impact_range = impact_projection.get("range") or {}

    if benchmark_status == "ready":
        stance = "The dataset is already in a comparatively strong position for a first stakeholder-facing conversation."
    elif benchmark_status == "watch":
        stance = "The dataset already supports directional interpretation, but it still carries enough uncertainty that the audience should treat this brief as an informed internal read rather than a final position."
    else:
        stance = "The dataset is best treated as an early baseline. It already surfaces useful directional patterns, but it is not yet robust enough for a high-confidence external narrative."

    action_text = actions[0]["title"] if actions else "Continue strengthening enrichment coverage and record quality before broad circulation."
    top_entity_text = ""
    if top_entity:
        top_entity_text = f"The highest-impact visible entity right now is {top_entity.get('entity_name') or top_entity.get('primary_label') or 'the current lead record'}, which can anchor a concrete stakeholder discussion."
    attention_points = "".join(
        f"<li>{point}</li>" for point in stakeholder.get("attention_points", [])
    )

    return f"""<section>
    <h2>Stakeholder Reading</h2>
    <div class="callout">
        <h3>{stakeholder["label"]}</h3>
        <p>This brief is being framed for {stakeholder["focus"]}. {stakeholder["brief_hint"]}</p>
        <p style="margin-top:8px">{stance}</p>
        <p style="margin-top:8px">Current benchmark readiness is <b>{readiness_pct}%</b>, average quality is <b>{quality_avg}%</b>, and enrichment coverage is <b>{coverage_pct}%</b>.</p>
        <p style="margin-top:8px">The current Monte Carlo impact projection is <b>{impact_score}/100</b>, with a probable range of <b>{impact_range.get("p10", 0)}–{impact_range.get("p90", 0)}</b>.</p>
        {'<p style="margin-top:8px">' + top_entity_text + '</p>' if top_entity_text else ''}
        <p style="margin-top:8px"><b>Recommended emphasis:</b> {action_text}</p>
        <p style="margin-top:10px"><b>How to read this brief for this audience:</b></p>
        <ul style="margin:8px 0 0 18px;color:#4b5563;line-height:1.7">{attention_points}</ul>
        <p style="margin-top:10px"><b>Narrative goal:</b> {stakeholder["narrative_goal"]}</p>
    </div>
</section>"""

# ── CSS (inline, print-friendly) ─────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       font-size: 14px; color: #111827; background: #fff; padding: 32px; }
.cover { text-align: center; padding: 60px 0 48px; border-bottom: 2px solid #e5e7eb; margin-bottom: 40px; }
.cover .logo { display: inline-flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.cover .logo-icon { width: 40px; height: 40px; background: #2563eb; border-radius: 10px;
                    display: flex; align-items: center; justify-content: center; }
.cover .logo-icon svg { width: 24px; height: 24px; color: #fff; stroke: #fff; }
.cover h1 { font-size: 28px; font-weight: 700; color: #111827; margin-bottom: 8px; }
.cover .meta { font-size: 13px; color: #6b7280; }
section { margin-bottom: 40px; }
section h2 { font-size: 17px; font-weight: 600; color: #1d4ed8; margin-bottom: 16px;
             padding-bottom: 8px; border-bottom: 1px solid #dbeafe; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px; margin-bottom: 16px; }
.stat-card { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; }
.stat-card .label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; }
.stat-card .value { font-size: 26px; font-weight: 700; color: #111827; margin-top: 4px; }
.stat-card .sub { font-size: 12px; color: #9ca3af; margin-top: 2px; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 8px 12px; background: #f3f4f6;
     font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; color: #6b7280;
     border-bottom: 1px solid #e5e7eb; }
td { padding: 9px 12px; border-bottom: 1px solid #f3f4f6; color: #374151; }
tr:last-child td { border-bottom: none; }
.bar-wrap { display: flex; align-items: center; gap: 8px; }
.bar { height: 8px; background: #2563eb; border-radius: 4px; }
.bar-bg { flex: 1; background: #e5e7eb; border-radius: 4px; height: 8px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 11px; font-weight: 600; }
.badge-blue   { background: #dbeafe; color: #1d4ed8; }
.badge-green  { background: #d1fae5; color: #065f46; }
.badge-amber  { background: #fef3c7; color: #92400e; }
.badge-gray   { background: #f3f4f6; color: #6b7280; }
.badge-red    { background: #fee2e2; color: #991b1b; }
.chip { display: inline-block; margin: 2px; padding: 3px 10px; border-radius: 9999px;
        font-size: 12px; background: #eff6ff; color: #1d4ed8; }
.callout { border-radius: 12px; padding: 16px; margin: 16px 0; border: 1px solid #e5e7eb; background: #f9fafb; }
.callout h3 { font-size: 13px; font-weight: 700; color: #111827; margin-bottom: 6px; }
.callout p { font-size: 13px; color: #4b5563; line-height: 1.6; }
.analyst-note { border-left: 4px solid #2563eb; background: #f8fafc; padding: 16px 18px; border-radius: 0 10px 10px 0; }
.analyst-note p { font-size: 14px; color: #1f2937; line-height: 1.7; margin-bottom: 10px; white-space: pre-wrap; }
.analyst-note p:last-child { margin-bottom: 0; }
footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid #e5e7eb;
         font-size: 12px; color: #9ca3af; text-align: center; }
@media print {
  body { padding: 16px; }
  .cover { padding: 40px 0 32px; }
  section { page-break-inside: avoid; }
}
"""

# ── Section builders ──────────────────────────────────────────────────────────

def _entities_query(db: Session, domain_id: str, org_id: int | None):
    query = scope_query_to_org(db.query(models.RawEntity), models.RawEntity, org_id)
    if domain_id:
        query = query.filter(models.RawEntity.domain == domain_id)
    return query


def _harmonization_query(db: Session, org_id: int | None):
    return scope_query_to_org(db.query(models.HarmonizationLog), models.HarmonizationLog, org_id)


def collect_entity_stats(db: Session, domain_id: str, org_id: int | None) -> "SectionData":
    """Format-neutral entity statistics: KPI cards + validation distribution.

    First section migrated onto the shared section payload; every format renders
    from this one collector rather than re-querying and re-formatting.
    """
    from backend.reporting.section_data import (
        SectionData, StatGrid, StatItem, Table,
    )

    query = _entities_query(db, domain_id, org_id)
    total = query.with_entities(func.count(models.RawEntity.id)).scalar() or 0
    by_status = query.with_entities(
        models.RawEntity.validation_status,
        func.count(models.RawEntity.id),
    ).group_by(models.RawEntity.validation_status).all()
    by_enrich = query.with_entities(
        models.RawEntity.enrichment_status,
        func.count(models.RawEntity.id),
    ).group_by(models.RawEntity.enrichment_status).all()

    status_map = {r[0]: r[1] for r in by_status}
    enrich_map = {r[0]: r[1] for r in by_enrich}

    valid_pct = round(status_map.get("valid", 0) / total * 100) if total else 0
    enriched = enrich_map.get("completed", 0)
    enrich_pct = round(enriched / total * 100) if total else 0

    grid = StatGrid(items=(
        StatItem(label="Total Entities", value=f"{total:,}"),
        StatItem(label="Valid", value=f"{status_map.get('valid', 0):,}", sub=f"{valid_pct}% of total"),
        StatItem(label="Pending", value=f"{status_map.get('pending', 0):,}", sub="awaiting validation"),
        StatItem(label="Enriched", value=f"{enriched:,}", sub=f"{enrich_pct}% coverage"),
    ))

    rows = tuple(
        (
            s or "—",
            f"{c:,}",
            f"{round(c / total * 100) if total else 0}%",
        )
        for s, c in sorted(by_status, key=lambda x: -x[1])
    )
    table = Table(
        columns=("Validation Status", "Count", "Distribution"),
        rows=rows,
        bar_column=2,
    )
    return SectionData(key="entity_stats", title="Entity Statistics", blocks=(grid, table))


def _section_entity_stats(db: Session, domain_id: str, org_id: int | None) -> str:
    from backend.reporting.html_renderer import render_html
    return render_html(collect_entity_stats(db, domain_id, org_id))


def _section_enrichment_coverage(db: Session, domain_id: str, org_id: int | None) -> str:
    query = _entities_query(db, domain_id, org_id)
    total = query.with_entities(func.count(models.RawEntity.id)).scalar() or 0
    completed = query.with_entities(func.count(models.RawEntity.id))\
        .filter(models.RawEntity.enrichment_status == "completed").scalar() or 0
    avg_cit = query.with_entities(func.avg(models.RawEntity.enrichment_citation_count))\
        .filter(models.RawEntity.enrichment_status == "completed").scalar() or 0
    top = query.with_entities(
        models.RawEntity.primary_label,
        models.RawEntity.enrichment_citation_count,
        models.RawEntity.enrichment_source,
    ).filter(
        models.RawEntity.enrichment_status == "completed"
    ).order_by(
        models.RawEntity.enrichment_citation_count.desc()
    ).limit(8).all()

    pct = round(completed / total * 100) if total else 0
    rows = "".join(f"""
        <tr><td>{r[0] or '—'}</td>
            <td>{r[1] or 0:,}</td>
            <td><span class="badge badge-blue">{r[2] or '—'}</span></td></tr>""" for r in top)

    return f"""<section>
    <h2>Enrichment Coverage</h2>
    <div class="grid">
        <div class="stat-card"><div class="label">Coverage</div><div class="value">{pct}%</div><div class="sub">{completed:,} of {total:,} entities</div></div>
        <div class="stat-card"><div class="label">Avg Citations</div><div class="value">{round(avg_cit or 0):,}</div><div class="sub">enriched entities only</div></div>
    </div>
    <table>
        <thead><tr><th>Entity</th><th>Citations</th><th>Source</th></tr></thead>
        <tbody>{rows if rows else '<tr><td colspan="3" style="color:#9ca3af;text-align:center;padding:20px">No enriched entities yet</td></tr>'}</tbody>
    </table>
</section>"""


def _section_top_brands(db: Session, domain_id: str, org_id: int | None) -> str:
    rows_q = _entities_query(db, domain_id, org_id).with_entities(
        models.RawEntity.secondary_label,
        func.count(models.RawEntity.id).label("n"),
    )\
        .filter(models.RawEntity.secondary_label.isnot(None))\
        .group_by(models.RawEntity.secondary_label)\
        .order_by(func.count(models.RawEntity.id).desc()).limit(15).all()
    max_n = rows_q[0][1] if rows_q else 1
    rows = "".join(f"""
        <tr><td>{r[0]}</td>
            <td>{r[1]:,}</td>
            <td><div class="bar-wrap">
                <div class="bar-bg"><div class="bar" style="width:{round(r[1]/max_n*100)}%"></div></div>
            </div></td></tr>""" for r in rows_q)

    return f"""<section>
    <h2>Top Secondary Labels / Classifications</h2>
    <table>
        <thead><tr><th>Label</th><th>Entities</th><th>Share</th></tr></thead>
        <tbody>{rows if rows else '<tr><td colspan="3" style="color:#9ca3af;text-align:center;padding:20px">No secondary-label data</td></tr>'}</tbody>
    </table>
</section>"""


def _section_topic_clusters(db: Session, domain_id: str, org_id: int | None) -> str:
    analyzer = TopicAnalyzer()
    try:
        result = analyzer.top_topics(domain_id=domain_id, top_n=15, org_id=org_id)
        topics = result.get("topics", [])
    except Exception:
        topics = []

    if not topics:
        return f"""<section><h2>Topic Clusters</h2>
        <p style="color:#9ca3af;padding:12px 0">No enriched concepts found — run enrichment first.</p>
        </section>"""

    max_c = topics[0]["count"] if topics else 1
    chips = "".join(f'<span class="chip">{t["concept"]} <b>({t["count"]})</b></span>' for t in topics[:20])
    rows = "".join(f"""
        <tr><td>{t["concept"]}</td>
            <td>{t["count"]:,}</td>
            <td><div class="bar-wrap">
                <div class="bar-bg"><div class="bar" style="width:{round(t['count']/max_c*100)}%"></div></div>
            </div></td></tr>""" for t in topics[:10])

    return f"""<section>
    <h2>Topic Clusters</h2>
    <div style="margin-bottom:16px">{chips}</div>
    <table>
        <thead><tr><th>Concept</th><th>Frequency</th><th>Relative weight</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
</section>"""


def _section_harmonization_log(db: Session, domain_id: str, org_id: int | None) -> str:
    logs = _harmonization_query(db, org_id)\
        .order_by(models.HarmonizationLog.executed_at.desc()).limit(10).all()

    if not logs:
        return f"""<section><h2>Harmonization Log</h2>
        <p style="color:#9ca3af;padding:12px 0">No harmonization steps executed yet.</p></section>"""

    def badge(reverted: bool) -> str:
        return '<span class="badge badge-red">Reverted</span>' if reverted else '<span class="badge badge-green">Applied</span>'

    rows = "".join(f"""
        <tr><td>{l.step_name or l.step_id}</td>
            <td>{l.records_updated:,}</td>
            <td>{badge(l.reverted)}</td>
            <td style="color:#9ca3af;font-size:12px">{l.executed_at.strftime('%Y-%m-%d %H:%M') if l.executed_at else '—'}</td></tr>"""
        for l in logs)

    return f"""<section>
    <h2>Harmonization Log</h2>
    <table>
        <thead><tr><th>Step</th><th>Records Updated</th><th>Status</th><th>Executed</th></tr></thead>
        <tbody>{rows}</tbody>
    </table>
</section>"""


def _section_decision_recommendations(
    db: Session,
    domain_id: str,
    org_id: int | None,
    benchmark_org: models.Organization | None = None,
) -> str:
    snapshot = AnalyticsService.get_domain_snapshot(
        db,
        TopicAnalyzer(),
        domain_id,
        org_id=org_id,
        benchmark_org=benchmark_org,
        top_n_concepts=10,
        top_n_entities=5,
    )
    actions = snapshot.get("recommended_actions") or []

    if not actions:
        return """<section>
    <h2>Suggested Next Actions</h2>
    <p style="color:#9ca3af;padding:12px 0">No recommendation signals yet — import or enrich more records to generate a prioritized action list.</p>
</section>"""

    def _priority_badge(priority: str) -> str:
        if priority == "high":
            return '<span class="badge badge-red">High priority</span>'
        if priority == "medium":
            return '<span class="badge badge-amber">Medium priority</span>'
        return '<span class="badge badge-gray">Low priority</span>'

    cards = "".join(
        f"""
        <div class="stat-card">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:center">
                <div class="label">{action["category"].replace("_", " ")}</div>
                {_priority_badge(action["priority"])}
            </div>
            <div style="font-size:16px;font-weight:700;color:#111827;margin-top:8px">{action["title"]}</div>
            <div class="sub" style="margin-top:8px;color:#4b5563">{action["detail"]}</div>
            <div style="margin-top:10px;font-size:12px;color:#6b7280">{action["evidence"]}</div>
        </div>"""
        for action in actions
    )

    return f"""<section>
    <h2>Suggested Next Actions</h2>
    <div class="grid">{cards}</div>
</section>"""


def _section_impact_projection(
    db: Session,
    domain_id: str,
    org_id: int | None,
    benchmark_org: models.Organization | None = None,
) -> str:
    snapshot = AnalyticsService.get_domain_snapshot(
        db,
        TopicAnalyzer(),
        domain_id,
        org_id=org_id,
        benchmark_org=benchmark_org,
        top_n_concepts=10,
        top_n_entities=10,
    )
    projection = snapshot.get("impact_projection") or {}
    score = int(projection.get("score") or 0)
    p10 = int((projection.get("range") or {}).get("p10") or 0)
    p50 = int((projection.get("range") or {}).get("p50") or score)
    p90 = int((projection.get("range") or {}).get("p90") or 0)
    confidence = str(projection.get("confidence") or "low").title()
    confidence_score = int(projection.get("confidence_score") or 0)
    drivers = projection.get("drivers") or {}

    def _bar(label: str, value: float) -> str:
        pct = max(0, min(100, round(float(value or 0))))
        return f"""
        <div style="margin-top:10px">
            <div style="display:flex;justify-content:space-between;font-size:12px;color:#4b5563">
                <span>{label}</span><b>{pct}%</b>
            </div>
            <div class="bar-bg" style="margin-top:5px"><div class="bar" style="width:{pct}%"></div></div>
        </div>"""

    return f"""<section>
    <h2>Impact Projection</h2>
    <div class="grid">
        <div class="stat-card">
            <div class="label">Expected Impact</div>
            <div class="value">{score}/100</div>
            <div class="sub">Monte Carlo median projection</div>
        </div>
        <div class="stat-card">
            <div class="label">Probable Range</div>
            <div class="value" style="font-size:24px">{p10}–{p90}</div>
            <div class="sub">P10 to P90 · expected {p50}</div>
        </div>
        <div class="stat-card">
            <div class="label">Confidence</div>
            <div class="value" style="font-size:24px">{confidence}</div>
            <div class="sub">{confidence_score}/100 stability score</div>
        </div>
    </div>
    <div class="callout">
        <h3>Executive interpretation</h3>
        <p>{projection.get("recommendation", "No impact projection is available yet.")}</p>
        <p style="margin-top:8px"><b>Brief angle:</b> {projection.get("brief_angle", "Use this as a directional signal only.")}</p>
        <p style="margin-top:8px;color:#6b7280">{projection.get("explanation", "")}</p>
    </div>
    <div class="stat-card">
        <div class="label">Projection drivers</div>
        {_bar("Coverage", drivers.get("coverage", 0))}
        {_bar("Quality", drivers.get("quality", 0))}
        {_bar("Citation signal", drivers.get("citation_signal", 0))}
        {_bar("Concentration", drivers.get("concentration", 0))}
    </div>
</section>"""


def _section_hidden_patterns(
    db: Session,
    domain_id: str,
    org_id: int | None,
    benchmark_org: models.Organization | None = None,
) -> str:
    result = PatternDiscoveryService.discover(
        db,
        domain_id=domain_id,
        org_id=org_id,
        limit=6,
    )
    patterns = result.get("patterns") or []
    if not patterns:
        return """<section>
    <h2>Hidden Patterns</h2>
    <p style="color:#9ca3af;padding:12px 0">No hidden patterns detected yet. Import or enrich more records to surface stronger signals.</p>
</section>"""

    cards = "".join(
        f"""
        <div class="stat-card">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:center">
                <div class="label">{pattern["type"].replace("_", " ")}</div>
                <span class="badge {'badge-green' if pattern['confidence'] == 'high' else 'badge-blue' if pattern['confidence'] == 'medium' else 'badge-gray'}">{pattern["confidence"].title()}</span>
            </div>
            <div style="font-size:16px;font-weight:700;color:#111827;margin-top:8px">{pattern["label"]}</div>
            <div style="margin-top:8px;font-size:13px;color:#4b5563;line-height:1.5">{pattern["evidence"]}</div>
            <div style="margin-top:10px;font-size:12px;color:#6b7280"><b>Action:</b> {pattern["recommended_action"]}</div>
            <div style="margin-top:10px" class="bar-wrap">
                <div class="bar-bg"><div class="bar" style="width:{int(pattern["impact_score"])}%"></div></div>
                <span>{int(pattern["impact_score"])}</span>
            </div>
        </div>"""
        for pattern in patterns
    )

    return f"""<section>
    <h2>Hidden Patterns</h2>
    <div class="callout">
        <h3>Executive reading</h3>
        <p>UKIP scanned the portfolio for non-obvious concentrations, outliers, quality risks, source imbalance and graph bridge signals.</p>
    </div>
    <div class="grid">{cards}</div>
</section>"""


def _section_institutional_benchmark(
    db: Session,
    domain_id: str,
    org_id: int | None,
    benchmark_profile_id: str | None = None,
    benchmark_org: models.Organization | None = None,
) -> str:
    snapshot = AnalyticsService.get_domain_snapshot(
        db,
        TopicAnalyzer(),
        domain_id,
        org_id=org_id,
        benchmark_org=benchmark_org,
        benchmark_profile_id=benchmark_profile_id,
        top_n_concepts=10,
        top_n_entities=5,
    )
    benchmark = snapshot.get("institutional_benchmark") or {}
    top_gaps = benchmark.get("top_gaps") or []
    rules = benchmark.get("rules") or []

    status = benchmark.get("status", "watch")
    status_badge = {
        "ready": '<span class="badge badge-green">Ready</span>',
        "watch": '<span class="badge badge-blue">Watch</span>',
        "gap": '<span class="badge badge-amber">Gap</span>',
    }.get(status, '<span class="badge badge-gray">Unknown</span>')
    readiness_pct = round(float(benchmark.get("readiness_pct") or 0))
    passed_rules = benchmark.get("passed_rules", 0)
    total_rules = benchmark.get("total_rules", 0)

    if status == "ready":
        benchmark_summary = (
            "This benchmark profile is currently in a ready state. "
            "The dataset is strong enough for a first stakeholder-facing interpretation with relatively limited benchmark risk."
        )
    elif status == "watch":
        benchmark_summary = (
            "This benchmark profile is in a watch state. "
            "The dataset already supports early interpretation, but important gaps still make the benchmark better suited for internal review than final external positioning."
        )
    else:
        benchmark_summary = (
            "This benchmark profile is currently showing a material gap. "
            "The benchmark is still useful as a directional baseline, but the current dataset should not be treated as fully decision-ready without additional enrichment or cleanup."
        )

    top_gap_text = ""
    if top_gaps:
        lead_gap = top_gaps[0]
        top_gap_text = (
            f"The main constraint right now is {lead_gap['label'].lower()}, "
            f"with evidence: {lead_gap['evidence']}"
        )

    cards = f"""
        <div class="stat-card">
            <div class="label">Benchmark Profile</div>
            <div class="value" style="font-size:18px">{benchmark.get("profile_name", "Institutional Benchmark")}</div>
            <div class="sub">{benchmark.get("description", "")}</div>
        </div>
        <div class="stat-card">
            <div class="label">Readiness</div>
            <div class="value">{readiness_pct}%</div>
            <div class="sub">{passed_rules} of {total_rules} rules satisfied</div>
        </div>
        <div class="stat-card">
            <div class="label">Status</div>
            <div class="value" style="font-size:18px">{status_badge}</div>
            <div class="sub">Baseline evaluation for the current dataset</div>
        </div>
    """

    callout = f"""
        <div class="callout">
            <h3>Executive reading</h3>
            <p>{benchmark_summary}</p>
            {'<p style="margin-top:8px">' + top_gap_text + '</p>' if top_gap_text else ''}
        </div>
    """

    rows = "".join(
        f"""
        <tr>
            <td>{gap["label"]}</td>
            <td><span class="badge {'badge-red' if gap['priority'] == 'high' else 'badge-amber' if gap['priority'] == 'medium' else 'badge-gray'}">{gap["priority"]}</span></td>
            <td>{gap["evidence"]}</td>
        </tr>"""
        for gap in top_gaps
    )

    rule_rows = "".join(
        f"""
        <tr>
            <td>{rule["label"]}</td>
            <td>{rule["observed"]}</td>
            <td>{rule["threshold"]}</td>
            <td>{'<span class="badge badge-green">Passed</span>' if rule["passed"] else '<span class="badge badge-amber">Below threshold</span>'}</td>
            <td>{rule["message"]}</td>
        </tr>"""
        for rule in rules
    )

    return f"""<section>
    <h2>Institutional Benchmark</h2>
    <div class="grid">{cards}</div>
    {callout}
    <table>
        <thead><tr><th>Gap</th><th>Priority</th><th>Evidence</th></tr></thead>
        <tbody>{rows if rows else '<tr><td colspan="3" style="color:#9ca3af;text-align:center;padding:20px">No major benchmark gaps detected.</td></tr>'}</tbody>
    </table>
    <div style="height:16px"></div>
    <table>
        <thead><tr><th>Rule</th><th>Observed</th><th>Threshold</th><th>Status</th><th>Interpretation</th></tr></thead>
        <tbody>{rule_rows if rule_rows else '<tr><td colspan="5" style="color:#9ca3af;text-align:center;padding:20px">No benchmark rules available.</td></tr>'}</tbody>
    </table>
</section>"""


def _section_agentic_trace(db: Session, domain_id: str, org_id: int | None) -> str:
    traces = (
        db.query(models.AnalysisContext)
        .filter(
            models.AnalysisContext.domain_id == domain_id,
            models.AnalysisContext.label.like("agentic-chat:%"),
        )
        .order_by(models.AnalysisContext.created_at.desc())
        .limit(5)
        .all()
    )
    if not traces:
        return """<section><h2>Agentic Research Trace</h2>
        <p style="color:#9ca3af;padding:12px 0">No saved agentic chat traces are available yet. Ask a question from the research assistant and save the trace to include it in this brief.</p></section>"""

    cards = []
    for trace in traces:
        try:
            payload = json.loads(trace.context_snapshot or "{}")
        except Exception:
            payload = {}
        question = payload.get("question") or trace.label.replace("agentic-chat:", "").strip()
        answer = payload.get("answer") or ""
        trace_meta = payload.get("trace") or {}
        sources = payload.get("sources") or []
        tool_list = ", ".join(trace_meta.get("tools_used") or []) or "No tools"
        source_list = ", ".join(
            str(s.get("label") or s.get("entity_id") or "source") for s in sources[:4] if isinstance(s, dict)
        ) or "No explicit sources"
        cards.append(f"""
        <div class="card" style="margin-bottom:12px">
            <div class="muted">Saved question</div>
            <h3 style="margin:4px 0 8px">{question}</h3>
            <p>{answer[:900]}</p>
            <p class="muted"><strong>Tools:</strong> {tool_list}</p>
            <p class="muted"><strong>Sources:</strong> {source_list}</p>
        </div>
        """)

    return f"""<section><h2>Agentic Research Trace</h2>
    <p>Esta seccion resume respuestas asistidas por IA generadas sobre datos del portafolio UKIP. Las fuentes y herramientas usadas quedan registradas para auditoria.</p>
    {''.join(cards)}
</section>"""

# ── Public API ────────────────────────────────────────────────────────────────

SECTION_BUILDERS = {
    "entity_stats": _section_entity_stats,
    "enrichment_coverage": _section_enrichment_coverage,
    "decision_recommendations": _section_decision_recommendations,
    "impact_projection": _section_impact_projection,
    "hidden_patterns": _section_hidden_patterns,
    "agentic_trace": _section_agentic_trace,
    "institutional_benchmark": _section_institutional_benchmark,
    "top_secondary_labels": _section_top_brands,
    "top_brands": _section_top_brands,
    "topic_clusters": _section_topic_clusters,
    "harmonization_log": _section_harmonization_log,
}

SECTION_LABELS = {
    "entity_stats": "Entity Statistics",
    "enrichment_coverage": "Enrichment Coverage",
    "decision_recommendations": "Suggested Next Actions",
    "impact_projection": "Impact Projection",
    "hidden_patterns": "Hidden Patterns",
    "agentic_trace": "Agentic Research Trace",
    "institutional_benchmark": "Institutional Benchmark",
    "top_secondary_labels": "Top Secondary Labels / Classifications",
    "top_brands": "Top Secondary Labels / Classifications",
    "topic_clusters": "Topic Clusters",
    "harmonization_log": "Harmonization Log",
}

# Deprecated section ids mapped to the public id that GET /reports/sections
# returns. Renderers must match on canonical ids only — a gate keyed on a
# deprecated alias silently drops the section for any client using the
# documented vocabulary. Run section lists through canonical_sections() at
# every renderer boundary so no renderer matches raw request strings.
SECTION_ALIASES = {
    "top_brands": "top_secondary_labels",
}


def canonical_sections(sections: list[str]) -> list[str]:
    """Resolve deprecated section aliases to their public ids, order preserved."""
    return [SECTION_ALIASES.get(section, section) for section in sections]


def build(
    db: Session,
    domain_id: str,
    sections: List[str],
    title: str | None = None,
    org_id: int | None = None,
    benchmark_profile_id: str | None = None,
    benchmark_org: models.Organization | None = None,
    stakeholder_profile: str | None = None,
    manual_sections: List[ManualReportSection] | None = None,
) -> str:
    """Return a complete, self-contained HTML report string."""
    domain_name = domain_id
    try:
        d = registry.get_domain(domain_id)
        domain_name = d.name if d else domain_id
    except Exception:
        pass

    report_title = title or f"UKIP Report — {domain_name}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stakeholder = _stakeholder_profile(stakeholder_profile)

    logo_svg = """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/>
    </svg>"""

    cover = f"""<div class="cover">
        <div class="logo">
            <div class="logo-icon">{logo_svg}</div>
            <span style="font-size:20px;font-weight:700;color:#111827">UKIP</span>
        </div>
        <h1>{report_title}</h1>
        <p class="meta">Domain: <b>{domain_name}</b> &nbsp;·&nbsp; Generated: <b>{generated_at}</b></p>
        <p class="meta" style="margin-top:8px">Stakeholder lens: <b>{stakeholder["label"]}</b></p>
    </div>"""

    body_sections = [
        _section_stakeholder_reading(
            db,
            domain_id,
            org_id,
            benchmark_profile_id=benchmark_profile_id,
            benchmark_org=benchmark_org,
            stakeholder_profile=stakeholder_profile,
        )
    ]
    for manual in manual_sections or []:
        manual_html = _section_manual_note(
            str(manual.get("title") or "Analyst Note"),
            str(manual.get("content") or ""),
        )
        if manual_html:
            body_sections.append(manual_html)
    for sec in sections:
        builder = SECTION_BUILDERS.get(sec)
        if builder:
            try:
                if sec == "institutional_benchmark":
                    rendered = builder(db, domain_id, org_id, benchmark_profile_id, benchmark_org)
                elif sec in {"decision_recommendations", "impact_projection", "hidden_patterns"}:
                    rendered = builder(db, domain_id, org_id, benchmark_org)
                else:
                    rendered = builder(db, domain_id, org_id)
                if not isinstance(rendered, str):
                    raise TypeError(f"section builder returned {type(rendered).__name__}, expected str")
                body_sections.append(rendered)
            except Exception as exc:
                body_sections.append(f'<section><h2>{SECTION_LABELS.get(sec, sec)}</h2>'
                                     f'<p style="color:#ef4444">Error building section: {exc}</p></section>')

    footer = f'<footer>Generated by UKIP &nbsp;·&nbsp; {generated_at}</footer>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{report_title}</title>
  <style>{_CSS}</style>
</head>
<body>
  {cover}
  {"".join(body_sections)}
  {footer}
</body>
</html>"""
