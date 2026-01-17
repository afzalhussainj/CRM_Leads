import logging
import os
from typing import Iterable, Optional

import requests

MAILTRAP_API_TOKEN = os.getenv("MAILTRAP_API_TOKEN")
MAILTRAP_SEND_URL = "https://send.api.mailtrap.io/api/send"

logger = logging.getLogger(__name__)


def send_mailtrap_email(
    subject: str,
    recipients: Iterable[str],
    html: Optional[str] = None,
    text: Optional[str] = None,
    from_email: Optional[str] = None,
):
    """Send an email via Mailtrap API.

    Args:
        subject: Email subject
        recipients: Iterable of recipient email addresses
        html: HTML body
        text: Plain text body (fallback if HTML not provided)
        from_email: Sender email (Mailtrap allows any for testing)
    Raises:
        RuntimeError: If the request fails or API token is missing
    """
    if not MAILTRAP_API_TOKEN:
        raise RuntimeError("MAILTRAP_API_TOKEN is not configured")

    if not recipients:
        raise RuntimeError("No recipients provided")

    payload = {
        "from": {
            "email": from_email or os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com"),
            "name": os.getenv("APPLICATION_NAME", "CRM"),
        },
        "to": [{"email": r} for r in recipients],
        "subject": subject,
    }

    if html:
        payload["html"] = html
    if text:
        payload["text"] = text
    if not html and not text:
        payload["text"] = ""

    headers = {
        "Authorization": f"Bearer {MAILTRAP_API_TOKEN}",
        "Content-Type": "application/json",
    }

    resp = requests.post(MAILTRAP_SEND_URL, json=payload, headers=headers, timeout=20)
    if resp.status_code >= 300:
        logger.error("Mailtrap API error %s: %s", resp.status_code, resp.text)
        raise RuntimeError(f"Mailtrap API returned {resp.status_code}")
    return True
