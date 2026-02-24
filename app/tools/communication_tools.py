"""
Communication tools for sending notifications via Email and WhatsApp.

Uses aiosmtplib for async email delivery and Twilio for WhatsApp messaging.
"""

from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from langchain_core.tools import tool
from twilio.rest import Client as TwilioClient

from app.config import get_settings

logger = logging.getLogger(__name__)


@tool
async def send_email(to: str, subject: str, body: str) -> str:
    """
    Send an email notification via SMTP.

    Args:
        to:      Recipient email address.
        subject: Email subject line.
        body:    Email body content (plain text).

    Returns:
        Confirmation message on success, or error details.
    """
    settings = get_settings()
    try:
        message = MIMEMultipart()
        message["From"] = settings.smtp_from_email
        message["To"] = to
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain"))

        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            start_tls=True,
            username=settings.smtp_username,
            password=settings.smtp_password,
        )

        logger.info("Email sent to %s: %s", to, subject)
        return f"Email sent successfully to {to}"
    except Exception as exc:
        logger.exception("Failed to send email to %s", to)
        return f"Failed to send email: {exc}"


@tool
def send_whatsapp(to: str, message: str) -> str:
    """
    Send a WhatsApp message via Twilio.

    Args:
        to:      Recipient phone number in E.164 format (e.g., '+1234567890').
        message: Message content to send.

    Returns:
        Confirmation with Twilio message SID on success, or error details.
    """
    settings = get_settings()
    try:
        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

        whatsapp_to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"

        msg = client.messages.create(
            body=message,
            from_=settings.twilio_whatsapp_from,
            to=whatsapp_to,
        )

        logger.info("WhatsApp sent to %s, SID=%s", to, msg.sid)
        return f"WhatsApp message sent to {to} (SID: {msg.sid})"
    except Exception as exc:
        logger.exception("Failed to send WhatsApp to %s", to)
        return f"Failed to send WhatsApp: {exc}"
