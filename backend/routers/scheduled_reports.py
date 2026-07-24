"""
Sprint 79 — Scheduled Reports: background scheduler + CRUD router.

Provides:
  - Background scheduler thread that checks for due reports every 60 seconds
  - CRUD endpoints for scheduled reports (admin+)
  - Manual trigger endpoint
  - Report execution that calls existing exporters and sends via email
"""
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend import database, models
from backend.notifications.emit import emit_outbound
from backend.auth import require_role
from backend.database import get_db
from backend.tenant_quotas import assert_org_quota_available
from backend.tenant_access import (
    get_scoped_record,
    persisted_org_id,
    resolve_request_org_id,
    scope_query_to_org,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_ALL_FORMATS = ("pdf", "excel", "html")


# ── Schemas ───────────────────────────────────────────────────────────────────

class ScheduledReportCreate(BaseModel):
    name: str                          = Field(min_length=1, max_length=200)
    domain_id: str                     = Field(default="default", min_length=1, max_length=64)
    format: str                        = Field(default="pdf", pattern="^(pdf|excel|html)$")
    sections: List[str]                = Field(default_factory=list)
    report_title: Optional[str]        = Field(default=None, max_length=200)
    interval_minutes: int              = Field(default=1440, ge=60, le=10080)  # 1h to 7 days
    recipient_emails: List[str]        = Field(default_factory=list)


class ScheduledReportUpdate(BaseModel):
    name: Optional[str]                = Field(default=None, min_length=1, max_length=200)
    domain_id: Optional[str]           = Field(default=None, min_length=1, max_length=64)
    format: Optional[str]              = Field(default=None, pattern="^(pdf|excel|html)$")
    sections: Optional[List[str]]      = None
    report_title: Optional[str]        = Field(default=None, max_length=200)
    interval_minutes: Optional[int]    = Field(default=None, ge=60, le=10080)
    recipient_emails: Optional[List[str]] = None
    is_active: Optional[bool]          = None


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize(r: models.ScheduledReport) -> dict:
    return {
        "id":                r.id,
        "org_id":            r.org_id,
        "name":              r.name,
        "domain_id":         r.domain_id,
        "format":            r.format,
        "sections":          json.loads(r.sections) if r.sections else [],
        "report_title":      r.report_title,
        "interval_minutes":  r.interval_minutes,
        "recipient_emails":  json.loads(r.recipient_emails) if r.recipient_emails else [],
        "is_active":         r.is_active,
        "last_run_at":       r.last_run_at.isoformat() if r.last_run_at else None,
        "next_run_at":       r.next_run_at.isoformat() if r.next_run_at else None,
        "last_status":       r.last_status,
        "last_error":        r.last_error,
        "total_sent":        r.total_sent,
        "created_at":        r.created_at.isoformat() if r.created_at else None,
    }


# ── CRUD Endpoints ────────────────────────────────────────────────────────────

@router.post("/scheduled-reports", status_code=201, tags=["scheduled-reports"])
def create_scheduled_report(
    payload: ScheduledReportCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = persisted_org_id(resolve_request_org_id(db, current_user))
    assert_org_quota_available(db, org_id, "scheduled_reports", current_user=current_user)
    now = datetime.now(timezone.utc)
    r = models.ScheduledReport(
        org_id=org_id,
        name=payload.name.strip(),
        domain_id=payload.domain_id,
        format=payload.format,
        sections=json.dumps(payload.sections),
        report_title=payload.report_title,
        interval_minutes=payload.interval_minutes,
        recipient_emails=json.dumps(payload.recipient_emails),
        is_active=True,
        next_run_at=now + timedelta(minutes=payload.interval_minutes),
        last_status="pending",
        total_sent=0,
        created_at=now,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _serialize(r)


@router.get("/scheduled-reports", tags=["scheduled-reports"])
def list_scheduled_reports(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    items = scope_query_to_org(
        db.query(models.ScheduledReport),
        models.ScheduledReport,
        org_id,
    ).order_by(
        models.ScheduledReport.id.desc()
    ).all()
    return [_serialize(r) for r in items]


@router.get("/scheduled-reports/{report_id}", tags=["scheduled-reports"])
def get_scheduled_report(
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    r = get_scoped_record(db, models.ScheduledReport, report_id, org_id)
    if not r:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    return _serialize(r)


@router.put("/scheduled-reports/{report_id}", tags=["scheduled-reports"])
def update_scheduled_report(
    report_id: int = Path(..., ge=1),
    payload: ScheduledReportUpdate = ...,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    r = get_scoped_record(db, models.ScheduledReport, report_id, org_id)
    if not r:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    if payload.name is not None:
        r.name = payload.name.strip()
    if payload.domain_id is not None:
        r.domain_id = payload.domain_id
    if payload.format is not None:
        r.format = payload.format
    if payload.sections is not None:
        r.sections = json.dumps(payload.sections)
    if payload.report_title is not None:
        r.report_title = payload.report_title
    if payload.interval_minutes is not None:
        r.interval_minutes = payload.interval_minutes
        base = r.last_run_at or datetime.now(timezone.utc)
        r.next_run_at = base + timedelta(minutes=payload.interval_minutes)
    if payload.recipient_emails is not None:
        r.recipient_emails = json.dumps(payload.recipient_emails)
    if payload.is_active is not None:
        r.is_active = payload.is_active
        if payload.is_active and not r.next_run_at:
            r.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=r.interval_minutes)
    db.commit()
    db.refresh(r)
    return _serialize(r)


@router.delete("/scheduled-reports/{report_id}", tags=["scheduled-reports"])
def delete_scheduled_report(
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    org_id = resolve_request_org_id(db, current_user)
    r = get_scoped_record(db, models.ScheduledReport, report_id, org_id)
    if not r:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    db.delete(r)
    db.commit()
    return {"deleted": report_id}


@router.post("/scheduled-reports/{report_id}/trigger", tags=["scheduled-reports"])
def trigger_scheduled_report(
    report_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_role("super_admin", "admin")),
):
    """Manually trigger a scheduled report right now."""
    org_id = resolve_request_org_id(db, current_user)
    r = get_scoped_record(db, models.ScheduledReport, report_id, org_id)
    if not r:
        raise HTTPException(status_code=404, detail="Scheduled report not found")
    result = _execute_report(r, db)
    return result


# ── Report executor ───────────────────────────────────────────────────────────

def _execute_report(schedule: models.ScheduledReport, db: Session) -> dict:
    """Generate and email a scheduled report. Never raises."""
    now = datetime.now(timezone.utc)
    schedule.last_run_at = now
    schedule.last_status = "running"
    schedule.last_error = None
    db.commit()

    domain_id = schedule.domain_id or "default"
    sections = json.loads(schedule.sections) if schedule.sections else []
    recipients = json.loads(schedule.recipient_emails) if schedule.recipient_emails else []
    fmt = schedule.format or "pdf"
    report_title = schedule.report_title or schedule.name
    org_id = getattr(schedule, "org_id", None)

    try:
        # ── 1. Generate report bytes ────────────────────────────────────────
        from backend import report_builder as _rb
        from backend.exporters.excel_exporter import EnterpriseExcelExporter

        # Use all sections if none specified
        if not sections:
            sections = list(_rb.SECTION_LABELS.keys())

        # Filter to valid sections only
        sections = [s for s in sections if s in _rb.SECTION_BUILDERS]

        # Sections this format cannot render are dropped by the exporter; record
        # the omission on the run instead of dropping it silently (phase 4/6).
        from backend.reporting import format_support
        omitted_sections = format_support.unsupported_sections(fmt, sections)

        if fmt == "excel":
            report_bytes = EnterpriseExcelExporter().build(
                db,
                domain_id,
                sections,
                org_id=org_id,
            )
            attachment_filename = (
                f"ukip_report_{domain_id}_{now.strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            attachment_mimetype = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        elif fmt == "pdf":
            try:
                from weasyprint import HTML as _WPHTML  # type: ignore
            except ImportError:
                raise RuntimeError(
                    "PDF reports require weasyprint. "
                    "Install it with: pip install weasyprint"
                )
            html = _rb.build(db, domain_id, sections, report_title, org_id=org_id)
            report_bytes = _WPHTML(string=html).write_pdf()
            attachment_filename = (
                f"ukip_report_{domain_id}_{now.strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            attachment_mimetype = "application/pdf"
        else:  # html
            html = _rb.build(db, domain_id, sections, report_title, org_id=org_id)
            report_bytes = html.encode("utf-8")
            attachment_filename = (
                f"ukip_report_{domain_id}_{now.strftime('%Y%m%d_%H%M%S')}.html"
            )
            attachment_mimetype = "text/html"

        # ── 2. Send email ───────────────────────────────────────────────────
        if recipients:
            smtp_settings = db.get(models.NotificationSettings, 1)
            if not smtp_settings or not smtp_settings.enabled or not smtp_settings.smtp_host:
                raise RuntimeError(
                    "SMTP not configured. Configure SMTP in Settings → Notifications."
                )
            from backend.notifications.email_sender import send_report_email
            subject = f"[UKIP] {report_title} — {now.strftime('%Y-%m-%d')}"
            body = (
                f"Your scheduled report '{schedule.name}' is attached.\n\n"
                f"Domain: {domain_id}\n"
                f"Format: {fmt.upper()}\n"
                f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
            )
            sent = send_report_email(
                settings=smtp_settings,
                to_addresses=recipients,
                subject=subject,
                body=body,
                attachment_bytes=report_bytes,
                attachment_filename=attachment_filename,
                attachment_mimetype=attachment_mimetype,
            )
            if not sent:
                raise RuntimeError("SMTP send failed — check server logs for details.")

        schedule.last_status = "success"
        schedule.total_sent = (schedule.total_sent or 0) + len(recipients)
        schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)
        db.commit()
        emit_outbound(
            "report.sent",
            {
                "schedule": schedule.name,
                "recipients": len(recipients),
                "format": fmt,
                "omitted_sections": omitted_sections,
            },
            database.SessionLocal,
        )
        return {
            "success": True,
            "recipients": len(recipients),
            "format": fmt,
            "attachment": attachment_filename,
            "omitted_sections": omitted_sections,
        }

    except Exception as exc:
        logger.exception("Scheduled report %d (%s) failed", schedule.id, schedule.name)
        schedule.last_status = "error"
        schedule.last_error = str(exc)
        schedule.next_run_at = now + timedelta(minutes=schedule.interval_minutes)
        db.commit()
        emit_outbound(
            "report.failed",
            {"schedule": schedule.name, "error": str(exc)},
            database.SessionLocal,
        )
        return {"success": False, "error": str(exc)}


# ── Background scheduler ──────────────────────────────────────────────────────

_scheduler_thread: threading.Thread | None = None
_scheduler_state_lock = threading.Lock()
SCHEDULER_POLL_SECONDS = 60
_scheduler_state = {
    "started_at": None,
    "last_heartbeat_at": None,
    "last_success_at": None,
    "last_loop_error": None,
    "last_loop_error_at": None,
}


def _update_scheduler_state(**updates) -> None:
    with _scheduler_state_lock:
        _scheduler_state.update(updates)


def get_scheduler_status(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    with _scheduler_state_lock:
        snapshot = dict(_scheduler_state)

    last_heartbeat_at = snapshot["last_heartbeat_at"]
    heartbeat_age = None
    if last_heartbeat_at is not None:
        heartbeat_age = round((now - last_heartbeat_at).total_seconds(), 2)

    return {
        "alive": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        "poll_seconds": SCHEDULER_POLL_SECONDS,
        "stale_after_seconds": SCHEDULER_POLL_SECONDS * 3,
        "started_at": snapshot["started_at"].isoformat() if snapshot["started_at"] else None,
        "last_heartbeat_at": last_heartbeat_at.isoformat() if last_heartbeat_at else None,
        "last_heartbeat_age_seconds": heartbeat_age,
        "last_success_at": snapshot["last_success_at"].isoformat() if snapshot["last_success_at"] else None,
        "last_loop_error": snapshot["last_loop_error"],
        "last_loop_error_at": (
            snapshot["last_loop_error_at"].isoformat()
            if snapshot["last_loop_error_at"]
            else None
        ),
    }


def _scheduler_loop():
    """Check for due scheduled reports every 60 seconds."""
    while True:
        _update_scheduler_state(last_heartbeat_at=datetime.now(timezone.utc))
        try:
            with database.SessionLocal() as db:
                now = datetime.now(timezone.utc)
                due = db.query(models.ScheduledReport).filter(
                    models.ScheduledReport.is_active == True,  # noqa: E712
                    models.ScheduledReport.next_run_at <= now,
                    models.ScheduledReport.last_status != "running",
                ).all()
                for schedule in due:
                    try:
                        logger.info(
                            "Scheduled report %d (%s) is due — dispatching",
                            schedule.id, schedule.name,
                        )
                        # Phase 4 migration (flag-gated, default off → in-process):
                        # shadow/queue also enqueue a durable job.
                        from backend.jobs.migration import dispatch_due

                        dispatch_due(db, domain="reports", job_type="report.execute",
                                     schedule=schedule, execute=_execute_report)
                    except Exception:
                        logger.exception(
                            "Unexpected error in scheduled report %d", schedule.id
                        )
                _update_scheduler_state(
                    last_success_at=datetime.now(timezone.utc),
                    last_loop_error=None,
                    last_loop_error_at=None,
                )
        except Exception:
            logger.exception("Report scheduler loop error")
            _update_scheduler_state(
                last_loop_error="report_scheduler_loop_error",
                last_loop_error_at=datetime.now(timezone.utc),
            )
        time.sleep(SCHEDULER_POLL_SECONDS)


def start_scheduler():
    """Start the background scheduler thread (called once during app lifespan)."""
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop, daemon=True, name="report-scheduler"
    )
    _scheduler_thread.start()
    _update_scheduler_state(started_at=datetime.now(timezone.utc))
    logger.info("Report scheduler started")
