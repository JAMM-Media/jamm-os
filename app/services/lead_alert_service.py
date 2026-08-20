# app/services/lead_alert_service.py
"""
Alert logic for significant lead events that require immediate firm-owner attention.

Currently covers: hot lead alert (Contract section 7.5).

NOTE: The notification type string "lead_hot_alert" is a proposed name and must
receive Andrew's sign-off before any live firm is on this feature. Event-type
strings freeze once a firm goes live (Contract section 9.1).
"""

import logging

from sqlalchemy.orm import Session

from app.core.enums import NotificationType, RecipientType, UserRole
from app.models.lead import Lead
from app.models.user import User
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def maybe_fire_hot_lead_alert(db: Session, lead: Lead, previous_hot: bool) -> None:
    """Fire an immediate hot lead alert if the lead was just marked hot.

    Fires when the lead transitions from not-hot to hot. Has no effect if
    the lead was already hot before the current operation.

    Reuses the same firm_owner lookup and fire-and-forget notification
    pattern as the R1 hold-for-approval alert and the lead-replied alert.

    Contract section 7.5: "Hot fires an immediate owner alert; hot leads
    should get a human same-day, not just the sequence."
    """
    if previous_hot or not lead.hot:
        return

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
            "hot_lead_alert: no firm owner found for firm=%s lead=%s -- notification skipped",
            lead.firm_id,
            lead.id,
        )
        return

    NotificationService.create_notification(
        db=db,
        firm_id=lead.firm_id,
        recipient_id=firm_owner.id,
        recipient_type=RecipientType.staff,
        title=f"Hot lead: {lead.name}",
        body=(
            f"Lead {lead.name} has been marked hot and needs same-day follow-up."
            " Check their urgency notes and reach out before they look elsewhere."
        ),
        notification_type=NotificationType.lead_hot_alert,
        related_entity_type="lead",
        related_entity_id=lead.id,
    )
    logger.info(
        "hot_lead_alert: fired for lead=%s firm=%s owner=%s",
        lead.id,
        lead.firm_id,
        firm_owner.id,
    )
