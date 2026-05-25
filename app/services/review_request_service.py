# app/services/review_request_service.py

"""
Client review request service for JAMM PX.

Sends a review request email to a client after engagement
completion. The email contains a 1-10 rating scale. High scores
(9-10) route to the firm's Google review page. Low scores (1-8)
collect private feedback sent to the firm owner.

Triggered manually by firm_owner or manager at engagement
completion. Never triggered by staff role.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.firm import Firm
from app.models.client import Client
from app.models.user import User
from app.core.enums import UserRole

logger = logging.getLogger(__name__)

REVIEW_RATING_BASE_URL = "https://app.jammpx.com/review"


def send_review_request(
    db: Session,
    firm: Firm,
    client: Client,
    engagement_id: UUID,
    requested_by: User,
) -> dict:
    """
    Send a review request email to the client.

    Validates:
    - Feature flag is enabled for this firm
    - Requesting user is firm_owner or manager
    - Client has an email address
    - Firm has a google_review_url configured in settings

    Returns { "sent": true } on success.
    Raises ValueError with a clear message on validation failure.
    """
    from app.services.email_service import EmailService

    # Feature flag check
    flags = firm.feature_flags or {}
    if not flags.get("review_requests_enabled"):
        raise ValueError(
            "Review requests are not enabled for this firm."
        )

    # Role check
    if requested_by.role not in (
        UserRole.firm_owner, UserRole.manager
    ):
        raise ValueError(
            "Only firm owners and managers can send review requests."
        )

    # Client email check
    if not client.email:
        raise ValueError(
            f"{client.name} does not have an email address on file."
        )

    # Google review URL check
    settings = firm.settings or {}
    google_review_url = settings.get("google_review_url")
    if not google_review_url:
        raise ValueError(
            "No Google review link configured. Add one in "
            "Settings → Review Requests before sending."
        )

    # Build rating buttons
    email_settings = EmailService.get_firm_email_settings(firm)
    _send_review_email(
        firm=firm,
        client=client,
        engagement_id=engagement_id,
        email_settings=email_settings,
    )

    # Log behavioral event
    from app.services.behavioral_log import log_event
    log_event(
        firm_id=firm.id,
        event_type="review_request.sent",
        entity_type="engagement",
        entity_id=engagement_id,
        actor_type="staff",
        actor_id=requested_by.id,
        metadata={
            "client_id": str(client.id),
            "client_email": client.email,
        },
    )

    return {"sent": True}


def _send_review_email(
    firm: Firm,
    client: Client,
    engagement_id: UUID,
    email_settings: dict,
) -> None:
    """Build and send the review request email to the client."""
    from app.services.email_service import EmailService

    firm_name = firm.name
    client_name = client.name.split()[0] if client.name else "there"

    rating_buttons = ""
    for i in range(1, 11):
        url = (
            f"{REVIEW_RATING_BASE_URL}"
            f"?score={i}&firm={firm.id}&engagement={engagement_id}"
        )
        rating_buttons += (
            f'<a href="{url}" style="display:inline-block;'
            f'margin:3px;padding:9px 14px;background:#1F3148;'
            f'color:#FFFFFF;text-decoration:none;border-radius:6px;'
            f'font-size:14px;font-weight:500;'
            f'font-family:Inter,sans-serif;">'
            f"{i}</a>"
        )

    html_body = f"""
    <div style="font-family:Inter,sans-serif;max-width:520px;
                margin:0 auto;padding:32px 24px;">
      <p style="font-size:15px;color:#1F3148;
                font-weight:500;margin-bottom:8px;">
        Hi {client_name},
      </p>
      <p style="font-size:14px;color:#374151;line-height:1.6;
                margin-bottom:20px;">
        It was great working with you. We'd love to hear how
        the experience went — it takes just one click.
      </p>
      <p style="font-size:14px;color:#1F3148;font-weight:500;
                margin-bottom:6px;">
        How would you rate your experience working with
        {firm_name}?
      </p>
      <p style="font-size:11px;color:#6B7280;margin-bottom:16px;">
        1 = Very poor &nbsp;&nbsp;&nbsp; 10 = Excellent
      </p>
      <div style="margin-bottom:28px;line-height:2.2;">
        {rating_buttons}
      </div>
      <p style="font-size:11px;color:#9CA3AF;line-height:1.5;">
        This takes one click and your feedback goes directly
        to the team at {firm_name}.
      </p>
    </div>
    """

    EmailService._send_raw(
        to_email=client.email,
        subject=f"How was your experience with {firm_name}?",
        html_body=html_body,
        from_name=firm_name,
        reply_to=email_settings.get("reply_to"),
        display_name=email_settings.get("display_name"),
    )
