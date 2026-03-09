"""
SMTP email notifications (Sprint 43).
Uses stdlib smtplib only — no extra pip dependencies.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
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
    if not settings.enabled:
        return False
    if not settings.recipient_email or not settings.smtp_host:
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
            msg["To"] = settings.recipient_email
            msg.attach(MIMEText(body, "plain"))
            smtp.sendmail(
                msg["From"],
                settings.recipient_email,
                msg.as_string(),
            )
        logger.info("Email notification sent: %s", subject)
        return True
    except Exception:
        logger.warning("Email notification failed: %s", subject, exc_info=True)
        return False
