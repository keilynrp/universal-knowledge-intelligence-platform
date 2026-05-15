"""
SMTP email notifications (Sprint 43) + report delivery with attachments (Sprint 79).
Uses stdlib smtplib only — no extra pip dependencies.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def _decrypt_password(encrypted: str) -> str:
    """Decrypt SMTP password using the Fernet key configured at startup."""
    if not encrypted:
        return ""
    try:
        from backend.encryption import decrypt_value
        return decrypt_value(encrypted)
    except Exception:
        logger.warning("Failed to decrypt SMTP password; using as-is")
        return encrypted


def send_notification(settings, subject: str, body: str) -> bool:
    """
    Send a plain-text email via TLS SMTP.
    Returns True on success, False on any error (never raises).
    """
    if not settings.recipient_email:
        return False
    return send_plain_email(settings, settings.recipient_email, subject, body)


def send_plain_email(settings, to_address: str, subject: str, body: str) -> bool:
    """
    Send a plain-text email via TLS SMTP to a specific recipient.
    Returns True on success, False on any error (never raises).
    """
    if not settings.enabled:
        return False
    if not to_address or not settings.smtp_host:
        return False

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, _decrypt_password(settings.smtp_password))

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.from_email or settings.smtp_user
            msg["To"] = to_address
            msg.attach(MIMEText(body, "plain"))
            smtp.sendmail(
                msg["From"],
                to_address,
                msg.as_string(),
            )
        logger.info("Email notification sent: %s", subject)
        return True
    except Exception:
        logger.warning("Email notification failed: %s", subject, exc_info=True)
        return False


def send_report_email(
    settings,
    to_addresses: list[str],
    subject: str,
    body: str,
    attachment_bytes: bytes,
    attachment_filename: str,
    attachment_mimetype: str = "application/octet-stream",
) -> bool:
    """
    Send a report as an email attachment to one or more recipients.
    Uses the same SMTP settings as send_notification.
    Returns True on success, False on any error (never raises).
    """
    if not settings.enabled or not settings.smtp_host:
        logger.info("SMTP not configured — skipping report email '%s'", subject)
        return False
    if not to_addresses:
        return False

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, _decrypt_password(settings.smtp_password))

            from_addr = settings.from_email or settings.smtp_user

            for recipient in to_addresses:
                msg = MIMEMultipart()
                msg["Subject"] = subject
                msg["From"] = from_addr
                msg["To"] = recipient
                msg.attach(MIMEText(body, "plain"))

                part = MIMEApplication(attachment_bytes, Name=attachment_filename)
                part["Content-Disposition"] = f'attachment; filename="{attachment_filename}"'
                part["Content-Type"] = attachment_mimetype
                msg.attach(part)

                smtp.sendmail(from_addr, recipient, msg.as_string())
                logger.info("Report email sent to %s: %s", recipient, subject)

        return True
    except Exception:
        logger.warning("Report email failed: %s", subject, exc_info=True)
        return False
