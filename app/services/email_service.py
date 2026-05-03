# app/services/email_service.py

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Resolve the templates directory relative to this file's location
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "email"


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
    def _send_raw(to_email: str, subject: str, html_body: str, firm_name: str) -> bool:
        """Send email via AWS SES. Returns True on success, False on failure.
        Never raises — all exceptions are caught and logged.
        Never logs email content — only recipient, subject, and errors.
        """
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
        from app.core.config import get_settings

        settings = get_settings()
        from_email = settings.AWS_SES_FROM_EMAIL
        if not from_email:
            logger.warning("_send_raw: AWS_SES_FROM_EMAIL is not configured — email not sent")
            return False

        source = f"{firm_name} <{from_email}>"

        try:
            client = boto3.client(
                "ses",
                region_name=settings.AWS_REGION,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )
            client.send_email(
                Source=source,
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )
            logger.info("Email sent: to=%s subject=%s", to_email, subject)
            return True
        except (BotoCoreError, ClientError) as e:
            logger.error("SES send failed: to=%s subject=%s error=%s", to_email, subject, str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error sending email: to=%s subject=%s error=%s", to_email, subject, str(e))
            return False

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
        return EmailService._send_raw(to_email, subject, html, firm_name)

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
        return EmailService._send_raw(to_email, subject, html, firm_name)

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
        subject = f"[{firm_name}] Invoice {invoice_number} \u2014 Payment Due"
        return EmailService._send_raw(to_email, subject, html, firm_name)

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
        return EmailService._send_raw(
            to_email=to_email,
            subject="Reset your JAMM PX password",
            html_body=html,
            firm_name="JAMM PX",
        )

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
        subject = f"Welcome to {firm_name} \u2014 Your Client Portal"
        return EmailService._send_raw(to_email, subject, html, firm_name)
