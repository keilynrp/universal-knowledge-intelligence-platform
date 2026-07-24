"""Scheduled-report omission recording (unify-report-format-coverage, phase 6).

A scheduled Excel report whose section list includes a section Excel cannot
render (agentic_trace) must record the omission on the run — surfaced on the run
result and the report.sent event — rather than silently dropping it. HTML/PDF
render every section, so they record no omissions.
"""
import json

from backend import models
from backend.routers.scheduled_reports import _execute_report


def _make_schedule(db, fmt, sections):
    """A schedule with no recipients: _execute_report generates the report and
    skips the email send, so the run reaches the success path without SMTP."""
    r = models.ScheduledReport(
        name=f"Test {fmt}",
        domain_id="default",
        format=fmt,
        sections=json.dumps(sections),
        recipient_emails=json.dumps([]),
        interval_minutes=1440,
        is_active=True,
        last_status="pending",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_excel_scheduled_report_records_omitted_sections(db_session):
    schedule = _make_schedule(db_session, "excel", ["entity_stats", "agentic_trace"])
    result = _execute_report(schedule, db_session)

    assert result["success"] is True
    assert "agentic_trace" in result["omitted_sections"]   # excel cannot render it
    assert "entity_stats" not in result["omitted_sections"]  # excel renders it


def test_html_scheduled_report_has_no_omissions(db_session):
    schedule = _make_schedule(db_session, "html", ["entity_stats", "agentic_trace"])
    result = _execute_report(schedule, db_session)

    assert result["success"] is True
    assert result["omitted_sections"] == []                # html renders everything
