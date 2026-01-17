import logging
import os
from typing import Iterable, Optional

import mailtrap as mt

logger = logging.getLogger(__name__)


def send_mailtrap_email(
    subject: str,
    recipients: Iterable[str],
    html: Optional[str] = None,
    text: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
):
    """Send an email via Mailtrap API using the official library.

    Args:
        subject: Email subject
        recipients: Iterable of recipient email addresses
        html: HTML body
        text: Plain text body (fallback if HTML not provided)
        from_email: Sender email address
        from_name: Sender name
    Raises:
        RuntimeError: If the request fails or API token is missing
    """
    token = os.getenv("MAILTRAP_API_TOKEN")
    if not token:
        raise RuntimeError("MAILTRAP_API_TOKEN is not configured")

    if not recipients:
        raise RuntimeError("No recipients provided")

    from_email = from_email or os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")
    from_name = from_name or os.getenv("APPLICATION_NAME", "CRM")
    inbox_id = int(os.getenv("MAILTRAP_INBOX_ID", "3886115"))

    try:
        # Create mail using the official library
        mail = mt.Mail(
            sender=mt.Address(email=from_email, name=from_name),
            to=[mt.Address(email=r) for r in recipients],
            subject=subject,
            text=text or "",
            html=html or "",
            category="CRM Email",
        )

        # Create client and send
        client = mt.MailtrapClient(token=token, sandbox=True, inbox_id=inbox_id)
        response = client.send(mail)
        
        logger.info("Mailtrap email sent successfully: %s", response)
        return True
    except Exception as e:
        logger.error("Mailtrap API error: %s", str(e))
        raise RuntimeError(f"Mailtrap API failed: {str(e)}")
