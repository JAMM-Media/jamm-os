# app/services/email_service.py

import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "email"
_POSTMARK_API_URL = "https://api.postmarkapp.com/email"


class EmailService:

    @staticmethod
    def _render_template(template_name: str, context: dict) -> str:
        """Load and render a Jinja2 template. Returns HTML string."""
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        template = env.get_template(template_name)
        return template.render(**context)

    @staticmethod
    def _send(to_email: str, subject: str, html_body: str, from_name: str) -> None:
        """Send email via Postmark HTTP API. Raises on failure."""
        from app.core.config import get_settings

        settings = get_settings()
        api_key = settings.POSTMARK_API_KEY
        if not api_key:
            raise RuntimeError("POSTMARK_API_KEY is not configured — email not sent")

        payload = {
            "From": f"{from_name} <noreply@jammpx.com>",
            "To": to_email,
            "Subject": subject,
            "HtmlBody": html_body,
            "MessageStream": "outbound",
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Postmark-Server-Token": api_key,
        }
        try:
            response = requests.post(_POSTMARK_API_URL, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            logger.info("Email sent: to=%s subject=%s", to_email, subject)
        except requests.RequestException as e:
            logger.error("Postmark send failed: to=%s subject=%s error=%s", to_email, subject, str(e))
            raise

    @staticmethod
    def _send_raw(to_email: str, subject: str, html_body: str, from_name: str) -> None:
        """Direct HTML send — used by magic link and portal invite flows."""
        EmailService._send(to_email, subject, html_body, from_name)

    @staticmethod
    def send_notification_email(
        to_email: str,
        firm_name: str,
        recipient_name: str,
        title: str,
        body: str,
        app_url: str = "",
    ) -> bool:
        html = EmailService._render_template("notification.html", {
            "firm_name": firm_name,
            "recipient_name": recipient_name,
            "title": title,
            "body": body,
            "app_url": app_url,
        })
        subject = f"[{firm_name}] {title}"
        EmailService._send(to_email, subject, html, firm_name)
        return True

    @staticmethod
    def send_document_request_email(
        to_email: str,
        firm_name: str,
        recipient_name: str,
        engagement_name: str,
        document_request_title: str,
        items: list[str],
        portal_url: str,
    ) -> bool:
        html = EmailService._render_template("document_request.html", {
            "firm_name": firm_name,
            "recipient_name": recipient_name,
            "engagement_name": engagement_name,
            "document_request_title": document_request_title,
            "items": items,
            "portal_url": portal_url,
        })
        subject = f"[{firm_name}] Document Request: {document_request_title}"
        EmailService._send(to_email, subject, html, firm_name)
        return True

    @staticmethod
    def send_invoice_email(
        to_email: str,
        firm_name: str,
        recipient_name: str,
        invoice_number: str,
        amount_due: str,
        due_date: str,
        payment_url: str,
    ) -> bool:
        html = EmailService._render_template("invoice.html", {
            "firm_name": firm_name,
            "recipient_name": recipient_name,
            "invoice_number": invoice_number,
            "amount_due": amount_due,
            "due_date": due_date,
            "payment_url": payment_url,
        })
        subject = f"[{firm_name}] Invoice {invoice_number} — Payment Due"
        EmailService._send(to_email, subject, html, firm_name)
        return True

    @staticmethod
    def send_password_reset_email(
        to_email: str,
        recipient_name: str,
        reset_url: str,
        expiry_hours: int = 1,
    ) -> bool:
        html = EmailService._render_template("password_reset.html", {
            "recipient_name": recipient_name,
            "reset_url": reset_url,
            "expiry_hours": expiry_hours,
            "firm_name": "JAMM PX",
        })
        EmailService._send(
            to_email=to_email,
            subject="Reset your JAMM PX password",
            html_body=html,
            from_name="JAMM PX",
        )
        return True

    @staticmethod
    def send_welcome_email(
        to_email: str,
        firm_name: str,
        recipient_name: str,
        portal_url: str,
        temp_password: str,
    ) -> bool:
        html = EmailService._render_template("welcome.html", {
            "firm_name": firm_name,
            "recipient_name": recipient_name,
            "portal_url": portal_url,
            "temp_password": temp_password,
        })
        subject = f"Welcome to {firm_name} — Your Client Portal"
        EmailService._send(to_email, subject, html, firm_name)
        return True
