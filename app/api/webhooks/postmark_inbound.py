# app/api/webhooks/postmark_inbound.py

import logging
import re
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.core.enums import EnrollmentStatus, NotificationType, NotificationTier, RecipientType, UserRole
from app.db.session import get_db
from app.models.enrollment import Enrollment
from app.models.lead import Lead
from app.models.lead_message import LeadMessage
from app.models.user import User
from app.services.behavioral_log import log_event
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

_security = HTTPBasic()


def _verify_credentials(credentials: HTTPBasicCredentials = Depends(_security)) -> None:
    """Constant-time credential check to prevent timing attacks."""
    from app.core.config import get_settings
    settings = get_settings()
    username_ok = secrets.compare_digest(
        credentials.username.encode(), settings.POSTMARK_INBOUND_WEBHOOK_USERNAME.encode()
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode(), settings.POSTMARK_INBOUND_WEBHOOK_PASSWORD.encode()
    )
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


def _strip_html(html: str) -> str:
    return re.sub(r'<[^>]+>', '', html).strip()


@router.post("/postmark-inbound", status_code=status.HTTP_200_OK)
def postmark_inbound(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _: None = Depends(_verify_credentials),
):
    """Receive Postmark inbound webhook, match reply to Lead via MailboxHash.

    Always returns 200 for unmatched or malformed payloads to avoid Postmark
    retry storms. Only 401 is returned for real auth failure.

    NOTE: This endpoint does NOT advance any Enrollment's current_step_id or
    evaluate wait_until_event conditions -- that is step-execution engine logic
    not yet built. This task captures the reply and fires the behavioral event
    only; a future task consumes that event.
    """
    mailbox_hash = payload.get("MailboxHash", "").strip()

    if not mailbox_hash:
        logger.warning("postmark_inbound: missing MailboxHash, ignoring")
        return {"status": "ignored", "reason": "no_mailbox_hash"}

    try:
        lead_id = uuid.UUID(mailbox_hash)
    except ValueError:
        logger.warning("postmark_inbound: malformed MailboxHash=%r, ignoring", mailbox_hash)
        return {"status": "ignored", "reason": "malformed_mailbox_hash"}

    # Query across all firms -- the webhook has no firm-scoping context of its own.
    # MailboxHash IS the routing key.
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        logger.warning("postmark_inbound: no Lead found for id=%s, ignoring", lead_id)
        return {"status": "ignored", "reason": "lead_not_found"}

    text_body = (payload.get("TextBody") or "").strip()
    if not text_body:
        html_body = payload.get("HtmlBody") or ""
        text_body = _strip_html(html_body)

    if not text_body:
        logger.warning("postmark_inbound: empty body for lead=%s, ignoring", lead_id)
        return {"status": "ignored", "reason": "empty_body"}

    message = LeadMessage(
        firm_id=lead.firm_id,
        lead_id=lead.id,
        sender_id=None,
        sender_role="lead",
        body=text_body,
        source="inbound_email",
    )
    db.add(message)
    db.commit()

    log_event(
        event_type="lead.email_replied",
        firm_id=lead.firm_id,
        entity_type="lead",
        entity_id=lead.id,
        actor_type="lead",
        metadata={"message_id": str(message.id), "from": payload.get("From", "")},
    )

    logger.info("postmark_inbound: reply captured lead=%s message=%s", lead_id, message.id)

    enrollment_id_for_log = None
    try:
        active_enrollment = (
            db.query(Enrollment)
            .filter(
                Enrollment.lead_id == lead.id,
                Enrollment.status == EnrollmentStatus.active.value,
            )
            .first()
        )
        if active_enrollment is not None:
            enrollment_id_for_log = active_enrollment.id
            active_enrollment.status = EnrollmentStatus.paused_reply.value
            db.commit()
            logger.info(
                "postmark_inbound: enrollment paused lead=%s enrollment=%s",
                lead.id,
                active_enrollment.id,
            )

        firm_owner = (
            db.query(User)
            .filter(
                User.firm_id == lead.firm_id,
                User.role == UserRole.firm_owner,
            )
            .first()
        )
        if firm_owner is None:
            logger.warning(
                "postmark_inbound: no firm owner for firm=%s lead=%s -- notification skipped",
                lead.firm_id,
                lead.id,
            )
        else:
            NotificationService.create_notification(
                db=db,
                firm_id=lead.firm_id,
                recipient_id=firm_owner.id,
                recipient_type=RecipientType.staff,
                title="Lead replied -- automation paused",
                body=(
                    "A lead replied to an automated email. Their sequence has been paused"
                    " and is awaiting your review before automation resumes."
                ),
                notification_type=NotificationType.lead_replied,
                tier=NotificationTier.loud,
                related_entity_type="lead",
                related_entity_id=lead.id,
            )
    except Exception:
        logger.exception(
            "postmark_inbound: pause/notify failed lead=%s enrollment=%s",
            lead.id,
            enrollment_id_for_log,
        )

    return {"status": "ok"}
