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
    logger.info("Attempting to send WhatsApp message to %s", to)
    
    try:
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            return "Twilio credentials missing. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."

        client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

        whatsapp_to = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        whatsapp_from = settings.twilio_whatsapp_from
        
        if not whatsapp_from.startswith("whatsapp:"):
            whatsapp_from = f"whatsapp:{whatsapp_from}"

        msg = client.messages.create(
            body=message,
            from_=whatsapp_from,
            to=whatsapp_to,
        )

        logger.info("✅ WhatsApp sent successfully to %s, SID=%s", to, msg.sid)
        return f"WhatsApp message sent to {to} (SID: {msg.sid})"
    except Exception as exc:
        # Capture specific Twilio error details if available
        error_msg = str(exc)
        if hasattr(exc, 'code'):
            error_msg = f"Twilio Error {exc.code}: {exc.msg}"
            logger.error("🛑 Twilio API Error: %s", error_msg)
        else:
            logger.exception("🛑 Failed to send WhatsApp to %s", to)
            
        return f"Failed to send WhatsApp: {error_msg}. Check if recipient has joined the Twilio Sandbox by sending 'join {whatsapp_from.split(':')[-1]}' to the sandbox number."
