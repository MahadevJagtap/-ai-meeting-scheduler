"""
Instant notification service for immediate user feedback.
Wraps synchronous communication tools in thread-safe async wrappers.
"""

import logging
import anyio
from app.tools.communication_tools import send_whatsapp
from app.config import get_settings

logger = logging.getLogger(__name__)

async def send_instant_whatsapp(to: str, message: str) -> None:
    """
    Send an instant WhatsApp message using anyio to-thread to prevent blocking.
    
    Args:
        to: Recipient phone number or whatsapp: string.
        message: The message body.
    """
    try:
        # anyio.to_thread.run_sync allows us to run synchronous code in a thread pool
        # This prevents the Twilio HTTP request from blocking the FastAPI event loop.
        await anyio.to_thread.run_sync(send_whatsapp.invoke, {"to": to, "message": message})
        logger.info("Instant WhatsApp notification triggered for %s", to)
    except Exception as exc:
        logger.error("Failed to send instant WhatsApp: %s", exc)
        # We don't raise here as notification failure shouldn't crash the main flow
