# app/services/anniversary_service.py

import logging
from datetime import date, datetime, timezone, timedelta

from sqlalchemy import select, func, extract

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.user import User
from app.core.enums import UserRole, RecipientType, NotificationType
from app.services.notification_service import NotificationService
from app.services.behavioral_log import log_event

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


def check_document_expiries() -> None:
    from app.db.session import SessionLocal
    from app.crud.document_expiry import get_expiring_soon
    from app.models.user import User
    from app.core.enums import UserRole, RecipientType, NotificationType
    from app.services.notification_service import NotificationService
    from sqlalchemy import select

    db = SessionLocal()
    try:
        expiring = get_expiring_soon(db, days_ahead=60)
        for expiry in expiring:
            days_left = (expiry.expires_on - date.today()).days
            recipients = db.execute(
                select(User).where(
                    User.firm_id == expiry.firm_id,
                    User.role.in_([
                        UserRole.firm_owner,
                        UserRole.manager,
                    ]),
                    User.is_active == True,
                )
            ).scalars().all()
            for recipient in recipients:
                NotificationService.create_notification(
                    db=db,
                    firm_id=expiry.firm_id,
                    recipient_id=recipient.id,
                    recipient_type=RecipientType.staff,
                    title="Document expiring soon",
                    body=(
                        f"{expiry.document_type}"
                        f" for client expires in"
                        f" {days_left} days"
                        f" ({expiry.expires_on})."
                    ),
                    notification_type=(
                        NotificationType.document_expiry_alert
                    ),
                    related_entity_type="client",
                    related_entity_id=expiry.client_id,
                )
            expiry.expiry_notification_sent = True
            db.commit()
        logger.info(
            "Document expiry check complete: %d expiring soon",
            len(expiring),
        )
    except Exception as e:
        logger.error("Document expiry check failed: %s", str(e))
    finally:
        db.close()


def check_credential_expiries() -> None:
    from app.crud import staff_credential as crud_staff_credential
    from app.models.notification import Notification

    db = SessionLocal()
    try:
        expiring = crud_staff_credential.get_expiring_soon(db, days_ahead=60)
        for credential in expiring:
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            existing = db.execute(
                select(Notification).where(
                    Notification.related_entity_type == "staff_credential",
                    Notification.related_entity_id == credential.id,
                    Notification.created_at >= week_ago,
                )
            ).scalars().first()
            if existing:
                continue

            staff_user = db.execute(
                select(User).where(User.id == credential.user_id)
            ).scalars().first()
            user_name = staff_user.full_name if staff_user and staff_user.full_name else "Staff member"

            days_until_expiry = (credential.expires_at - date.today()).days

            managers = db.execute(
                select(User).where(
                    User.firm_id == credential.firm_id,
                    User.role.in_([UserRole.firm_owner, UserRole.manager]),
                    User.is_active == True,
                )
            ).scalars().all()

            for manager in managers:
                NotificationService.create_notification(
                    db=db,
                    firm_id=credential.firm_id,
                    recipient_id=manager.id,
                    recipient_type=RecipientType.staff,
                    title="Credential Expiring Soon",
                    body=(
                        f"{user_name}'s {credential.credential_type.value} expires on {credential.expires_at}."
                    ),
                    notification_type=NotificationType.deadline_alert,
                    related_entity_type="staff_credential",
                    related_entity_id=credential.id,
                )

            log_event(
                event_type="staff.credential_expiry_warning",
                firm_id=credential.firm_id,
                entity_type="staff_credential",
                entity_id=credential.id,
                metadata={
                    "credential_type": credential.credential_type.value,
                    "user_id": str(credential.user_id),
                    "expires_at": credential.expires_at.isoformat(),
                    "days_until_expiry": days_until_expiry,
                },
            )

        logger.info(
            "Credential expiry check complete: %d credentials expiring soon",
            len(expiring),
        )

    except Exception as e:
        logger.error("Credential expiry check failed: %s", str(e))
    finally:
        db.close()
