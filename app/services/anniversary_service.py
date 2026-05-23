# app/services/anniversary_service.py

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, extract

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.user import User
from app.core.enums import UserRole, RecipientType, NotificationType
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def check_client_anniversaries() -> None:
    db = SessionLocal()
    try:
        current_year = datetime.now(timezone.utc).year

        clients_with_engagement_this_year = (
            select(Engagement.client_id)
            .where(
                extract("year", Engagement.created_at) == current_year
            )
            .scalar_subquery()
        )

        latest_engagement = (
            select(
                Engagement.client_id,
                func.max(Engagement.created_at).label("last_engagement"),
            )
            .group_by(Engagement.client_id)
            .subquery()
        )

        ten_months_ago = datetime.now(timezone.utc) - timedelta(days=305)

        flagged = db.execute(
            select(Client, latest_engagement.c.last_engagement)
            .join(
                latest_engagement,
                Client.id == latest_engagement.c.client_id,
            )
            .where(Client.id.not_in(clients_with_engagement_this_year))
            .where(latest_engagement.c.last_engagement < ten_months_ago)
            .where(Client.is_active == True)
        ).all()

        for client, last_engagement in flagged:
            recipients = db.execute(
                select(User).where(
                    User.firm_id == client.firm_id,
                    User.role.in_([UserRole.firm_owner, UserRole.manager]),
                    User.is_active == True,
                )
            ).scalars().all()

            last_date = last_engagement.strftime("%B %Y")

            for recipient in recipients:
                NotificationService.create_notification(
                    db=db,
                    firm_id=client.firm_id,
                    recipient_id=recipient.id,
                    recipient_type=RecipientType.staff,
                    title="Client not yet scheduled this year",
                    body=(
                        f"{client.name} has no engagement opened in {current_year}. "
                        f"Last active: {last_date}."
                    ),
                    notification_type=NotificationType.client_anniversary,
                    related_entity_type="client",
                    related_entity_id=client.id,
                )

        logger.info(
            "Anniversary check complete: %d clients flagged across all firms",
            len(flagged),
        )

    except Exception as e:
        logger.error("Anniversary check failed: %s", str(e))
    finally:
        db.close()
